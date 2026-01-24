import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import Configuration from './pages/Configuration'
import Scheduler from './pages/Scheduler'
import Reports from './pages/Reports'
import Logs from './pages/Logs'

function App() {
  return (
    <Router>
      <div className="min-h-screen bg-gray-100">
        <Navbar />
        <main>
          <div className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/configuration" element={<Configuration />} />
              <Route path="/scheduler" element={<Scheduler />} />
              <Route path="/reports" element={<Reports />} />
              <Route path="/logs" element={<Logs />} />
            </Routes>
          </div>
        </main>
      </div>
    </Router>
  )
}

function Navbar() {
  const location = useLocation();
  
  const navItems = [
    { path: '/', label: 'Dashboard', icon: '📊' },
    { path: '/configuration', label: 'Configuration', icon: '⚙️' },
    { path: '/scheduler', label: 'Scheduler', icon: '⏰' },
    { path: '/reports', label: 'Reports', icon: '📈' },
    { path: '/logs', label: 'Logs', icon: '📝' },
  ];

  return (
    <nav className="bg-white shadow-lg">
      <div className="max-w-7xl mx-auto px-4">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center">
            <h1 className="text-xl font-bold text-gray-900">
              🤖 Web Scraper Gemini
            </h1>
          </div>
          <div className="flex space-x-1">
            {navItems.map(item => (
              <Link
                key={item.path}
                to={item.path}
                className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                  location.pathname === item.path
                    ? 'bg-blue-600 text-white'
                    : 'text-gray-700 hover:bg-gray-100'
                }`}
              >
                <span className="mr-1">{item.icon}</span>
                {item.label}
              </Link>
            ))}
          </div>
        </div>
      </div>
    </nav>
  );
}

export default App
