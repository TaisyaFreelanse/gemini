import { useState, useEffect } from 'react';
import { configAPI } from '../api/client';

export default function Configuration() {
  const [config, setConfig] = useState({
    domains_api_url: '',
    gemini_api_key: '',
    webhook_url: '',
    webhook_token: '',
    proxy_host: '',
    proxy_http_port: 59100,
    proxy_socks_port: 59101,
    proxy_login: '',
    proxy_password: '',
    gemini_prompt: '',
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(null);

  useEffect(() => {
    fetchConfig();
  }, []);

  const fetchConfig = async () => {
    try {
      const response = await configAPI.get();
      setConfig(response.data);
      setLoading(false);
    } catch (err) {
      console.error('Error fetching config:', err);
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setMessage(null);

    try {
      await configAPI.update(config);
      setMessage({ type: 'success', text: 'Конфігурація успішно збережена!' });
    } catch (err) {
      setMessage({ type: 'error', text: `Помилка: ${err.message}` });
    } finally {
      setSaving(false);
    }
  };

  const handleReset = async () => {
    if (!confirm('Ви впевнені? Це скине всі налаштування до дефолтних значень.')) {
      return;
    }

    try {
      await configAPI.reset();
      fetchConfig();
      setMessage({ type: 'success', text: 'Конфігурацію скинуто до дефолтних значень' });
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

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-3xl font-bold text-gray-900">Конфігурація</h1>
        <button
          onClick={handleReset}
          className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
        >
          Скинути до дефолту
        </button>
      </div>

      {message && (
        <div className={`mb-6 px-4 py-3 rounded-md ${
          message.type === 'success' 
            ? 'bg-green-50 border border-green-200 text-green-700' 
            : 'bg-red-50 border border-red-200 text-red-700'
        }`}>
          {message.text}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* API Settings */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-medium text-gray-900 mb-4">API налаштування</h2>
          
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                API URL для отримання доменів
              </label>
              <input
                type="url"
                value={config.domains_api_url}
                onChange={(e) => setConfig({...config, domains_api_url: e.target.value})}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="https://api.example.com/domains"
              />
            </div>
          </div>
        </div>

        {/* Gemini AI */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-medium text-gray-900 mb-4">Gemini AI</h2>
          
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Gemini API Key *
              </label>
              <input
                type="password"
                value={config.gemini_api_key}
                onChange={(e) => setConfig({...config, gemini_api_key: e.target.value})}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="AIzaSy..."
                required
              />
              <p className="mt-1 text-xs text-gray-500">
                Отримати можна на <a href="https://makersuite.google.com/app/apikey" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">Google AI Studio</a>
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Промпт для Gemini (опціонально)
              </label>
              <textarea
                value={config.gemini_prompt}
                onChange={(e) => setConfig({...config, gemini_prompt: e.target.value})}
                rows={6}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-sm"
                placeholder="Залиште порожнім для використання дефолтного промпту"
              />
            </div>
          </div>
        </div>

        {/* Webhook */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-medium text-gray-900 mb-4">Webhook</h2>
          
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Webhook URL
              </label>
              <input
                type="url"
                value={config.webhook_url}
                onChange={(e) => setConfig({...config, webhook_url: e.target.value})}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="https://api.example.com/webhook"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Bearer Token
              </label>
              <input
                type="password"
                value={config.webhook_token}
                onChange={(e) => setConfig({...config, webhook_token: e.target.value})}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="your-secret-token"
              />
            </div>
          </div>
        </div>

        {/* Proxy */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-medium text-gray-900 mb-4">Proxy налаштування</h2>
          
          <div className="grid grid-cols-2 gap-4">
            <div className="col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Proxy Host
              </label>
              <input
                type="text"
                value={config.proxy_host}
                onChange={(e) => setConfig({...config, proxy_host: e.target.value})}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="proxy.example.com"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                HTTP Port
              </label>
              <input
                type="number"
                value={config.proxy_http_port}
                onChange={(e) => setConfig({...config, proxy_http_port: parseInt(e.target.value)})}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                SOCKS5 Port
              </label>
              <input
                type="number"
                value={config.proxy_socks_port}
                onChange={(e) => setConfig({...config, proxy_socks_port: parseInt(e.target.value)})}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Login
              </label>
              <input
                type="text"
                value={config.proxy_login}
                onChange={(e) => setConfig({...config, proxy_login: e.target.value})}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Password
              </label>
              <input
                type="password"
                value={config.proxy_password}
                onChange={(e) => setConfig({...config, proxy_password: e.target.value})}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>
        </div>

        {/* Submit */}
        <div className="flex justify-end">
          <button
            type="submit"
            disabled={saving}
            className="px-6 py-3 bg-blue-600 text-white font-medium rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {saving ? 'Збереження...' : 'Зберегти конфігурацію'}
          </button>
        </div>
      </form>
    </div>
  );
}
