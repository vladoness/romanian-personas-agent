import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import api from '../services/api';
import './Dashboard.css';

function Dashboard() {
  const [personas, setPersonas] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [stats, setStats] = useState({ total: 0, active: 0, ingesting: 0, draft: 0, failed: 0 });

  useEffect(() => {
    loadPersonas();
  }, []);

  const loadPersonas = async () => {
    setLoading(true);
    setError('');

    try {
      // Fetch all personas (no status filter to get everything)
      const data = await api.getPersonas();
      setPersonas(data.personas || []);

      // Calculate stats
      const stats = {
        total: data.personas?.length || 0,
        active: data.personas?.filter(p => p.status === 'active').length || 0,
        ingesting: data.personas?.filter(p => p.status === 'ingesting').length || 0,
        draft: data.personas?.filter(p => p.status === 'draft').length || 0,
        failed: data.personas?.filter(p => p.status === 'failed').length || 0
      };
      setStats(stats);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (personaId, displayName) => {
    if (!confirm(`Are you sure you want to delete "${displayName}"? This will remove all associated data.`)) {
      return;
    }

    try {
      await api.deletePersona(personaId);
      loadPersonas(); // Reload list
    } catch (err) {
      alert(`Error deleting persona: ${err.message}`);
    }
  };

  if (loading) {
    return (
      <div className="loading">
        <div className="spinner"></div>
        <p>Loading personas...</p>
      </div>
    );
  }

  return (
    <div className="dashboard">
      <div className="dashboard-header">
        <h1>Persona Dashboard</h1>
        <Link to="/create" className="btn btn-primary">
          Create New Persona
        </Link>
      </div>

      {error && <div className="error-message">{error}</div>}

      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-value">{stats.total}</div>
          <div className="stat-label">Total Personas</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{stats.active}</div>
          <div className="stat-label">Active</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{stats.ingesting}</div>
          <div className="stat-label">Ingesting</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{stats.draft}</div>
          <div className="stat-label">Drafts</div>
        </div>
        {stats.failed > 0 && (
          <div className="stat-card stat-danger">
            <div className="stat-value">{stats.failed}</div>
            <div className="stat-label">Failed</div>
          </div>
        )}
      </div>

      <div className="personas-list">
        {personas.length === 0 ? (
          <div className="empty-state">
            <p>No personas yet. Create your first one!</p>
            <Link to="/create" className="btn btn-primary">
              Create Persona
            </Link>
          </div>
        ) : (
          <div className="grid grid-3">
            {personas.map(persona => (
              <div key={persona.id} className="persona-card">
                <div className="persona-card-header">
                  <h3>{persona.display_name}</h3>
                  <span className={`badge badge-${persona.status}`}>
                    {persona.status}
                  </span>
                </div>
                <div className="persona-card-body">
                  <div className="persona-years">
                    {persona.birth_year} - {persona.death_year || 'present'}
                  </div>
                  <div className="persona-id">ID: {persona.persona_id}</div>
                  <div className="persona-description">
                    {persona.description?.substring(0, 100)}
                    {persona.description?.length > 100 ? '...' : ''}
                  </div>
                </div>
                <div className="persona-card-footer">
                  <Link
                    to={`/persona/${persona.persona_id}`}
                    className="btn btn-secondary"
                  >
                    View Details
                  </Link>
                  <button
                    onClick={() => handleDelete(persona.persona_id, persona.display_name)}
                    className="btn btn-danger"
                  >
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default Dashboard;
