import logging
from typing import Dict, List, Optional, Callable
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.job import Job
from apscheduler.jobstores.memory import MemoryJobStore
import asyncio

from app.core.config import settings
import redis
import json

logger = logging.getLogger(__name__)

# Redis клієнт для читання конфігурації
_redis_client = None

def _get_redis():
    """Отримати Redis клієнт (lazy init)"""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.REDIS_URL)
    return _redis_client


def _redis_str(key: str, default: str = "") -> str:
    """Прочитати строку з Redis"""
    try:
        raw = _get_redis().get(key)
        return raw.decode().strip() if raw else default
    except Exception:
        return default


def _redis_int(key: str, default: int) -> int:
    """Прочитати int з Redis"""
    try:
        raw = _get_redis().get(key)
        return int(raw.decode()) if raw else default
    except Exception:
        return default


REDIS_JOBS_KEY = "scheduler:jobs"


def _save_job_to_redis(job_id: str, job_data: Dict):
    """Зберегти job в Redis для відновлення після рестарту"""
    try:
        r = _get_redis()
        r.hset(REDIS_JOBS_KEY, job_id, json.dumps(job_data))
        print(f"  ✓ Job {job_id} saved to Redis", flush=True)
    except Exception as e:
        print(f"  ✗ Failed to save job {job_id} to Redis: {e}", flush=True)


def _delete_job_from_redis(job_id: str):
    """Видалити job з Redis"""
    try:
        r = _get_redis()
        r.hdel(REDIS_JOBS_KEY, job_id)
        print(f"  ✓ Job {job_id} deleted from Redis", flush=True)
    except Exception as e:
        print(f"  ✗ Failed to delete job {job_id} from Redis: {e}", flush=True)


def _get_saved_jobs_from_redis() -> Dict[str, Dict]:
    """Отримати збережені jobs з Redis"""
    try:
        r = _get_redis()
        jobs_raw = r.hgetall(REDIS_JOBS_KEY)
        jobs = {}
        for job_id, job_data in jobs_raw.items():
            job_id_str = job_id.decode() if isinstance(job_id, bytes) else job_id
            job_data_str = job_data.decode() if isinstance(job_data, bytes) else job_data
            jobs[job_id_str] = json.loads(job_data_str)
        return jobs
    except Exception as e:
        print(f"  ✗ Failed to get jobs from Redis: {e}", flush=True)
        return {}


def _get_current_config() -> Dict:
    """
    Отримати актуальну конфігурацію з Redis та .env
    Викликається в момент запуску задачі, щоб використати поточні налаштування
    """
    # Gemini
    gemini_key = _redis_str("config:gemini_key") or settings.GEMINI_API_KEY
    prompt_template = _redis_str("config:prompt") or None
    
    # Proxy - читаємо з Redis, fallback на .env
    proxy_host = _redis_str("config:proxy_host") or settings.PROXY_HOST
    proxy_login = _redis_str("config:proxy_login") or settings.PROXY_LOGIN
    proxy_password = _redis_str("config:proxy_password") or settings.PROXY_PASSWORD
    proxy_http_port = _redis_int("config:proxy_http_port", settings.PROXY_HTTP_PORT)
    proxy_socks_port = _redis_int("config:proxy_socks_port", settings.PROXY_SOCKS_PORT)
    
    # Webhook
    webhook_url = _redis_str("config:webhook_url") or settings.WEBHOOK_URL
    webhook_token = _redis_str("config:webhook_token") or settings.WEBHOOK_TOKEN
    
    config = {
        'gemini_key': gemini_key,
        'prompt': prompt_template,
        'webhook': {
            'url': webhook_url,
            'token': webhook_token
        },
        'proxy': {
            'host': proxy_host,
            'http_port': proxy_http_port,
            'socks_port': proxy_socks_port,
            'login': proxy_login,
            'password': proxy_password
        } if proxy_host else None
    }
    
    logger.info(f"Config loaded: proxy={'enabled' if proxy_host else 'disabled'}, host={proxy_host}")
    
    return config


