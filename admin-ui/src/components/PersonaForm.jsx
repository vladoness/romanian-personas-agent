import { useState } from 'react';
import './PersonaForm.css';

function PersonaForm({ onSubmit, initialData = null }) {
  const [formData, setFormData] = useState(initialData || {
    persona_id: '',
    display_name: '',
    birth_year: '',
    death_year: '',
    description: '',
    speaking_style: '',
    key_themes: '',
    voice_prompt: '',
    representative_quotes: [''],
    color: '#666666',
    works_top_k: 8,
    quotes_top_k: 10,
    profile_top_k: 5
  });

  const [errors, setErrors] = useState({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  const validateForm = () => {
    const newErrors = {};

    if (!formData.persona_id) {
      newErrors.persona_id = 'Persona ID is required';
    } else if (!/^[a-zA-Z0-9_-]+$/.test(formData.persona_id)) {
      newErrors.persona_id = 'Persona ID can only contain letters, numbers, hyphens, and underscores';
    }

    if (!formData.display_name) {
      newErrors.display_name = 'Display name is required';
    }

    if (!formData.birth_year) {
      newErrors.birth_year = 'Birth year is required';
    } else if (formData.birth_year < 1000 || formData.birth_year > new Date().getFullYear()) {
      newErrors.birth_year = 'Birth year must be a valid year';
    }

    if (formData.death_year && formData.death_year < formData.birth_year) {
      newErrors.death_year = 'Death year must be after birth year';
    }

    if (!formData.description) {
      newErrors.description = 'Description is required';
    }

    if (!formData.speaking_style) {
      newErrors.speaking_style = 'Speaking style is required';
    }

    if (!formData.key_themes) {
      newErrors.key_themes = 'Key themes are required';
    }

    if (!formData.voice_prompt) {
      newErrors.voice_prompt = 'Voice prompt is required';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!validateForm()) {
      return;
    }

    setIsSubmitting(true);

    try {
      // Clean up data
      const submitData = {
        ...formData,
        birth_year: parseInt(formData.birth_year),
        death_year: formData.death_year ? parseInt(formData.death_year) : null,
        representative_quotes: formData.representative_quotes.filter(q => q.trim() !== '')
      };

      await onSubmit(submitData);
    } catch (err) {
      alert(`Error: ${err.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleChange = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    // Clear error when user starts typing
    if (errors[field]) {
      setErrors(prev => ({ ...prev, [field]: undefined }));
    }
  };

  const addQuote = () => {
    setFormData(prev => ({
      ...prev,
      representative_quotes: [...prev.representative_quotes, '']
    }));
  };

  const removeQuote = (index) => {
    setFormData(prev => ({
      ...prev,
      representative_quotes: prev.representative_quotes.filter((_, i) => i !== index)
    }));
  };

  const updateQuote = (index, value) => {
    setFormData(prev => ({
      ...prev,
      representative_quotes: prev.representative_quotes.map((q, i) => i === index ? value : q)
    }));
  };

  return (
    <form onSubmit={handleSubmit} className="persona-form">
      <div className="form-section">
        <h3>Basic Information</h3>

        <div className="form-row">
          <div className="form-group">
            <label>Persona ID *</label>
            <input
              type="text"
              value={formData.persona_id}
              onChange={(e) => handleChange('persona_id', e.target.value)}
              placeholder="e.g., new_persona"
              disabled={!!initialData}
            />
            {errors.persona_id && <span className="error-text">{errors.persona_id}</span>}
            <small>Unique identifier (lowercase, alphanumeric, hyphens, underscores)</small>
          </div>

          <div className="form-group">
            <label>Display Name *</label>
            <input
              type="text"
              value={formData.display_name}
              onChange={(e) => handleChange('display_name', e.target.value)}
              placeholder="e.g., Ion Creanga"
            />
            {errors.display_name && <span className="error-text">{errors.display_name}</span>}
          </div>
        </div>

        <div className="form-row">
          <div className="form-group">
            <label>Birth Year *</label>
            <input
              type="number"
              value={formData.birth_year}
              onChange={(e) => handleChange('birth_year', e.target.value)}
              placeholder="1837"
            />
            {errors.birth_year && <span className="error-text">{errors.birth_year}</span>}
          </div>

          <div className="form-group">
            <label>Death Year</label>
            <input
              type="number"
              value={formData.death_year}
              onChange={(e) => handleChange('death_year', e.target.value)}
              placeholder="1889 (optional)"
            />
            {errors.death_year && <span className="error-text">{errors.death_year}</span>}
          </div>
        </div>

        <div className="form-group">
          <label>Color</label>
          <input
            type="color"
            value={formData.color}
            onChange={(e) => handleChange('color', e.target.value)}
          />
          <small>UI accent color for this persona</small>
        </div>
      </div>

      <div className="form-section">
        <h3>Description & Voice</h3>

        <div className="form-group">
          <label>Description *</label>
          <textarea
            value={formData.description}
            onChange={(e) => handleChange('description', e.target.value)}
            placeholder="Brief biographical description..."
            rows={3}
          />
          {errors.description && <span className="error-text">{errors.description}</span>}
        </div>

        <div className="form-group">
          <label>Speaking Style *</label>
          <textarea
            value={formData.speaking_style}
            onChange={(e) => handleChange('speaking_style', e.target.value)}
            placeholder="e.g., Romantic, melancholic, philosophical"
            rows={2}
          />
          {errors.speaking_style && <span className="error-text">{errors.speaking_style}</span>}
        </div>

        <div className="form-group">
          <label>Key Themes *</label>
          <textarea
            value={formData.key_themes}
            onChange={(e) => handleChange('key_themes', e.target.value)}
            placeholder="e.g., Love, nature, mortality, Romanian identity"
            rows={2}
          />
          {errors.key_themes && <span className="error-text">{errors.key_themes}</span>}
        </div>

        <div className="form-group">
          <label>Voice Prompt *</label>
          <textarea
            value={formData.voice_prompt}
            onChange={(e) => handleChange('voice_prompt', e.target.value)}
            placeholder="You are [Persona Name]..."
            rows={6}
          />
          {errors.voice_prompt && <span className="error-text">{errors.voice_prompt}</span>}
          <small>System prompt for Claude synthesis</small>
        </div>
      </div>

      <div className="form-section">
        <h3>Representative Quotes</h3>
        {formData.representative_quotes.map((quote, index) => (
          <div key={index} className="quote-row">
            <textarea
              value={quote}
              onChange={(e) => updateQuote(index, e.target.value)}
              placeholder="Enter a representative quote..."
              rows={2}
            />
            {formData.representative_quotes.length > 1 && (
              <button
                type="button"
                onClick={() => removeQuote(index)}
                className="btn btn-danger btn-sm"
              >
                Remove
              </button>
            )}
          </div>
        ))}
        <button type="button" onClick={addQuote} className="btn btn-secondary">
          Add Quote
        </button>
      </div>

      <div className="form-section">
        <h3>Retrieval Settings (Advanced)</h3>
        <div className="form-row">
          <div className="form-group">
            <label>Works Top K</label>
            <input
              type="number"
              value={formData.works_top_k}
              onChange={(e) => handleChange('works_top_k', parseInt(e.target.value))}
              min={1}
              max={20}
            />
            <small>Number of works chunks to retrieve</small>
          </div>

          <div className="form-group">
            <label>Quotes Top K</label>
            <input
              type="number"
              value={formData.quotes_top_k}
              onChange={(e) => handleChange('quotes_top_k', parseInt(e.target.value))}
              min={1}
              max={20}
            />
            <small>Number of quotes to retrieve</small>
          </div>

          <div className="form-group">
            <label>Profile Top K</label>
            <input
              type="number"
              value={formData.profile_top_k}
              onChange={(e) => handleChange('profile_top_k', parseInt(e.target.value))}
              min={1}
              max={20}
            />
            <small>Number of profile chunks to retrieve</small>
          </div>
        </div>
      </div>

      <div className="form-actions">
        <button type="submit" className="btn btn-primary" disabled={isSubmitting}>
          {isSubmitting ? 'Submitting...' : 'Create Persona'}
        </button>
      </div>
    </form>
  );
}

export default PersonaForm;
