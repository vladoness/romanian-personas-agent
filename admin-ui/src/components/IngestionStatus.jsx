import { useState, useEffect } from 'react';
import api from '../services/api';
import './IngestionStatus.css';

function IngestionStatus({ personaId, onComplete }) {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [polling, setPolling] = useState(true);

  useEffect(() => {
    loadStatus();

    // Poll every 3 seconds if not all completed
    const interval = setInterval(() => {
      if (polling) {
        loadStatus();
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [personaId, polling]);

  const loadStatus = async () => {
    try {
      const data = await api.getIngestionStatus(personaId);
      setStatus(data);
      setError('');

      // Stop polling if all completed or any failed
      if (data.all_completed || data.any_failed) {
        setPolling(false);
        if (data.all_completed && onComplete) {
          onComplete(data);
        }
      }
    } catch (err) {
      setError(err.message);
      setPolling(false);
    } finally {
      setLoading(false);
    }
  };

  const handleRetry = async () => {
    setError('');
    try {
      await api.retryIngestion(personaId);
      setPolling(true);
      loadStatus();
    } catch (err) {
      setError(err.message);
    }
  };

  if (loading) {
    return (
      <div className="ingestion-status">
        <div className="loading">
          <div className="spinner"></div>
          <p>Loading ingestion status...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="ingestion-status">
        <div className="error-message">{error}</div>
      </div>
    );
  }

  if (!status) {
    return null;
  }

  const getStatusColor = (jobStatus) => {
    switch (jobStatus) {
      case 'completed': return '#28a745';
      case 'processing': return '#667eea';
      case 'failed': return '#dc3545';
      default: return '#6c757d';
    }
  };

  return (
    <div className="ingestion-status">
      <div className="status-header">
        <h2>Ingestion Status</h2>
        <span className={`badge badge-${status.overall_status}`}>
          {status.overall_status}
        </span>
      </div>

      <div className="overall-progress">
        <div className="progress-info">
          <span>Overall Progress</span>
          <span>{status.overall_progress}%</span>
        </div>
        <div className="progress-bar">
          <div
            className="progress-bar-fill"
            style={{ width: `${status.overall_progress}%` }}
          />
        </div>
      </div>

      <div className="jobs-list">
        {status.jobs.map(job => (
          <div key={job.id} className="job-card">
            <div className="job-header">
              <div className="job-title">
                <strong>{job.collection_type}</strong>
                <span className={`badge badge-${job.status}`}>
                  {job.status}
                </span>
              </div>
              {job.total_vectors !== null && (
                <div className="job-vectors">
                  {job.total_vectors} vectors
                </div>
              )}
            </div>

            <div className="job-progress">
              <div className="progress-bar">
                <div
                  className="progress-bar-fill"
                  style={{
                    width: `${job.progress}%`,
                    backgroundColor: getStatusColor(job.status)
                  }}
                />
              </div>
              <span className="progress-percentage">{job.progress}%</span>
            </div>

            {job.error_message && (
              <div className="job-error">
                Error: {job.error_message}
              </div>
            )}

            {job.started_at && (
              <div className="job-timing">
                <small>
                  Started: {new Date(job.started_at).toLocaleString()}
                  {job.completed_at && (
                    <> | Completed: {new Date(job.completed_at).toLocaleString()}</>
                  )}
                </small>
              </div>
            )}
          </div>
        ))}
      </div>

      {status.any_failed && (
        <div className="status-actions">
          <button onClick={handleRetry} className="btn btn-primary">
            Retry Failed Jobs
          </button>
        </div>
      )}

      {status.all_completed && (
        <div className="success-message">
          All ingestion jobs completed successfully! The persona is now active.
        </div>
      )}

      {polling && (
        <div className="info-message">
          Auto-refreshing every 3 seconds...
        </div>
      )}
    </div>
  );
}

export default IngestionStatus;
