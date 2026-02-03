import { useState, useEffect } from 'react';
import { schedulerAPI, configAPI, parsingAPI } from '../api/client';

export default function Scheduler() {
  const [status, setStatus] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAddForm, setShowAddForm] = useState(false);
  const [newJob, setNewJob] = useState({
    job_id: '',
    cron_expression: '',  // користувач повинен обрати
    job_type: 'full_scraping',
    domains: '',
    batch_size: 500,
    domainSource: 'uploaded',  // 'uploaded', 'manual', 'api'
  });
  const [message, setMessage] = useState(null);
  const [uploadedDomainsCount, setUploadedDomainsCount] = useState(0);
  const [apiUrl, setApiUrl] = useState('');
  const [apiDomains, setApiDomains] = useState([]);
  const [apiLoading, setApiLoading] = useState(false);
  const [diagnostic, setDiagnostic] = useState(null);
  const [clearingQueue, setClearingQueue] = useState(false);

  useEffect(() => {
    fetchStatus();
    fetchUploadedDomains();
    fetchDiagnostic();
    const interval = setInterval(() => {
      fetchStatus();
      fetchDiagnostic();
    }, 10000);
    return () => clearInterval(interval);
  }, []);

  const fetchDiagnostic = async () => {
    try {
      const response = await parsingAPI.diagnostic();
      setDiagnostic(response.data);
    } catch (err) {
      console.error('Error fetching diagnostic:', err);
    }
  };

  const handleClearStuckSession = async () => {
    if (!confirm('Очистити застряглу сесію? Це скасує всі активні задачі парсингу.')) return;
    
    setClearingQueue(true);
    try {
      // Спочатку очищаємо чергу
      const clearResult = await parsingAPI.clearQueue();
      // Потім синхронізуємо стан
      await parsingAPI.syncState();
      
      setMessage({ 
        type: 'success', 
        text: `Застряглу сесію очищено. ${clearResult.data?.details?.purged_count || 0} задач скасовано.`
      });
      
      // Оновлюємо діагностику
      fetchDiagnostic();
      fetchStatus();
    } catch (err) {
      setMessage({ type: 'error', text: `Помилка очищення: ${err.response?.data?.detail || err.message}` });
    } finally {
      setClearingQueue(false);
    }
  };

  const fetchUploadedDomains = async () => {
    try {
      const response = await configAPI.getDomains();
      setUploadedDomainsCount(response.data.count || 0);
    } catch (err) {
      console.error('Error fetching uploaded domains:', err);
    }
  };

  const fetchStatus = async () => {
    try {
      const response = await schedulerAPI.status();
      setStatus(response.data);
      setJobs(response.data.jobs || []);
      setLoading(false);
    } catch (err) {
      console.error('Error fetching scheduler status:', err);
      setLoading(false);
    }
  };

  const handleStartStop = async () => {
    try {
      if (status?.is_running) {
        await schedulerAPI.stop();
        setMessage({ type: 'success', text: 'Scheduler зупинено' });
      } else {
        await schedulerAPI.start();
        setMessage({ type: 'success', text: 'Scheduler запущено' });
      }
      fetchStatus();
    } catch (err) {
      setMessage({ type: 'error', text: `Помилка: ${err.message}` });
    }
  };

  const fetchDomainsFromApi = async () => {
    if (!apiUrl.trim()) {
      setMessage({ type: 'error', text: 'Введіть URL API' });
      return;
    }
    
    setApiLoading(true);
    try {
      const response = await schedulerAPI.fetchDomainsFromApi(apiUrl);
      const domains = response.data.domains || [];
      setApiDomains(domains);
      setMessage({ type: 'success', text: `Завантажено ${domains.length} доменів з API` });
    } catch (err) {
      setMessage({ type: 'error', text: `Помилка завантаження: ${err.response?.data?.detail || err.message}` });
      setApiDomains([]);
    } finally {
      setApiLoading(false);
    }
  };

  const handleAddJob = async (e) => {
    e.preventDefault();
    
    // Валідація cron виразу
    if (!newJob.cron_expression || newJob.cron_expression.trim() === '') {
      setMessage({ type: 'error', text: 'Оберіть розклад запуску' });
      return;
    }
    
    try {
      let domains = [];
      
      if (newJob.domainSource === 'uploaded') {
        // Отримуємо завантажені домени
        const response = await configAPI.getDomains();
        domains = response.data.domains || [];
        if (domains.length === 0) {
          setMessage({ type: 'error', text: 'Немає завантажених доменів. Завантажте JSON файл у Configuration.' });
          return;
        }
      } else if (newJob.domainSource === 'manual') {
        // Парсимо введені вручну
        domains = newJob.domains.split('\n').map(d => d.trim()).filter(Boolean);
        if (domains.length === 0) {
          setMessage({ type: 'error', text: 'Введіть хоча б один домен' });
          return;
        }
      } else if (newJob.domainSource === 'api') {
        // Використовуємо завантажені з API
        if (apiDomains.length === 0) {
          setMessage({ type: 'error', text: 'Спочатку завантажте домени з API' });
          return;
        }
        domains = apiDomains;
      }
      
      // Використовуємо введений ID або генеруємо автоматично
      const jobId = newJob.job_id.trim() || generateJobId();
      
      await schedulerAPI.addJob({
        job_id: jobId,
        cron_expression: newJob.cron_expression,
        job_type: newJob.job_type,
        domains,
        batch_size: parseInt(newJob.batch_size),
      });
      
      setMessage({ type: 'success', text: `Задачу успішно додано (${domains.length} доменів)` });
      setShowAddForm(false);
      setNewJob({
        job_id: '',
        cron_expression: '',
        job_type: 'full_scraping',
        domains: '',
        batch_size: 500,
        domainSource: 'uploaded',
      });
      setApiUrl('');
      setApiDomains([]);
      fetchStatus();
    } catch (err) {
      setMessage({ type: 'error', text: `Помилка: ${err.response?.data?.detail || err.message}` });
    }
  };

  const handleRemoveJob = async (jobId) => {
    if (!confirm(`Видалити задачу "${jobId}"?`)) return;
    
    try {
      await schedulerAPI.removeJob(jobId);
      setMessage({ type: 'success', text: 'Задачу видалено' });
      fetchStatus();
    } catch (err) {
      setMessage({ type: 'error', text: `Помилка: ${err.message}` });
    }
  };

  const handlePauseResume = async (jobId, isPending) => {
    try {
      if (isPending) {
        await schedulerAPI.resumeJob(jobId);
        setMessage({ type: 'success', text: 'Задачу відновлено' });
      } else {
        await schedulerAPI.pauseJob(jobId);
        setMessage({ type: 'success', text: 'Задачу призупинено' });
      }
      fetchStatus();
    } catch (err) {
      setMessage({ type: 'error', text: `Помилка: ${err.message}` });
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  const cronExamples = [
    { label: '-- Оберіть час --', value: '' },
    { label: '📅 Щодня о 09:00 UTC (11:00 Київ)', value: '0 9 * * *' },
    { label: '📅 Щодня о 11:00 UTC (13:00 Київ)', value: '0 11 * * *' },
    { label: '📅 Щодня о 17:00 UTC (19:00 Київ)', value: '0 17 * * *' },
    { label: '📅 Двічі на день: 09:00 та 17:00 UTC', value: '0 9,17 * * *' },
    { label: '⏰ Кожні 6 годин', value: '0 */6 * * *' },
    { label: '⏰ Кожні 2 години', value: '0 */2 * * *' },
    { label: '⏰ Кожні 30 хвилин', value: '*/30 * * * *' },
    { label: '📆 Понеділок о 09:00 UTC', value: '0 9 * * 1' },
    { label: '📆 Вівторок о 09:00 UTC', value: '0 9 * * 2' },
    { label: '📆 Середа о 09:00 UTC', value: '0 9 * * 3' },
    { label: '📆 Четвер о 09:00 UTC', value: '0 9 * * 4' },
    { label: '📆 П\'ятниця о 09:00 UTC', value: '0 9 * * 5' },
    { label: '🔧 Кожну хвилину (тест)', value: '* * * * *' },
  ];
  
  // Генерація ID задачі якщо не вказано
  const generateJobId = () => {
    const now = new Date();
    return `job_${now.getFullYear()}${(now.getMonth()+1).toString().padStart(2,'0')}${now.getDate().toString().padStart(2,'0')}_${now.getHours().toString().padStart(2,'0')}${now.getMinutes().toString().padStart(2,'0')}`;
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold text-gray-900">Scheduler</h1>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <div className={`h-3 w-3 rounded-full ${
              status?.is_running ? 'bg-green-500 animate-pulse' : 'bg-gray-400'
            }`}></div>
            <span className="text-sm font-medium text-gray-700">
              {status?.is_running ? 'Активний' : 'Зупинено'}
            </span>
          </div>
          <button
            onClick={handleStartStop}
            className={`px-4 py-2 rounded-md font-medium ${
              status?.is_running
                ? 'bg-red-600 text-white hover:bg-red-700'
                : 'bg-green-600 text-white hover:bg-green-700'
            }`}
          >
            {status?.is_running ? 'Зупинити' : 'Запустити'}
          </button>
        </div>
      </div>

      {message && (
        <div className={`px-4 py-3 rounded-md ${
          message.type === 'success' 
            ? 'bg-green-50 border border-green-200 text-green-700' 
            : 'bg-red-50 border border-red-200 text-red-700'
        }`}>
          {message.text}
        </div>
      )}

      {/* Блок діагностики застряглих сесій */}
      {diagnostic && (
        <div className={`rounded-lg shadow p-4 ${
          diagnostic.redis?.['parsing:active_session'] 
            ? 'bg-yellow-50 border-2 border-yellow-400' 
            : 'bg-white'
        }`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
                diagnostic.redis?.['parsing:active_session']
                  ? 'bg-yellow-200 text-yellow-800'
                  : 'bg-green-200 text-green-800'
              }`}>
                {diagnostic.redis?.['parsing:active_session'] ? '⚠️' : '✓'}
              </div>
              <div>
                <h3 className="font-medium text-gray-900">
                  {diagnostic.redis?.['parsing:active_session'] 
                    ? `Активна сесія #${diagnostic.redis['parsing:active_session']}` 
                    : 'Немає активних сесій'}
                </h3>
                <p className="text-sm text-gray-600">
                  Статус: <span className="font-medium">{diagnostic.redis?.['scraping:status'] || 'idle'}</span>
                  {diagnostic.redis?.['parsing:active_session_ttl'] && (
                    <span className="ml-2 text-gray-500">
                      (TTL: {Math.round(diagnostic.redis['parsing:active_session_ttl'] / 60)} хв)
                    </span>
                  )}
                </p>
              </div>
            </div>
            
            {diagnostic.redis?.['parsing:active_session'] && (
              <button
                onClick={handleClearStuckSession}
                disabled={clearingQueue}
                className="px-4 py-2 bg-yellow-600 text-white font-medium rounded-md hover:bg-yellow-700 disabled:bg-yellow-300 flex items-center gap-2"
              >
                {clearingQueue ? (
                  <>
                    <span className="animate-spin">⏳</span>
                    Очищення...
                  </>
                ) : (
                  <>
                    🧹 Очистити застряглу сесію
                  </>
                )}
              </button>
            )}
          </div>
          
          {/* Детальна інформація */}
          {diagnostic.redis?.['parsing:active_session'] && (
            <details className="mt-3">
              <summary className="text-sm text-gray-600 cursor-pointer hover:text-gray-800">
                Детальна діагностика...
              </summary>
              <div className="mt-2 grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                <div className="p-2 bg-gray-100 rounded">
                  <div className="text-gray-500">DB Status</div>
                  <div className="font-medium">{diagnostic.db?.status || 'N/A'}</div>
                </div>
                <div className="p-2 bg-gray-100 rounded">
                  <div className="text-gray-500">Processed</div>
                  <div className="font-medium">{diagnostic.db?.processed_domains || 0} / {diagnostic.db?.total_domains || 0}</div>
                </div>
                <div className="p-2 bg-gray-100 rounded">
                  <div className="text-gray-500">Celery Active</div>
                  <div className="font-medium">{diagnostic.celery?.active_tasks ?? 'N/A'}</div>
                </div>
                <div className="p-2 bg-gray-100 rounded">
                  <div className="text-gray-500">Queue Length</div>
                  <div className="font-medium">{diagnostic.celery?.queue_length ?? 'N/A'}</div>
                </div>
              </div>
              {diagnostic.recommendations?.length > 0 && (
                <div className="mt-2 p-2 bg-yellow-100 rounded text-sm text-yellow-800">
                  <strong>Рекомендації:</strong>
                  <ul className="list-disc list-inside mt-1">
                    {diagnostic.recommendations.map((rec, i) => (
                      <li key={i}>{rec}</li>
                    ))}
                  </ul>
                </div>
              )}
            </details>
          )}
        </div>
      )}

      {/* Додати задачу */}
      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-medium text-gray-900">Cron задачі</h2>
          <button
            onClick={() => setShowAddForm(!showAddForm)}
            className="px-4 py-2 bg-blue-600 text-white font-medium rounded-md hover:bg-blue-700"
          >
            {showAddForm ? 'Скасувати' : '+ Додати задачу'}
          </button>
        </div>

        {showAddForm && (
          <form onSubmit={handleAddJob} className="mb-6 p-4 border border-gray-200 rounded-md space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  ID задачі <span className="text-gray-400 font-normal">(необов'язково)</span>
                </label>
                <input
                  type="text"
                  value={newJob.job_id}
                  onChange={(e) => setNewJob({...newJob, job_id: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                  placeholder="full_scraping (автогенерація якщо пусто)"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Тип задачі
                </label>
                <select
                  value={newJob.job_type}
                  onChange={(e) => setNewJob({...newJob, job_type: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                >
                  <option value="full_scraping">Повний парсинг</option>
                  <option value="partial_scraping">Частковий парсинг</option>
                </select>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Розклад запуску
              </label>
              
              {/* Простий вибір часу */}
              <div className="mb-3">
                <select
                  onChange={(e) => e.target.value && setNewJob({...newJob, cron_expression: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md bg-white"
                  value={newJob.cron_expression}
                >
                  {cronExamples.map(ex => (
                    <option key={ex.value} value={ex.value}>{ex.label}</option>
                  ))}
                </select>
              </div>
              
              {/* Або ручний ввід */}
              <details className="text-sm">
                <summary className="cursor-pointer text-blue-600 hover:text-blue-800 mb-2">
                  Або ввести cron вираз вручну
                </summary>
                <div className="mt-2 p-3 bg-gray-50 rounded-md">
                  <input
                    type="text"
                    value={newJob.cron_expression}
                    onChange={(e) => setNewJob({...newJob, cron_expression: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md font-mono text-sm"
                    placeholder="хвилина година день місяць день_тижня"
                  />
                  <div className="mt-2 text-xs text-gray-500">
                    <p className="font-medium mb-1">Формат: хв год день міс день_тижня</p>
                    <ul className="list-disc list-inside space-y-0.5">
                      <li><code className="bg-gray-200 px-1">0 9 * * *</code> — щодня о 09:00</li>
                      <li><code className="bg-gray-200 px-1">0 9 * * 1</code> — понеділок о 09:00</li>
                      <li><code className="bg-gray-200 px-1">0 9,17 * * *</code> — о 09:00 та 17:00</li>
                      <li><code className="bg-gray-200 px-1">*/30 * * * *</code> — кожні 30 хв</li>
                    </ul>
                  </div>
                </div>
              </details>
              
              {/* Інформація про часовий пояс */}
              <div className="mt-2 p-2 bg-blue-50 border border-blue-200 rounded text-xs text-blue-700">
                ⏰ <strong>Часовий пояс: UTC</strong> (Київ = UTC+2 зимою, UTC+3 влітку)
                <br />
                Наприклад: 09:00 UTC = 11:00 за київським часом (зима)
              </div>
            </div>

            {newJob.job_type === 'partial_scraping' && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Розмір пачки доменів
                </label>
                <input
                  type="number"
                  value={newJob.batch_size}
                  onChange={(e) => setNewJob({...newJob, batch_size: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                  min="1"
                />
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Джерело доменів
              </label>
              
              {/* Радіо кнопки для вибору джерела */}
              <div className="space-y-2 mb-3">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name="domainSource"
                    checked={newJob.domainSource === 'uploaded'}
                    onChange={() => setNewJob({...newJob, domainSource: 'uploaded'})}
                    className="w-4 h-4 text-blue-600"
                  />
                  <span className="text-sm">
                    Використати завантажені домени 
                    <span className={`ml-2 px-2 py-0.5 rounded text-xs font-medium ${
                      uploadedDomainsCount > 0 
                        ? 'bg-green-100 text-green-700' 
                        : 'bg-gray-100 text-gray-500'
                    }`}>
                      {uploadedDomainsCount} доменів
                    </span>
                  </span>
                </label>
                
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name="domainSource"
                    checked={newJob.domainSource === 'api'}
                    onChange={() => setNewJob({...newJob, domainSource: 'api'})}
                    className="w-4 h-4 text-blue-600"
                  />
                  <span className="text-sm">
                    Завантажити з API
                    {apiDomains.length > 0 && (
                      <span className="ml-2 px-2 py-0.5 rounded text-xs font-medium bg-purple-100 text-purple-700">
                        {apiDomains.length} доменів
                      </span>
                    )}
                  </span>
                </label>
                
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name="domainSource"
                    checked={newJob.domainSource === 'manual'}
                    onChange={() => setNewJob({...newJob, domainSource: 'manual'})}
                    className="w-4 h-4 text-blue-600"
                  />
                  <span className="text-sm">Ввести вручну</span>
                </label>
              </div>

              {/* Поле для API URL */}
              {newJob.domainSource === 'api' && (
                <div className="mb-3 p-3 bg-purple-50 border border-purple-200 rounded-md">
                  <label className="block text-sm font-medium text-purple-700 mb-2">
                    URL API для отримання доменів
                  </label>
                  <div className="flex gap-2">
                    <input
                      type="url"
                      value={apiUrl}
                      onChange={(e) => setApiUrl(e.target.value)}
                      className="flex-1 px-3 py-2 border border-purple-300 rounded-md text-sm"
                      placeholder="https://example.com/api/shops?key=xxx"
                    />
                    <button
                      type="button"
                      onClick={fetchDomainsFromApi}
                      disabled={apiLoading}
                      className="px-4 py-2 bg-purple-600 text-white font-medium rounded-md hover:bg-purple-700 disabled:bg-purple-300"
                    >
                      {apiLoading ? '⏳' : '🔄 Завантажити'}
                    </button>
                  </div>
                  <p className="mt-2 text-xs text-purple-600">
                    Формат відповіді: {"{"}"data": [{"{"}"url": "https://shop.com/", ...{"}"}]{"}"}
                  </p>
                  {apiDomains.length > 0 && (
                    <div className="mt-2 p-2 bg-white rounded border border-purple-200">
                      <p className="text-sm text-green-700 font-medium">
                        ✓ Завантажено {apiDomains.length} доменів
                      </p>
                      <details className="mt-1">
                        <summary className="text-xs text-purple-600 cursor-pointer hover:text-purple-800">
                          Переглянути перші 10 доменів...
                        </summary>
                        <div className="mt-1 text-xs text-gray-600 font-mono max-h-32 overflow-y-auto">
                          {apiDomains.slice(0, 10).map((d, i) => (
                            <div key={i}>{d}</div>
                          ))}
                          {apiDomains.length > 10 && <div>... та ще {apiDomains.length - 10}</div>}
                        </div>
                      </details>
                    </div>
                  )}
                </div>
              )}

              {/* Текстове поле для ручного вводу */}
              {newJob.domainSource === 'manual' && (
                <textarea
                  value={newJob.domains}
                  onChange={(e) => setNewJob({...newJob, domains: e.target.value})}
                  rows={4}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md font-mono text-sm"
                  placeholder="example.com&#10;test.com&#10;demo.com"
                />
              )}
              
              {newJob.domainSource === 'uploaded' && uploadedDomainsCount === 0 && (
                <div className="p-3 bg-yellow-50 border border-yellow-200 rounded-md text-sm text-yellow-700">
                  ⚠️ Немає завантажених доменів. Перейдіть у <strong>Configuration</strong> та завантажте JSON файл з доменами.
                </div>
              )}
              
              {newJob.domainSource === 'api' && apiDomains.length === 0 && apiUrl && (
                <div className="p-3 bg-yellow-50 border border-yellow-200 rounded-md text-sm text-yellow-700">
                  ⚠️ Введіть URL та натисніть "Завантажити" для отримання доменів.
                </div>
              )}
            </div>

            <button
              type="submit"
              className="w-full px-4 py-2 bg-blue-600 text-white font-medium rounded-md hover:bg-blue-700"
            >
              Додати задачу
            </button>
          </form>
        )}

        {/* Список задач */}
        {jobs.length === 0 ? (
          <div className="text-center py-12 text-gray-500">
            <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <p className="mt-2">Немає активних задач</p>
          </div>
        ) : (
          <div className="space-y-3">
            {jobs.map(job => (
              <div key={job.id} className="border border-gray-200 rounded-md p-4 hover:bg-gray-50">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <h3 className="font-medium text-gray-900">{job.id}</h3>
                      <span className={`px-2 py-1 text-xs font-medium rounded-full ${
                        job.pending ? 'bg-gray-100 text-gray-800' : 'bg-green-100 text-green-800'
                      }`}>
                        {job.pending ? 'Призупинено' : 'Активна'}
                      </span>
                    </div>
                    <div className="text-sm text-gray-600 space-y-1">
                      <p><span className="font-medium">Trigger:</span> {job.trigger}</p>
                      <p><span className="font-medium">Наступний запуск:</span> {job.next_run_time ? new Date(job.next_run_time).toLocaleString() : 'N/A'}</p>
                      <p className="text-xs text-gray-500 font-mono">{job.func}</p>
                    </div>
                  </div>
                  <div className="flex gap-2 ml-4">
                    <button
                      onClick={() => handlePauseResume(job.id, job.pending)}
                      className="p-2 text-blue-600 hover:bg-blue-50 rounded"
                      title={job.pending ? 'Відновити' : 'Призупинити'}
                    >
                      {job.pending ? '▶️' : '⏸'}
                    </button>
                    <button
                      onClick={() => handleRemoveJob(job.id)}
                      className="p-2 text-red-600 hover:bg-red-50 rounded"
                      title="Видалити"
                    >
                      🗑️
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
