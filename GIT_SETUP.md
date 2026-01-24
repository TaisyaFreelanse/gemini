# 📦 Інструкція для завантаження проекту на Git

## ✅ Файли створені

- ✅ `.gitignore` - виключає непотрібні файли з репозиторію
- ✅ `.dockerignore` - оптимізує Docker образи

---

## 🔒 Перевірка перед публікацією

### ВАЖЛИВО! Перевірте що ці файли НЕ потраплять в Git:

```bash
# 1. Перевірте що .env виключено
git status | grep .env

# Якщо .env видно - це помилка! Видаліть його з tracking:
git rm --cached .env

# 2. Перевірте що немає секретів
git status | grep -E "(password|secret|key|token)"
```

### ⚠️ Змініть секрети в .env.example на placeholder:

Відкрийте `.env.example` та замініть:
- ✅ `GEMINI_API_KEY=your_gemini_api_key_here`
- ✅ `POSTGRES_PASSWORD=your_secure_password`
- ✅ `WEBHOOK_TOKEN=your_webhook_token`

---

## 🚀 Команди для публікації на Git

### 1. Ініціалізація Git (якщо ще не зроблено)

```bash
cd c:\Users\GameOn-DP\Desktop\gemini
git init
```

### 2. Додати remote repository

```bash
# GitHub
git remote add origin https://github.com/your-username/web-scraper-gemini.git

# або GitLab
git remote add origin https://gitlab.com/your-username/web-scraper-gemini.git

# або Bitbucket
git remote add origin https://bitbucket.org/your-username/web-scraper-gemini.git
```

### 3. Створити .gitattributes (опційно, для Windows)

```bash
echo "* text=auto eol=lf" > .gitattributes
echo "*.png binary" >> .gitattributes
echo "*.jpg binary" >> .gitattributes
```

### 4. Додати всі файли

```bash
git add .
```

### 5. Перевірити що додається

```bash
git status
```

**Переконайтесь що НЕ додається:**
- ❌ `.env`
- ❌ `__pycache__/`
- ❌ `node_modules/`
- ❌ `postgres_data/`
- ❌ `*.log`
- ❌ `dump.rdb`

### 6. Створити перший commit

```bash
git commit -m "Initial commit: Web Scraper Gemini AI

Features:
- FastAPI backend with async web scraping
- Gemini AI integration for promo code extraction
- Redis caching (404x speedup)
- Rate limiting (100 req/min)
- PostgreSQL database with migrations
- Celery workers for background tasks
- React frontend with Tailwind CSS
- Docker Compose setup
- 4000-7991 domains/hour performance

Status: Production Ready ✅"
```

### 7. Створити branch (опційно)

```bash
# Якщо хочете використовувати main замість master
git branch -M main
```

### 8. Push на GitHub

```bash
# Перший push
git push -u origin main

# Або якщо master
git push -u origin master
```

---

## 📝 Створення README.md для GitHub

Ваш `README.md` вже готовий! Він містить:
- ✅ Опис проекту
- ✅ Архітектуру
- ✅ Інструкції запуску
- ✅ API endpoints
- ✅ Документацію

---

## 🏷️ Додавання тегів (releases)

```bash
# Створити перший release
git tag -a v1.0.0 -m "Release v1.0.0 - Production Ready

- Full integration with Gemini AI
- Redis caching with 404x speedup
- Rate limiting 100 req/min
- Performance: 4000-7991 domains/hour
- Docker Compose setup
- Complete documentation"

# Push тега
git push origin v1.0.0
```

---

## 📋 Рекомендований .github/workflows (CI/CD)

Створіть `.github/workflows/test.yml` для автоматичного тестування:

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:15-alpine
        env:
          POSTGRES_PASSWORD: test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
      
      redis:
        image: redis:7-alpine
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          cd backend
          pip install -r requirements.txt
      
      - name: Run tests
        env:
          DATABASE_URL: postgresql://postgres:test@localhost:5432/test_db
          REDIS_URL: redis://localhost:6379/0
          GEMINI_API_KEY: test_key
        run: |
          cd backend
          python -m pytest tests/ -v
```

---

## 🔐 Робота з секретами на GitHub

### Для GitHub Actions, додайте secrets:

1. Перейдіть в Settings → Secrets → Actions
2. Додайте:
   - `GEMINI_API_KEY`
   - `POSTGRES_PASSWORD`
   - `WEBHOOK_TOKEN`

---

## 📊 GitHub Project Badges

Додайте в `README.md` на початку:

```markdown
# Web Scraper Gemini AI

![Docker](https://img.shields.io/badge/Docker-Ready-blue?logo=docker)
![Python](https://img.shields.io/badge/Python-3.11+-green?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-Latest-teal?logo=fastapi)
![React](https://img.shields.io/badge/React-18-blue?logo=react)
![License](https://img.shields.io/badge/License-MIT-yellow)
![Status](https://img.shields.io/badge/Status-Production%20Ready-success)
```

---

## ✅ Checklist перед push

- [ ] `.env` НЕ в Git (перевірити git status)
- [ ] `.env.example` має placeholder значення (не реальні ключі)
- [ ] `README.md` оновлений
- [ ] Всі тести пройдені локально
- [ ] Docker Compose працює
- [ ] Немає hardcoded паролів у коді
- [ ] `GEMINI_API_KEY` не в коді
- [ ] `.gitignore` включає всі потрібні виключення
- [ ] Видалено всі `TODO` та debug коментарі
- [ ] Документація актуальна

---

## 🌟 Після публікації

### 1. Додайте Topics на GitHub:
- `web-scraping`
- `gemini-ai`
- `fastapi`
- `react`
- `docker`
- `celery`
- `postgresql`
- `redis`
- `promo-codes`
- `python`
- `javascript`

### 2. Створіть GitHub Pages (опційно)
- Можна опублікувати документацію з папки `docs/`

### 3. Додайте LICENSE файл
- Рекомендується MIT або Apache 2.0

---

## 🚨 Що НІКОЛИ не повинно потрапити в Git:

❌ `.env` файл з реальними секретами  
❌ `postgres_data/` - дані бази  
❌ `node_modules/` - залежності  
❌ `__pycache__/` - Python cache  
❌ `*.log` - логи  
❌ `dump.rdb` - Redis dump  
❌ API ключі та паролі  
❌ SSL сертифікати  

---

## 📞 Підтримка

Якщо потрібна допомога:
1. Перевірте документацію в `README.md`
2. Створіть Issue на GitHub
3. Контакт: your-email@example.com

---

**Готово! Проект готовий до публікації на Git!** 🚀
