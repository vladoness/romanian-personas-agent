import { useState } from 'react';
import api from '../services/api';
import './FileUploader.css';

function FileUploader({ personaId, onUploadComplete }) {
  const [uploading, setUploading] = useState({ works: false, quotes: false, profile: false });
  const [selectedFiles, setSelectedFiles] = useState({ works: [], quotes: [], profile: [] });
  const [uploadResults, setUploadResults] = useState({ works: null, quotes: null, profile: null });

  const collectionTypes = [
    {
      type: 'works',
      label: 'Literary Works',
      accept: '.txt,.md',
      description: 'Upload poems, essays, speeches (.txt, .md)'
    },
    {
      type: 'quotes',
      label: 'Quotes',
      accept: '.jsonl',
      description: 'Upload quotes in JSONL format'
    },
    {
      type: 'profile',
      label: 'Profile Documents',
      accept: '.txt,.md,.pdf',
      description: 'Upload biographical documents (.txt, .md, .pdf)'
    }
  ];

  const handleFileSelect = (type, event) => {
    const files = Array.from(event.target.files);
    setSelectedFiles(prev => ({ ...prev, [type]: files }));
  };

  const handleUpload = async (type) => {
    const files = selectedFiles[type];
    if (files.length === 0) {
      alert('Please select files to upload');
      return;
    }

    setUploading(prev => ({ ...prev, [type]: true }));
    setUploadResults(prev => ({ ...prev, [type]: null }));

    try {
      const result = await api.uploadFiles(personaId, type, files);
      setUploadResults(prev => ({ ...prev, [type]: result }));
      setSelectedFiles(prev => ({ ...prev, [type]: [] }));

      // Clear file input
      const input = document.getElementById(`file-input-${type}`);
      if (input) input.value = '';

      if (onUploadComplete) {
        onUploadComplete(type, result);
      }
    } catch (err) {
      alert(`Upload failed: ${err.message}`);
    } finally {
      setUploading(prev => ({ ...prev, [type]: false }));
    }
  };

  const clearFiles = (type) => {
    setSelectedFiles(prev => ({ ...prev, [type]: [] }));
    const input = document.getElementById(`file-input-${type}`);
    if (input) input.value = '';
  };

  return (
    <div className="file-uploader">
      <h2>Upload Files</h2>
      <p className="uploader-description">
        Upload source documents for ingestion into ChromaDB collections.
      </p>

      <div className="upload-sections">
        {collectionTypes.map(({ type, label, accept, description }) => (
          <div key={type} className="upload-section">
            <div className="upload-header">
              <h3>{label}</h3>
              <span className="badge badge-draft">{type}</span>
            </div>

            <p className="upload-description">{description}</p>

            <div className="upload-controls">
              <input
                id={`file-input-${type}`}
                type="file"
                accept={accept}
                multiple
                onChange={(e) => handleFileSelect(type, e)}
                disabled={uploading[type]}
              />

              {selectedFiles[type].length > 0 && (
                <div className="selected-files">
                  <div className="selected-files-header">
                    <strong>Selected files ({selectedFiles[type].length}):</strong>
                    <button
                      type="button"
                      onClick={() => clearFiles(type)}
                      className="btn btn-secondary btn-sm"
                      disabled={uploading[type]}
                    >
                      Clear
                    </button>
                  </div>
                  <ul>
                    {selectedFiles[type].map((file, index) => (
                      <li key={index}>
                        {file.name} ({(file.size / 1024).toFixed(1)} KB)
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <button
                onClick={() => handleUpload(type)}
                className="btn btn-primary"
                disabled={uploading[type] || selectedFiles[type].length === 0}
              >
                {uploading[type] ? 'Uploading...' : 'Upload Files'}
              </button>
            </div>

            {uploadResults[type] && (
              <div className="upload-result">
                <div className="success-message">
                  Successfully uploaded {uploadResults[type].uploaded_count} file(s)
                  {uploadResults[type].skipped_count > 0 && (
                    <span> ({uploadResults[type].skipped_count} skipped)</span>
                  )}
                </div>
                {uploadResults[type].uploaded.length > 0 && (
                  <details>
                    <summary>View uploaded files</summary>
                    <ul>
                      {uploadResults[type].uploaded.map((file, index) => (
                        <li key={index}>
                          {file.name} ({(file.size_bytes / 1024).toFixed(1)} KB)
                        </li>
                      ))}
                    </ul>
                  </details>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

export default FileUploader;
