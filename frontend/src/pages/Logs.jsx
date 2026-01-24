import { useState, useEffect, useRef } from 'react';

export default function Logs() {
  const [logs, setLogs] = useState([
    // Mock logs для демонстрації
    { id: 1, level: 'INFO', message: 'Scheduler запущено', timestamp: new Date().toISOString() },
    { id: 2, level: 'INFO', message: 'Початок парсингу example.com', timestamp: new Date().toISOString() },
    { id: 3, level: 'ERROR', message: 'Помилка підключення до proxy', timestamp: new Date().toISOString() },
    { id: 4, level: 'INFO', message: 'Знайдено 5 угод на test.com', timestamp: new Date().toISOString() },
    { id: 5, level: 'DEBUG', message: 'Gemini API response: 200 OK', timestamp: new Date().toISOString() },
  ]);
  const [filter, setFilter] = useState('all');
  const [autoScroll, setAutoScroll] = useState(true);
  const logsEndRef = useRef(null);

  useEffect(() => {
    if (autoScroll) {
      logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, autoScroll]);

  // Mock: Додавання нових логів (замість WebSocket)
  useEffect(() => {
    const interval = setInterval(() => {
      const mockLevels = ['INFO', 'ERROR', 'DEBUG', 'WARNING'];
      const mockMessages = [
        'Парсинг домену завершено',
        'Угода відправлена в webhook',
        'Redis connection established',
        'Celery worker ready',
        'Gemini API quota warning',
        'Proxy rotated successfully',
      ];
      
      const newLog = {
        id: Date.now(),
        level: mockLevels[Math.floor(Math.random() * mockLevels.length)],
        message: mockMessages[Math.floor(Math.random() * mockMessages.length)],
        timestamp: new Date().toISOString(),
      };
      
      setLogs(prev => [...prev.slice(-99), newLog]); // Зберігаємо останні 100 логів
    }, 5000); // Новий лог кожні 5 секунд

    return () => clearInterval(interval);
  }, []);

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

  const clearLogs = () => {
    if (confirm('Очистити всі логи?')) {
      setLogs([]);
    }
  };

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
            onClick={clearLogs}
            className="px-4 py-2 bg-red-600 text-white font-medium rounded-md hover:bg-red-700"
          >
            Очистити логи
          </button>
        </div>
      </div>

      {/* Фільтри */}
      <div className="bg-white p-4 rounded-lg shadow flex items-center gap-4">
        <span className="text-sm font-medium text-gray-700">Рівень:</span>
        {['all', 'INFO', 'ERROR', 'WARNING', 'DEBUG'].map(level => (
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
          Всього: {filteredLogs.length} записів
        </span>
      </div>

      {/* Логи */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200 bg-gray-50">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-medium text-gray-900">Real-time логи</h2>
            <div className="flex items-center gap-2">
              <div className="h-2 w-2 rounded-full bg-green-500 animate-pulse"></div>
              <span className="text-sm text-gray-600">Підключено</span>
            </div>
          </div>
        </div>

        <div className="max-h-[600px] overflow-y-auto">
          {filteredLogs.length === 0 ? (
            <div className="text-center py-12 text-gray-500">
              <p>Немає логів для відображення</p>
            </div>
          ) : (
            <div className="divide-y divide-gray-200">
              {filteredLogs.map(log => (
                <div key={log.id} className="px-6 py-3 hover:bg-gray-50 transition-colors">
                  <div className="flex items-start gap-3">
                    <span className="text-lg">{getLevelIcon(log.level)}</span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className={`px-2 py-0.5 text-xs font-medium rounded ${getLevelColor(log.level)}`}>
                          {log.level}
                        </span>
                        <span className="text-xs text-gray-500">
                          {new Date(log.timestamp).toLocaleString()}
                        </span>
                      </div>
                      <p className="text-sm text-gray-900 font-mono break-words">
                        {log.message}
                      </p>
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
                Логи оновлюються автоматично в режимі реального часу. 
                Зберігається останні 100 записів. Для повної історії використовуйте файлові логи на сервері.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
