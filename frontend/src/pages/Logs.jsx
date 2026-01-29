import { useState, useEffect, useRef } from 'react';
import { logsAPI } from '../api/client';

export default function Logs() {
  const [logs, setLogs] = useState([]);
  const [filter, setFilter] = useState('all');
  const [autoScroll, setAutoScroll] = useState(true);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState(null);
  const [lastTimestamp, setLastTimestamp] = useState(null);
  const logsEndRef = useRef(null);

  useEffect(() => {
    fetchLogs();
    fetchStats();
    
    // Оновлюємо логи кожні 3 секунди
    const interval = setInterval(() => {
      fetchLogs();
      fetchStats();
    }, 3000);

    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (autoScroll) {
      logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, autoScroll]);

  const fetchLogs = async () => {
    try {
      const response = await logsAPI.get({ limit: 200 });
      if (response.data.success) {
        // Логи приходять від нових до старих, перевертаємо для відображення
        const newLogs = (response.data.logs || []).reverse();
        setLogs(newLogs);
        
        if (newLogs.length > 0) {
          setLastTimestamp(newLogs[newLogs.length - 1].timestamp);
        }
      }
      setLoading(false);
    } catch (err) {
      console.error('Error fetching logs:', err);
      setLoading(false);
    }
  };

  const fetchStats = async () => {
    try {
      const response = await logsAPI.stats();
      if (response.data.success) {
        setStats(response.data);
      }
    } catch (err) {
      console.error('Error fetching stats:', err);
    }
  };

  const filteredLogs = filter === 'all' 
    ? logs 
    : logs.filter(log => log.level === filter);

  const getLevelColor = (level) => {
    switch (level) {
      case 'ERROR': return 'text-red-600 bg-red-50';
      case 'WARNING': return 'text-yellow-600 bg-yellow-50';
      case 'INFO': return 'text-blue-600 bg-blue-50';
      case 'DEBUG': return 'text-gray-600 bg-gray-50';
      default: return 'text-gray-600 bg-gray-50';
    }
  };

  const getLevelIcon = (level) => {
    switch (level) {
      case 'ERROR': return '❌';
      case 'WARNING': return '⚠️';
      case 'INFO': return 'ℹ️';
      case 'DEBUG': return '🔧';
      default: return '📝';
    }
  };

  const clearLogs = async () => {
    if (!confirm('Очистити всі логи?')) return;
    
    try {
      await logsAPI.clear();
      setLogs([]);
      fetchStats();
    } catch (err) {
      console.error('Error clearing logs:', err);
      alert('Помилка очищення логів');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold text-gray-900">Логи</h1>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-sm text-gray-700">
            <input
              type="checkbox"
              checked={autoScroll}
              onChange={(e) => setAutoScroll(e.target.checked)}
              className="rounded border-gray-300"
            />
            Auto-scroll
          </label>
          <button
            onClick={fetchLogs}
            className="px-4 py-2 bg-blue-600 text-white font-medium rounded-md hover:bg-blue-700"
          >
            🔄 Оновити
          </button>
          <button
            onClick={clearLogs}
            className="px-4 py-2 bg-red-600 text-white font-medium rounded-md hover:bg-red-700"
          >
            Очистити логи
          </button>
        </div>
      </div>

      {/* Статистика */}
      {stats && (
        <div className="grid grid-cols-5 gap-4">
          <div className="bg-white p-4 rounded-lg shadow text-center">
            <div className="text-2xl font-bold text-gray-900">{stats.total || 0}</div>
            <div className="text-sm text-gray-500">Всього</div>
          </div>
          <div className="bg-blue-50 p-4 rounded-lg shadow text-center">
            <div className="text-2xl font-bold text-blue-600">{stats.by_level?.INFO || 0}</div>
            <div className="text-sm text-gray-500">INFO</div>
          </div>
          <div className="bg-yellow-50 p-4 rounded-lg shadow text-center">
            <div className="text-2xl font-bold text-yellow-600">{stats.by_level?.WARNING || 0}</div>
            <div className="text-sm text-gray-500">WARNING</div>
          </div>
          <div className="bg-red-50 p-4 rounded-lg shadow text-center">
            <div className="text-2xl font-bold text-red-600">{stats.by_level?.ERROR || 0}</div>
            <div className="text-sm text-gray-500">ERROR</div>
          </div>
          <div className="bg-gray-50 p-4 rounded-lg shadow text-center">
            <div className="text-2xl font-bold text-gray-600">{stats.by_level?.DEBUG || 0}</div>
            <div className="text-sm text-gray-500">DEBUG</div>
          </div>
        </div>
      )}

      {/* Фільтри */}
      <div className="bg-white p-4 rounded-lg shadow flex items-center gap-4">
        <span className="text-sm font-medium text-gray-700">Рівень:</span>
        {['all', 'INFO', 'WARNING', 'ERROR', 'DEBUG'].map(level => (
          <button
            key={level}
            onClick={() => setFilter(level)}
            className={`px-3 py-1 text-sm font-medium rounded-md transition-colors ${
              filter === level
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            {level === 'all' ? 'Всі' : level}
          </button>
        ))}
        <span className="ml-auto text-sm text-gray-500">
          Показано: {filteredLogs.length} записів
        </span>
      </div>

      {/* Логи */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200 bg-gray-50">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-medium text-gray-900">Real-time логи парсингу</h2>
            <div className="flex items-center gap-2">
              <div className="h-2 w-2 rounded-full bg-green-500 animate-pulse"></div>
              <span className="text-sm text-gray-600">Оновлюється кожні 3 сек</span>
            </div>
          </div>
        </div>

        <div className="max-h-[600px] overflow-y-auto">
          {filteredLogs.length === 0 ? (
            <div className="text-center py-12 text-gray-500">
              <svg className="mx-auto h-12 w-12 text-gray-400 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <p className="font-medium">Немає логів для відображення</p>
              <p className="text-sm mt-1">Логи з'являться при запуску парсингу</p>
            </div>
          ) : (
            <div className="divide-y divide-gray-200">
              {filteredLogs.map(log => (
                <div key={log.id} className="px-6 py-3 hover:bg-gray-50 transition-colors">
                  <div className="flex items-start gap-3">
                    <span className="text-lg">{getLevelIcon(log.level)}</span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1 flex-wrap">
                        <span className={`px-2 py-0.5 text-xs font-medium rounded ${getLevelColor(log.level)}`}>
                          {log.level}
                        </span>
                        {log.domain && (
                          <span className="px-2 py-0.5 text-xs font-medium rounded bg-purple-100 text-purple-700">
                            {log.domain}
                          </span>
                        )}
                        <span className="text-xs text-gray-500">
                          {new Date(log.timestamp).toLocaleString()}
                        </span>
                      </div>
                      <p className="text-sm text-gray-900 break-words">
                        {log.message}
                      </p>
                      {log.extra && Object.keys(log.extra).length > 0 && (
                        <div className="mt-1 text-xs text-gray-500 font-mono">
                          {JSON.stringify(log.extra)}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
              <div ref={logsEndRef} />
            </div>
          )}
        </div>
      </div>

      {/* Інформація */}
      <div className="bg-blue-50 border border-blue-200 rounded-md p-4">
        <div className="flex">
          <div className="flex-shrink-0">
            <svg className="h-5 w-5 text-blue-400" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
            </svg>
          </div>
          <div className="ml-3">
            <h3 className="text-sm font-medium text-blue-800">
              Про логи
            </h3>
            <div className="mt-2 text-sm text-blue-700">
              <p>
                Логи оновлюються автоматично кожні 3 секунди. 
                Зберігаються останні 500 записів. Логи показують реальний прогрес парсингу: 
                завантаження HTML, аналіз через Gemini AI, відправка в webhook.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
