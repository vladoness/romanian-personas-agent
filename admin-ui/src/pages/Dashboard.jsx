import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import api from '../services/api';
import './Dashboard.css';

function Dashboard() {
  const [personas, setPersonas] = useState([]);
  const [collections, setCollections] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [stats, setStats] = useState({ total: 0, active: 0, ingesting: 0, draft: 0, failed: 0, totalVectors: 0 });

  useEffect(() => {
    loadPersonas();
  }, []);

  const loadPersonas = async () => {
    setLoading(true);
    setError('');

    try {
      const data = await api.getPersonas();
      const personaList = data.personas || [];
      setPersonas(personaList);

      // Fetch collection stats for each persona in parallel
      const collectionResults = {};
      let totalVectors = 0;
      const collectionPromises = personaList.map(async (p) => {
        try {
          const colData = await api.getCollections(p.persona_id);
          collectionResults[p.persona_id] = colData;
          totalVectors += colData.total_vectors || 0;
        } catch {
          collectionResults[p.persona_id] = { total_vectors: 0, collections: {} };
        }
      });
      await Promise.all(collectionPromises);
      setCollections(collectionResults);

      // Calculate stats
      setStats({
        total: personaList.length,
        active: personaList.filter(p => p.status === 'active').length,
        ingesting: personaList.filter(p => p.status === 'ingesting').length,
        draft: personaList.filter(p => p.status === 'draft').length,
        failed: personaList.filter(p => p.status === 'failed').length,
        totalVectors
      });
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
      loadPersonas();
    } catch (err) {
      alert(`Error deleting persona: ${err.message}`);
    }
  };

  const formatVectors = (n) => {
    if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
    return String(n);
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
          <div className="stat-value">{formatVectors(stats.totalVectors)}</div>
          <div className="stat-label">Total Vectors</div>
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
            {personas.map(persona => {
              const colStats = collections[persona.persona_id];
              const cols = colStats?.collections || {};
              return (
                <div key={persona.id} className="persona-card" style={{ borderTop: `3px solid ${persona.color}` }}>
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
                    {colStats && (
                      <div className="persona-vectors">
                        <span title="Works vectors">W: {formatVectors(cols.works?.vectors || 0)}</span>
                        <span title="Quotes vectors">Q: {formatVectors(cols.quotes?.vectors || 0)}</span>
                        <span title="Profile vectors">P: {formatVectors(cols.profile?.vectors || 0)}</span>
                        <strong title="Total vectors">{formatVectors(colStats.total_vectors || 0)} vectors</strong>
                      </div>
                    )}
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
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

export default Dashboard;
