import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from '../services/api';
import FileUploader from '../components/FileUploader';
import IngestionStatus from '../components/IngestionStatus';
import './PersonaDetail.css';

function PersonaDetail() {
  const { personaId } = useParams();
  const navigate = useNavigate();
  const [persona, setPersona] = useState(null);
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState('details');

  useEffect(() => {
    loadPersona();
    loadFiles();
  }, [personaId]);

  const loadPersona = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await api.getPersona(personaId);
      setPersona(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const loadFiles = async () => {
    try {
      const data = await api.getFiles(personaId);
      setFiles(data.files || []);
    } catch (err) {
      console.error('Error loading files:', err);
    }
  };

  const handleDelete = async () => {
    if (!confirm(`Are you sure you want to delete "${persona.display_name}"? This cannot be undone.`)) {
      return;
    }

    try {
      await api.deletePersona(personaId);
      navigate('/');
    } catch (err) {
      alert(`Error deleting persona: ${err.message}`);
    }
  };

  const handleTriggerIngestion = async () => {
    try {
      await api.triggerIngestion(personaId);
      setActiveTab('ingestion');
      loadPersona(); // Refresh status
    } catch (err) {
      alert(`Error triggering ingestion: ${err.message}`);
    }
  };

  const handleUploadComplete = () => {
    loadFiles();
  };

  if (loading) {
    return (
      <div className="loading">
        <div className="spinner"></div>
        <p>Loading persona...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="error-message">{error}</div>
    );
  }

  if (!persona) {
    return <div>Persona not found</div>;
  }

  const groupedFiles = files.reduce((acc, file) => {
    if (!acc[file.collection_type]) {
      acc[file.collection_type] = [];
    }
    acc[file.collection_type].push(file);
    return acc;
  }, {});

  return (
    <div className="persona-detail">
      <div className="detail-header">
        <div>
          <h1>{persona.display_name}</h1>
          <div className="detail-meta">
            <span className={`badge badge-${persona.status}`}>{persona.status}</span>
            <span className="detail-years">
              {persona.birth_year} - {persona.death_year || 'present'}
            </span>
          </div>
        </div>
        <div className="header-actions">
          {(persona.status === 'draft' || persona.status === 'failed') && (
            <button onClick={handleTriggerIngestion} className="btn btn-primary">
              {persona.status === 'failed' ? 'Retry Ingestion' : 'Start Ingestion'}
            </button>
          )}
          <button onClick={handleDelete} className="btn btn-danger">
            Delete Persona
          </button>
        </div>
      </div>

      <div className="tabs">
        <button
          className={`tab ${activeTab === 'details' ? 'active' : ''}`}
          onClick={() => setActiveTab('details')}
        >
          Details
        </button>
        <button
          className={`tab ${activeTab === 'files' ? 'active' : ''}`}
          onClick={() => setActiveTab('files')}
        >
          Files ({files.length})
        </button>
        <button
          className={`tab ${activeTab === 'upload' ? 'active' : ''}`}
          onClick={() => setActiveTab('upload')}
        >
          Upload
        </button>
        <button
          className={`tab ${activeTab === 'ingestion' ? 'active' : ''}`}
          onClick={() => setActiveTab('ingestion')}
        >
          Ingestion Status
        </button>
      </div>

      <div className="tab-content">
        {activeTab === 'details' && (
          <div className="details-grid">
            <div className="detail-card">
              <h3>Basic Information</h3>
              <div className="detail-row">
                <strong>ID:</strong>
                <span>{persona.persona_id}</span>
              </div>
              <div className="detail-row">
                <strong>Display Name:</strong>
                <span>{persona.display_name}</span>
              </div>
              <div className="detail-row">
                <strong>Birth Year:</strong>
                <span>{persona.birth_year}</span>
              </div>
              {persona.death_year && (
                <div className="detail-row">
                  <strong>Death Year:</strong>
                  <span>{persona.death_year}</span>
                </div>
              )}
              <div className="detail-row">
                <strong>Color:</strong>
                <span>
                  <div
                    className="color-preview"
                    style={{ backgroundColor: persona.color }}
                  />
                  {persona.color}
                </span>
              </div>
            </div>

            <div className="detail-card">
              <h3>Description</h3>
              <p>{persona.description}</p>
            </div>

            <div className="detail-card">
              <h3>Speaking Style</h3>
              <p>{persona.speaking_style}</p>
            </div>

            <div className="detail-card">
              <h3>Key Themes</h3>
              <p>{persona.key_themes}</p>
            </div>

            <div className="detail-card">
              <h3>Voice Prompt</h3>
              <pre className="voice-prompt">{persona.voice_prompt}</pre>
            </div>

            {persona.representative_quotes && persona.representative_quotes.length > 0 && (
              <div className="detail-card">
                <h3>Representative Quotes</h3>
                <ul className="quotes-list">
                  {persona.representative_quotes.map((quote, index) => (
                    <li key={index}>{quote}</li>
                  ))}
                </ul>
              </div>
            )}

            <div className="detail-card">
              <h3>Retrieval Settings</h3>
              <div className="detail-row">
                <strong>Works Top K:</strong>
                <span>{persona.works_top_k}</span>
              </div>
              <div className="detail-row">
                <strong>Quotes Top K:</strong>
                <span>{persona.quotes_top_k}</span>
              </div>
              <div className="detail-row">
                <strong>Profile Top K:</strong>
                <span>{persona.profile_top_k}</span>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'files' && (
          <div className="files-view">
            {files.length === 0 ? (
              <div className="empty-state">
                <p>No files uploaded yet.</p>
                <button
                  onClick={() => setActiveTab('upload')}
                  className="btn btn-primary"
                >
                  Upload Files
                </button>
              </div>
            ) : (
              <div>
                {['works', 'quotes', 'profile'].map(type => (
                  groupedFiles[type] && groupedFiles[type].length > 0 && (
                    <div key={type} className="files-group">
                      <h3>{type.charAt(0).toUpperCase() + type.slice(1)} ({groupedFiles[type].length})</h3>
                      <table className="files-table">
                        <thead>
                          <tr>
                            <th>File Name</th>
                            <th>Size</th>
                            <th>Uploaded</th>
                          </tr>
                        </thead>
                        <tbody>
                          {groupedFiles[type].map(file => (
                            <tr key={file.id}>
                              <td>{file.file_name}</td>
                              <td>{(file.file_size_bytes / 1024).toFixed(1)} KB</td>
                              <td>{new Date(file.created_at).toLocaleString()}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )
                ))}
              </div>
            )}
          </div>
        )}

        {activeTab === 'upload' && (
          <FileUploader
            personaId={personaId}
            onUploadComplete={handleUploadComplete}
          />
        )}

        {activeTab === 'ingestion' && (
          <IngestionStatus
            personaId={personaId}
            onComplete={() => loadPersona()}
          />
        )}
      </div>
    </div>
  );
}

export default PersonaDetail;
