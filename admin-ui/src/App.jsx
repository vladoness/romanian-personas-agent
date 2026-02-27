import { BrowserRouter as Router, Routes, Route, Link, Navigate } from 'react-router-dom';
import { useState, useEffect } from 'react';
import api from './services/api';
import Dashboard from './pages/Dashboard';
import CreatePersona from './pages/CreatePersona';
import PersonaDetail from './pages/PersonaDetail';
import './App.css';

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [password, setPassword] = useState('');
  const [showLogin, setShowLogin] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    // Check if already authenticated
    if (api.isAuthenticated()) {
      setIsAuthenticated(true);
    } else {
      setShowLogin(true);
    }
  }, []);

  const handleLogin = async (e) => {
    e.preventDefault();
    setError('');

    // Store password and test it
    api.setPassword(password);

    try {
      // Try to fetch personas to verify credentials
      await api.getPersonas();
      setIsAuthenticated(true);
      setShowLogin(false);
    } catch (err) {
      setError('Invalid password');
      api.clearPassword();
    }
  };

  const handleLogout = () => {
    api.clearPassword();
    setIsAuthenticated(false);
    setShowLogin(true);
  };

  if (showLogin) {
    return (
      <div className="login-container">
        <div className="login-box">
          <h1>Persona Admin</h1>
          <form onSubmit={handleLogin}>
            <div className="form-group">
              <label>Admin Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter admin password"
                autoFocus
              />
            </div>
            {error && <div className="error-message">{error}</div>}
            <button type="submit" className="btn btn-primary">
              Login
            </button>
          </form>
        </div>
      </div>
    );
  }

  return (
    <Router>
      <div className="app">
        <nav className="navbar">
          <div className="nav-content">
            <Link to="/" className="nav-brand">
              Persona Admin
            </Link>
            <div className="nav-links">
              <Link to="/" className="nav-link">Dashboard</Link>
              <Link to="/create" className="nav-link">Create Persona</Link>
              <button onClick={handleLogout} className="btn btn-secondary">
                Logout
              </button>
            </div>
          </div>
        </nav>

        <main className="main-content">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/create" element={<CreatePersona />} />
            <Route path="/persona/:personaId" element={<PersonaDetail />} />
            <Route path="*" element={<Navigate to="/" />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;
