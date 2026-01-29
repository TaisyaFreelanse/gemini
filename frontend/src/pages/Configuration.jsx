import { useState, useEffect, useRef } from 'react';
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
  
  // Domains state
  const [domains, setDomains] = useState([]);
  const [domainsCount, setDomainsCount] = useState(0);
  const [uploadingDomains, setUploadingDomains] = useState(false);
  const [domainsMessage, setDomainsMessage] = useState(null);
  const fileInputRef = useRef(null);

  useEffect(() => {
    fetchConfig();
    fetchDomains();
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

  const fetchDomains = async () => {
    try {
      const response = await configAPI.getDomains();
      setDomains(response.data.domains || []);
      setDomainsCount(response.data.count || 0);
    } catch (err) {
      console.error('Error fetching domains:', err);
    }
  };

  const handleFileUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    setUploadingDomains(true);
    setDomainsMessage(null);

    try {
      const text = await file.text();
      const data = JSON.parse(text);
      
      const response = await configAPI.uploadDomains(data);
      
      setDomainsMessage({ 
        type: 'success', 
        text: response.data.message || `Завантажено ${response.data.count} доменів`
      });
      
      // Оновлюємо список
      await fetchDomains();
      
    } catch (err) {
      console.error('Upload error:', err);
      let errorText = 'Помилка завантаження файлу';
      if (err.response?.data?.detail) {
        errorText = err.response.data.detail;
      } else if (err.message.includes('JSON')) {
        errorText = 'Невірний формат JSON файлу';
      }
      setDomainsMessage({ type: 'error', text: errorText });
    } finally {
      setUploadingDomains(false);
      // Очищаємо input щоб можна було завантажити той самий файл знову
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const handleClearDomains = async () => {
    if (!confirm('Ви впевнені? Це видалить всі завантажені домени.')) {
      return;
    }

    try {
      await configAPI.clearDomains();
      setDomains([]);
      setDomainsCount(0);
      setDomainsMessage({ type: 'success', text: 'Список доменів очищено' });
    } catch (err) {
      setDomainsMessage({ type: 'error', text: 'Помилка очищення' });
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

      {/* Domains Upload Section - Outside form */}
      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <h2 className="text-lg font-medium text-gray-900 mb-4">📋 Список доменів для парсингу</h2>
        
        {domainsMessage && (
          <div className={`mb-4 px-4 py-3 rounded-md ${
            domainsMessage.type === 'success' 
              ? 'bg-green-50 border border-green-200 text-green-700' 
              : 'bg-red-50 border border-red-200 text-red-700'
          }`}>
            {domainsMessage.text}
          </div>
        )}
        
        <div className="space-y-4">
          {/* Статистика */}
          <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
            <div>
              <span className="text-2xl font-bold text-blue-600">{domainsCount}</span>
              <span className="text-gray-600 ml-2">доменів завантажено</span>
            </div>
            <div className="flex gap-2">
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleFileUpload}
                accept=".json"
                className="hidden"
              />
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={uploadingDomains}
                className="px-4 py-2 bg-blue-600 text-white font-medium rounded-md hover:bg-blue-700 disabled:opacity-50"
              >
                {uploadingDomains ? '⏳ Завантаження...' : '📤 Завантажити JSON'}
              </button>
              {domainsCount > 0 && (
                <button
                  type="button"
                  onClick={handleClearDomains}
                  className="px-4 py-2 bg-red-600 text-white font-medium rounded-md hover:bg-red-700"
                >
                  🗑️ Очистити
                </button>
              )}
            </div>
          </div>
          
          {/* Формат */}
          <div className="text-sm text-gray-500">
            <p className="font-medium mb-1">Підтримувані формати JSON:</p>
            <code className="block bg-gray-100 p-2 rounded text-xs">
              {'{"status": true, "data": ["domain1.com", "domain2.com", ...]}'}
            </code>
            <code className="block bg-gray-100 p-2 rounded text-xs mt-1">
              {'{"domains": ["domain1.com", "domain2.com", ...]}'}
            </code>
          </div>
          
          {/* Список доменів */}
          {domains.length > 0 && (
            <div>
              <p className="text-sm font-medium text-gray-700 mb-2">
                Перші {Math.min(domains.length, 20)} доменів:
              </p>
              <div className="max-h-48 overflow-y-auto bg-gray-50 rounded-lg p-3">
                <div className="flex flex-wrap gap-2">
                  {domains.slice(0, 20).map((domain, idx) => (
                    <span 
                      key={idx}
                      className="px-2 py-1 bg-white border border-gray-200 rounded text-sm text-gray-700"
                    >
                      {domain}
                    </span>
                  ))}
                  {domains.length > 20 && (
                    <span className="px-2 py-1 bg-gray-200 rounded text-sm text-gray-600">
                      +{domains.length - 20} ще...
                    </span>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* API Settings */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-medium text-gray-900 mb-4">API налаштування</h2>
          
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                API URL для отримання доменів (альтернатива)
              </label>
              <input
                type="url"
                value={config.domains_api_url}
                onChange={(e) => setConfig({...config, domains_api_url: e.target.value})}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="https://api.example.com/domains"
              />
              <p className="mt-1 text-xs text-gray-500">
                Якщо не завантажили JSON файл, домени можуть бути отримані з цього API
              </p>
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
