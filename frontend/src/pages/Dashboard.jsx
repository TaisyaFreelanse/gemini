import { useState, useEffect } from 'react';
import { parsingAPI } from '../api/client';

export default function Dashboard() {
  const [status, setStatus] = useState(null);
  const [progress, setProgress] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 5000); // Оновлення кожні 5 секунд
    return () => clearInterval(interval);
  }, []);

  const fetchStatus = async () => {
    try {
      const response = await parsingAPI.status();
      setStatus(response.data);
      
      if (response.data.session_id) {
        const progressResponse = await parsingAPI.progress(response.data.session_id);
        setProgress(progressResponse.data);
      }
      
      setLoading(false);
    } catch (err) {
      setError(err.message);
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
        <p className="font-bold">Помилка завантаження</p>
        <p>{error}</p>
      </div>
    );
  }

  const progressPercent = progress 
    ? Math.round((progress.processed / progress.total) * 100) 
    : 0;

  const domainsPerHour = progress && progress.processed > 0
    ? Math.round((progress.processed / ((Date.now() - new Date(progress.started_at)) / 3600000)))
    : 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>
        <div className="flex items-center gap-2">
          <div className={`h-3 w-3 rounded-full ${
            status?.is_running ? 'bg-green-500 animate-pulse' : 'bg-gray-400'
          }`}></div>
          <span className="text-sm font-medium text-gray-700">
            {status?.is_running ? 'Активний' : 'Зупинено'}
          </span>
        </div>
      </div>

      {/* Статус карти */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white p-6 rounded-lg shadow">
          <div className="text-sm font-medium text-gray-500 mb-1">Оброблено доменів</div>
          <div className="text-3xl font-bold text-gray-900">
            {progress?.processed || 0} / {progress?.total || 0}
          </div>
        </div>

        <div className="bg-white p-6 rounded-lg shadow">
          <div className="text-sm font-medium text-gray-500 mb-1">Швидкість обробки</div>
          <div className="text-3xl font-bold text-gray-900">
            {domainsPerHour} <span className="text-lg text-gray-500">domains/hour</span>
          </div>
        </div>

        <div className="bg-white p-6 rounded-lg shadow">
          <div className="text-sm font-medium text-gray-500 mb-1">Успішних / Помилок</div>
          <div className="text-3xl font-bold">
            <span className="text-green-600">{progress?.successful || 0}</span>
            <span className="text-gray-400 mx-2">/</span>
            <span className="text-red-600">{progress?.failed || 0}</span>
          </div>
        </div>
      </div>

      {/* Прогрес бар */}
      {progress && (
        <div className="bg-white p-6 rounded-lg shadow">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-lg font-medium text-gray-900">Прогрес парсингу</h3>
            <span className="text-sm font-medium text-gray-700">{progressPercent}%</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-4">
            <div
              className="bg-blue-600 h-4 rounded-full transition-all duration-500"
              style={{ width: `${progressPercent}%` }}
            ></div>
          </div>
          <div className="mt-2 flex items-center justify-between text-sm text-gray-600">
            <span>Запущено: {new Date(progress.started_at).toLocaleString()}</span>
            <span>В процесі: {progress.running || 0}</span>
          </div>
        </div>
      )}

      {/* Останні домени */}
      {progress?.domains && (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-200">
            <h3 className="text-lg font-medium text-gray-900">Останні домени</h3>
          </div>
          <div className="divide-y divide-gray-200">
            {Object.entries(progress.domains).slice(-10).reverse().map(([domain, status]) => (
              <div key={domain} className="px-6 py-3 flex items-center justify-between hover:bg-gray-50">
                <span className="text-sm font-mono text-gray-700">{domain}</span>
                <span className={`px-2 py-1 text-xs font-medium rounded-full ${
                  status === 'completed' ? 'bg-green-100 text-green-800' :
                  status === 'failed' ? 'bg-red-100 text-red-800' :
                  status === 'running' ? 'bg-blue-100 text-blue-800' :
                  'bg-gray-100 text-gray-800'
                }`}>
                  {status}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Порожній стан */}
      {!progress && (
        <div className="bg-white rounded-lg shadow p-12 text-center">
          <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <h3 className="mt-2 text-sm font-medium text-gray-900">Немає активного парсингу</h3>
          <p className="mt-1 text-sm text-gray-500">Почніть новий парсинг або налаштуйте scheduler</p>
        </div>
      )}
    </div>
  );
}
