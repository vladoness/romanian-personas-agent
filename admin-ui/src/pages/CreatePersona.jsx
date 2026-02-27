import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../services/api';
import PersonaForm from '../components/PersonaForm';
import FileUploader from '../components/FileUploader';
import IngestionStatus from '../components/IngestionStatus';
import './CreatePersona.css';

function CreatePersona() {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [createdPersona, setCreatedPersona] = useState(null);
  const [error, setError] = useState('');

  const handlePersonaCreate = async (formData) => {
    setError('');
    try {
      const result = await api.createPersona(formData);
      setCreatedPersona({
        persona_id: result.persona_id,
        display_name: formData.display_name
      });
      setStep(2);
    } catch (err) {
      setError(err.message);
      throw err;
    }
  };

  const handleUploadComplete = (type, result) => {
    console.log(`Uploaded ${type}:`, result);
  };

  const handleTriggerIngestion = async () => {
    try {
      await api.triggerIngestion(createdPersona.persona_id);
      setStep(3);
    } catch (err) {
      setError(err.message);
    }
  };

  const handleIngestionComplete = (status) => {
    console.log('Ingestion completed:', status);
    // Auto-advance to success after a brief moment
    setTimeout(() => {
      setStep(4);
    }, 2000);
  };

  const handleSkipUpload = () => {
    if (confirm('Skip file upload? You can upload files later from the persona detail page.')) {
      navigate(`/persona/${createdPersona.persona_id}`);
    }
  };

  return (
    <div className="create-persona">
      <div className="create-header">
        <h1>Create New Persona</h1>
        <div className="step-indicator">
          <div className={`step ${step >= 1 ? 'active' : ''} ${step > 1 ? 'completed' : ''}`}>
            1. Basic Info
          </div>
          <div className={`step ${step >= 2 ? 'active' : ''} ${step > 2 ? 'completed' : ''}`}>
            2. Upload Files
          </div>
          <div className={`step ${step >= 3 ? 'active' : ''} ${step > 3 ? 'completed' : ''}`}>
            3. Ingestion
          </div>
          <div className={`step ${step >= 4 ? 'active' : ''}`}>
            4. Complete
          </div>
        </div>
      </div>

      {error && <div className="error-message">{error}</div>}

      {step === 1 && (
        <div className="step-content">
          <PersonaForm onSubmit={handlePersonaCreate} />
        </div>
      )}

      {step === 2 && createdPersona && (
        <div className="step-content">
          <div className="success-message mb-3">
            Persona "{createdPersona.display_name}" created successfully!
          </div>

          <FileUploader
            personaId={createdPersona.persona_id}
            onUploadComplete={handleUploadComplete}
          />

          <div className="step-actions">
            <button onClick={handleSkipUpload} className="btn btn-secondary">
              Skip Upload (Upload Later)
            </button>
            <button onClick={handleTriggerIngestion} className="btn btn-primary">
              Proceed to Ingestion
            </button>
          </div>
        </div>
      )}

      {step === 3 && createdPersona && (
        <div className="step-content">
          <IngestionStatus
            personaId={createdPersona.persona_id}
            onComplete={handleIngestionComplete}
          />
        </div>
      )}

      {step === 4 && createdPersona && (
        <div className="step-content">
          <div className="completion-card">
            <div className="completion-icon">✓</div>
            <h2>Persona Created Successfully!</h2>
            <p>
              "{createdPersona.display_name}" has been created and is ready to use.
            </p>
            <div className="completion-actions">
              <button
                onClick={() => navigate(`/persona/${createdPersona.persona_id}`)}
                className="btn btn-primary"
              >
                View Persona Details
              </button>
              <button
                onClick={() => navigate('/')}
                className="btn btn-secondary"
              >
                Back to Dashboard
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default CreatePersona;