class SchedulerService:
    """
    Сервіс для автоматизації парсингу через cron
    
    Основні можливості:
    - Підтримка cron expressions (напр. "0 */6 * * *")
    - Повний парсинг всіх доменів
    - Частковий парсинг (N доменів за раз)
    - Управління задачами (додавання, видалення, пауза)
    - Моніторинг виконання задач
    """
    
    def __init__(self):
        """Ініціалізація scheduler"""
        # Налаштування jobstore
        jobstores = {
            'default': MemoryJobStore()
        }
        
        # Налаштування executor
        job_defaults = {
            'coalesce': True,  # Об'єднати пропущені запуски
            'max_instances': 1,  # Не запускати паралельні копії однієї задачі
            'misfire_grace_time': 300  # 5 хвилин grace period
        }
        
        self.scheduler = AsyncIOScheduler(
            jobstores=jobstores,
            job_defaults=job_defaults,
            timezone='UTC'
        )
        
        self._is_running = False
        logger.info("SchedulerService ініціалізовано")
    
    def start(self):
        """Запустити scheduler"""
        print(f"  SchedulerService.start() called, _is_running={self._is_running}", flush=True)
        if not self._is_running:
            try:
                # Для AsyncIOScheduler потрібен event loop
                import asyncio
                try:
                    loop = asyncio.get_running_loop()
                    print(f"  Event loop found: {loop}", flush=True)
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    print(f"  Created new event loop: {loop}", flush=True)
                
                self.scheduler.start()
                self._is_running = True
                print(f"  ✓ Scheduler started successfully, state: {self.scheduler.state}", flush=True)
                logger.info("✓ Scheduler запущено")
                
                # Відновлюємо збережені jobs з Redis
                self._restore_jobs_from_redis()
                
            except Exception as e:
                print(f"  ✗ Scheduler start error: {e}", flush=True)
                import traceback
                traceback.print_exc()
        else:
            logger.warning("Scheduler вже запущений")
    
    def _restore_jobs_from_redis(self):
        """Відновити збережені jobs з Redis після рестарту"""
        print("  Restoring jobs from Redis...", flush=True)
        saved_jobs = _get_saved_jobs_from_redis()
        
        if not saved_jobs:
            print("  No saved jobs found in Redis", flush=True)
            return
        
        print(f"  Found {len(saved_jobs)} saved jobs in Redis", flush=True)
        
        for job_id, job_data in saved_jobs.items():
            try:
                job_type = job_data.get('type')
                cron_expression = job_data.get('cron_expression')
                domains = job_data.get('domains', [])
                
                print(f"  Restoring job {job_id}: type={job_type}, cron={cron_expression}, domains={len(domains)}", flush=True)
                
                if job_type == 'full_scraping' and domains:
                    # Відновлюємо full_scraping job
                    self.schedule_full_scraping(
                        cron_expression=cron_expression,
                        domains=domains,
                        config=None,
                        save_to_redis=False  # Не зберігати повторно
                    )
                    print(f"  ✓ Job {job_id} restored successfully", flush=True)
                elif job_type == 'partial_scraping' and domains:
                    batch_size = job_data.get('batch_size', 500)
                    self.schedule_partial_scraping(
                        cron_expression=cron_expression,
                        all_domains=domains,
                        batch_size=batch_size,
                        config=None,
                        save_to_redis=False
                    )
                    print(f"  ✓ Job {job_id} restored successfully", flush=True)
                else:
                    print(f"  ⚠ Unknown job type or empty domains: {job_type}", flush=True)
                    
            except Exception as e:
                print(f"  ✗ Failed to restore job {job_id}: {e}", flush=True)
                import traceback
                traceback.print_exc()
    
    def shutdown(self, wait: bool = True):
        """
        Зупинити scheduler
        
        Args:
            wait: Чекати завершення поточних задач
        """
        if self._is_running:
            self.scheduler.shutdown(wait=wait)
            self._is_running = False
            logger.info("✓ Scheduler зупинено")
        else:
            logger.warning("Scheduler вже зупинений")
    
    def is_running(self) -> bool:
        """Перевірити чи працює scheduler"""
        return self._is_running
    
    # ========== Додавання задач ==========
    
    def add_cron_job(
        self,
        job_id: str,
        func: Callable,
        cron_expression: str,
        args: tuple = (),
        kwargs: dict = None,
        description: str = ""
    ) -> Optional[Job]:
        """
        Додати задачу з cron expression
        
        Args:
            job_id: Унікальний ID задачі
            func: Функція для виконання
            cron_expression: Cron expression (напр. "0 */6 * * *")
            args: Позиційні аргументи для функції
            kwargs: Іменовані аргументи для функції
            description: Опис задачі
        
        Returns:
            Job instance або None якщо помилка
        
        Examples:
            - "0 */6 * * *" - кожні 6 годин
            - "0 0 * * *" - щодня о 00:00
            - "*/30 * * * *" - кожні 30 хвилин
        """
        try:
            # Парсимо cron expression (5 полів: minute hour day month day_of_week)
            raw = (cron_expression or "").strip()
            parts = raw.split()
            # Нормалізація: якщо 4 поля — додати day_of_week=*
            if len(parts) == 4:
                parts.append('*')
            if len(parts) == 1:
                if parts[0] == '*' or parts[0].lower() == 'every_minute':
                    parts = ['*', '*', '*', '*', '*']  # кожну хвилину
                else:
                    parts = [parts[0], '*', '*', '*', '*']  # хв N щогодини
            if len(parts) != 5:
                raise ValueError(
                    "Cron має 5 полів: minute hour day month day_of_week. "
                    "Приклад: * * * * * (кожну хв), */5 * * * * (кожні 5 хв), 0 */6 * * * (кожні 6 год)"
                )
            expr = ' '.join(parts)
            trigger = CronTrigger.from_crontab(expr, timezone='UTC')
            
            # Обгортка для логування виклику
            def job_wrapper(*a, **kw):
                logger.info(f"🔔 CRON TRIGGER FIRED: {job_id}")
                try:
                    return func(*a, **kw)
                except Exception as e:
                    logger.error(f"✗ Job {job_id} failed: {e}")
                    raise
            
            job = self.scheduler.add_job(
                func=job_wrapper,
                trigger=trigger,
                id=job_id,
                args=args,
                kwargs=kwargs or {},
                replace_existing=True
            )
            
            logger.info(
                f"✓ Додано cron задачу '{job_id}': {cron_expression} "
                f"(наступний запуск: {job.next_run_time})"
            )
            logger.info(f"  Scheduler running: {self._is_running}, Jobs count: {len(self.scheduler.get_jobs())}")
            
            return job
            
        except Exception as e:
            logger.error(f"✗ Помилка додавання cron задачі '{job_id}': {e}")
            return None
    
    def add_interval_job(
        self,
        job_id: str,
        func: Callable,
        interval_minutes: int,
        args: tuple = (),
        kwargs: dict = None,
        description: str = ""
    ) -> Optional[Job]:
        """
        Додати задачу з інтервалом
        
        Args:
            job_id: Унікальний ID задачі
            func: Функція для виконання
            interval_minutes: Інтервал в хвилинах
            args: Позиційні аргументи
            kwargs: Іменовані аргументи
            description: Опис задачі
        
        Returns:
            Job instance або None
        """
        try:
            trigger = IntervalTrigger(minutes=interval_minutes, timezone='UTC')
            
            job = self.scheduler.add_job(
                func=func,
                trigger=trigger,
                id=job_id,
                args=args,
                kwargs=kwargs or {},
                replace_existing=True
            )
            
            logger.info(
                f"✓ Додано interval задачу '{job_id}': кожні {interval_minutes} хв "
                f"(наступний запуск: {job.next_run_time})"
            )
            
            return job
            
        except Exception as e:
            logger.error(f"✗ Помилка додавання interval задачі '{job_id}': {e}")
            return None
    
    # ========== Управління задачами ==========
    
    def remove_job(self, job_id: str) -> bool:
        """
        Видалити задачу
        
        Args:
            job_id: ID задачі
        
        Returns:
            True якщо успішно видалено
        """
        try:
            self.scheduler.remove_job(job_id)
            # Видаляємо з Redis також
            _delete_job_from_redis(job_id)
            logger.info(f"✓ Задачу '{job_id}' видалено")
            return True
        except Exception as e:
            logger.error(f"✗ Помилка видалення задачі '{job_id}': {e}")
            return False
    
    def pause_job(self, job_id: str) -> bool:
        """Призупинити задачу"""
        try:
            self.scheduler.pause_job(job_id)
            logger.info(f"✓ Задачу '{job_id}' призупинено")
            return True
        except Exception as e:
            logger.error(f"✗ Помилка призупинення задачі '{job_id}': {e}")
            return False
    
    def resume_job(self, job_id: str) -> bool:
        """Відновити задачу"""
        try:
            self.scheduler.resume_job(job_id)
            logger.info(f"✓ Задачу '{job_id}' відновлено")
            return True
        except Exception as e:
            logger.error(f"✗ Помилка відновлення задачі '{job_id}': {e}")
            return False
    
    def get_job(self, job_id: str) -> Optional[Job]:
        """Отримати інформацію про задачу"""
        return self.scheduler.get_job(job_id)
    
    def get_all_jobs(self) -> List[Dict]:
        """
        Отримати список всіх задач
        
        Returns:
            List[Dict] з інформацією про задачі
        """
        jobs = self.scheduler.get_jobs()
        
        result = []
        for job in jobs:
            result.append({
                'id': job.id,
                'name': job.name,
                'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None,
                'trigger': str(job.trigger),
                'func': f"{job.func.__module__}.{job.func.__name__}",
                'pending': job.pending
            })
        
        return result
    
    # ========== Спеціалізовані задачі для парсингу ==========
    
    def schedule_full_scraping(
        self,
        cron_expression: str,
        domains: List[str],
        config: Optional[Dict] = None,
        save_to_redis: bool = True
    ) -> Optional[Job]:
        """
        Запланувати повний парсинг всіх доменів
        
        Args:
            cron_expression: Cron вираз (напр. "0 0 * * *")
            domains: Список доменів для парсингу
            config: Додаткова конфігурація (ігнорується, читається з Redis/.env)
            save_to_redis: Зберігати в Redis для відновлення після рестарту
        
        Returns:
            Job instance або None
        """
        from app.tasks.scraping_tasks import start_batch_scraping
        from app.db.session import SessionLocal
        from app.db import crud
        
        job_id = "full_scraping"
        
        # Зберігаємо в Redis для відновлення після рестарту
        if save_to_redis:
            _save_job_to_redis(job_id, {
                'type': 'full_scraping',
                'cron_expression': cron_expression,
                'domains': domains
            })
        
        def run_full_scraping():
            """Wrapper для синхронного виклику Celery task"""
            print(f"🚀 CRON JOB TRIGGERED: run_full_scraping at {datetime.now()}", flush=True)
            logger.info("🚀 CRON JOB TRIGGERED: run_full_scraping")
            
            try:
                # Перевіряємо чи є активна сесія парсингу
                r = _get_redis()
                active_session = r.get("parsing:active_session")
                if active_session:
                    active_session_id = active_session.decode() if isinstance(active_session, bytes) else active_session
                    print(f"⏭ Пропускаємо: активна сесія {active_session_id} ще не завершена", flush=True)
                    logger.warning(f"Пропускаємо запуск: активна сесія {active_session_id} ще не завершена")
                    return
                
                # Читаємо актуальний конфіг в момент запуску (не при створенні job)
                runtime_config = _get_current_config()
                logger.info(f"Config loaded, proxy: {runtime_config.get('proxy', {}).get('host', 'none')}")
                
                # Створюємо сесію в БД
                db = SessionLocal()
                try:
                    db_session = crud.create_scraping_session(db, total_domains=len(domains))
                    session_id = db_session.id
                    
                    # Позначаємо активну сесію в Redis (TTL 2 години)
                    r.setex("parsing:active_session", 7200, str(session_id))
                    
                    # Встановлюємо статус для Dashboard
                    r.set("scraping:status", "running")
                    r.set("scraping:session_id", str(session_id))
                    
                    print(f"✓ Запуск повного парсингу: {len(domains)} доменів, сесія {session_id}", flush=True)
                    logger.info(f"✓ Запуск повного парсингу: {len(domains)} доменів, сесія {session_id}")
                    
                    result = start_batch_scraping.delay(domains, session_id, runtime_config)
                    print(f"✓ Celery task запущено: {result.id}", flush=True)
                    logger.info(f"✓ Celery task запущено: {result.id}")
                except Exception as e:
                    print(f"✗ Помилка створення сесії парсингу: {e}", flush=True)
                    logger.error(f"✗ Помилка створення сесії парсингу: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                finally:
                    db.close()
            except Exception as e:
                print(f"✗ CRON JOB ERROR: {e}", flush=True)
                logger.error(f"✗ CRON JOB ERROR: {e}")
                import traceback
                logger.error(traceback.format_exc())
        
        return self.add_cron_job(
            job_id=job_id,
            func=run_full_scraping,
            cron_expression=cron_expression,
            description=f"Повний парсинг {len(domains)} доменів"
        )
    
    def schedule_partial_scraping(
        self,
        cron_expression: str,
        all_domains: List[str],
        batch_size: int = 500,
        config: Optional[Dict] = None,
        save_to_redis: bool = True
    ) -> Optional[Job]:
        """
        Запланувати частковий парсинг (N доменів за раз)
        
        Args:
            cron_expression: Cron вираз
            all_domains: Повний список доменів
            batch_size: Кількість доменів в одній пачці
            config: Додаткова конфігурація (ігнорується, читається з Redis/.env)
            save_to_redis: Зберігати в Redis для відновлення після рестарту
        
        Returns:
            Job instance або None
        """
        from app.tasks.scraping_tasks import start_batch_scraping
        from app.db.session import SessionLocal
        from app.db import crud
        import random
        
        job_id = "partial_scraping"
        
        # Зберігаємо в Redis для відновлення після рестарту
        if save_to_redis:
            _save_job_to_redis(job_id, {
                'type': 'partial_scraping',
                'cron_expression': cron_expression,
                'domains': all_domains,
                'batch_size': batch_size
            })
        
        def run_partial_scraping():
            """Wrapper для часткового парсингу"""
            # Читаємо актуальний конфіг в момент запуску
            runtime_config = _get_current_config()
            
            # Вибираємо випадкові домени для парсингу
            domains_batch = random.sample(
                all_domains,
                min(batch_size, len(all_domains))
            )
            
            # Створюємо сесію в БД
            db = SessionLocal()
            try:
                r = _get_redis()
                
                # Перевіряємо чи є активна сесія парсингу
                active_session = r.get("parsing:active_session")
                if active_session:
                    active_session_id = active_session.decode() if isinstance(active_session, bytes) else active_session
                    logger.warning(f"Пропускаємо запуск: активна сесія {active_session_id} ще не завершена")
                    return
                
                db_session = crud.create_scraping_session(db, total_domains=len(domains_batch))
                session_id = db_session.id
                
                # Позначаємо активну сесію в Redis
                r.setex("parsing:active_session", 7200, str(session_id))
                r.set("scraping:status", "running")
                r.set("scraping:session_id", str(session_id))
                
                logger.info(
                    f"Запуск часткового парсингу: {len(domains_batch)}/{len(all_domains)} доменів, "
                    f"сесія {session_id}"
                )
                
                result = start_batch_scraping.delay(domains_batch, session_id, runtime_config)
                logger.info(f"Celery task запущено: {result.id}")
            except Exception as e:
                logger.error(f"Помилка створення сесії парсингу: {e}")
            finally:
                db.close()
        
        return self.add_cron_job(
            job_id=job_id,
            func=run_partial_scraping,
            cron_expression=cron_expression,
            description=f"Частковий парсинг {batch_size}/{len(all_domains)} доменів"
        )
    
    def schedule_cleanup_old_sessions(
        self,
        interval_hours: int = 24
    ) -> Optional[Job]:
        """
        Запланувати очищення старих сесій з Redis
        
        Args:
            interval_hours: Інтервал в годинах
        
        Returns:
            Job instance або None
        """
        from app.tasks.scraping_tasks import cleanup_old_sessions
        
        def run_cleanup():
            """Wrapper для очищення"""
            logger.info("Запуск очищення старих сесій...")
            cleanup_old_sessions.delay()
        
        return self.add_interval_job(
            job_id="cleanup_sessions",
            func=run_cleanup,
            interval_minutes=interval_hours * 60,
            description="Очищення старих сесій з Redis"
        )


# Глобальний instance scheduler
_scheduler_instance: Optional[SchedulerService] = None


def get_scheduler() -> SchedulerService:
    """
    Отримати глобальний instance scheduler
    
    Returns:
        SchedulerService instance
    """
    global _scheduler_instance
    
    if _scheduler_instance is None:
        _scheduler_instance = SchedulerService()
    
    return _scheduler_instance


def init_default_jobs(domains: List[str], config: Optional[Dict] = None):
    """
    Ініціалізувати дефолтні задачі
    
    Args:
        domains: Список доменів для парсингу
        config: Конфігурація парсингу
    """
    scheduler = get_scheduler()
    
    # Запускаємо scheduler якщо не запущений
    if not scheduler.is_running():
        scheduler.start()
    
    logger.info("Ініціалізація дефолтних cron задач...")
    
    # 1. Повний парсинг кожні 6 годин
    scheduler.schedule_full_scraping(
        cron_expression="0 */6 * * *",
        domains=domains,
        config=config
    )
    
    # 2. Частковий парсинг кожні 2 години (500 доменів)
    scheduler.schedule_partial_scraping(
        cron_expression="0 */2 * * *",
        all_domains=domains,
        batch_size=500,
        config=config
    )
    
    # 3. Очищення старих сесій раз на добу
    scheduler.schedule_cleanup_old_sessions(interval_hours=24)
    
    logger.info("✓ Дефолтні cron задачі додано")
    
    # Виводимо список задач
    jobs = scheduler.get_all_jobs()
    logger.info(f"Активних задач: {len(jobs)}")
    for job in jobs:
        logger.info(f"  - {job['id']}: наступний запуск {job['next_run_time']}")
