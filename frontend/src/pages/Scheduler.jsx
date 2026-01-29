import { useState, useEffect } from 'react';
import { schedulerAPI, configAPI } from '../api/client';

export default function Scheduler() {
  const [status, setStatus] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAddForm, setShowAddForm] = useState(false);
  const [newJob, setNewJob] = useState({
    job_id: '',
    cron_expression: '* * * * *',  // кожну хвилину — для тесту
    job_type: 'full_scraping',
    domains: '',
    batch_size: 500,
    useUploadedDomains: true,  // за замовчуванням використовувати завантажені домени
  });
  const [message, setMessage] = useState(null);
  const [uploadedDomainsCount, setUploadedDomainsCount] = useState(0);

  useEffect(() => {
    fetchStatus();
    fetchUploadedDomains();
    const interval = setInterval(fetchStatus, 10000);
    return () => clearInterval(interval);
  }, []);

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

  const handleAddJob = async (e) => {
    e.preventDefault();
    
    try {
      let domains = [];
      
      if (newJob.useUploadedDomains) {
        // Отримуємо завантажені домени
        const response = await configAPI.getDomains();
        domains = response.data.domains || [];
        if (domains.length === 0) {
          setMessage({ type: 'error', text: 'Немає завантажених доменів. Завантажте JSON файл у Configuration.' });
          return;
        }
      } else {
        // Парсимо введені вручну
        domains = newJob.domains.split('\n').map(d => d.trim()).filter(Boolean);
        if (domains.length === 0) {
          setMessage({ type: 'error', text: 'Введіть хоча б один домен' });
          return;
        }
      }
      
      await schedulerAPI.addJob({
        job_id: newJob.job_id,
        cron_expression: newJob.cron_expression,
        job_type: newJob.job_type,
        domains,
        batch_size: parseInt(newJob.batch_size),
      });
      
      setMessage({ type: 'success', text: `Задачу успішно додано (${domains.length} доменів)` });
      setShowAddForm(false);
      setNewJob({
        job_id: '',
        cron_expression: '* * * * *',
        job_type: 'full_scraping',
        domains: '',
        batch_size: 500,
        useUploadedDomains: true,
      });
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
    { label: 'Кожну хвилину (тест)', value: '* * * * *' },
    { label: 'Кожні 5 хвилин', value: '*/5 * * * *' },
    { label: 'Кожні 30 хвилин', value: '*/30 * * * *' },
    { label: 'Кожні 6 годин', value: '0 */6 * * *' },
    { label: 'Кожні 2 години', value: '0 */2 * * *' },
    { label: 'Щодня о 00:00', value: '0 0 * * *' },
    { label: 'Понеділок о 9:00', value: '0 9 * * 1' },
  ];

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
                  ID задачі
                </label>
                <input
                  type="text"
                  value={newJob.job_id}
                  onChange={(e) => setNewJob({...newJob, job_id: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                  placeholder="my_job"
                  required
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
                Cron вираз
              </label>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={newJob.cron_expression}
                  onChange={(e) => setNewJob({...newJob, cron_expression: e.target.value})}
                  className="flex-1 px-3 py-2 border border-gray-300 rounded-md font-mono"
                  placeholder="* * * * * (5 полів: хв год день міс тижд)"
                  required
                />
                <select
                  onChange={(e) => setNewJob({...newJob, cron_expression: e.target.value})}
                  className="px-3 py-2 border border-gray-300 rounded-md"
                >
                  <option value="">Приклади...</option>
                  {cronExamples.map(ex => (
                    <option key={ex.value} value={ex.value}>{ex.label}</option>
                  ))}
                </select>
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
                    checked={newJob.useUploadedDomains}
                    onChange={() => setNewJob({...newJob, useUploadedDomains: true})}
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
                    checked={!newJob.useUploadedDomains}
                    onChange={() => setNewJob({...newJob, useUploadedDomains: false})}
                    className="w-4 h-4 text-blue-600"
                  />
                  <span className="text-sm">Ввести вручну</span>
                </label>
              </div>

              {/* Текстове поле для ручного вводу */}
              {!newJob.useUploadedDomains && (
                <textarea
                  value={newJob.domains}
                  onChange={(e) => setNewJob({...newJob, domains: e.target.value})}
                  rows={4}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md font-mono text-sm"
                  placeholder="example.com&#10;test.com&#10;demo.com"
                />
              )}
              
              {newJob.useUploadedDomains && uploadedDomainsCount === 0 && (
                <div className="p-3 bg-yellow-50 border border-yellow-200 rounded-md text-sm text-yellow-700">
                  ⚠️ Немає завантажених доменів. Перейдіть у <strong>Configuration</strong> та завантажте JSON файл з доменами.
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
