import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000';

class ApiClient {
  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      headers: {
        'Content-Type': 'application/json'
      }
    });

    // Add auth interceptor
    this.client.interceptors.request.use(config => {
      const password = this.getPassword();
      if (password) {
        const credentials = btoa(`admin:${password}`);
        config.headers.Authorization = `Basic ${credentials}`;
      }
      return config;
    });

    // Add error interceptor
    this.client.interceptors.response.use(
      response => response,
      error => {
        const message = error.response?.data?.detail || error.message || 'An error occurred';
        console.error('API Error:', message);
        throw new Error(message);
      }
    );
  }

  getPassword() {
    return localStorage.getItem('admin_password');
  }

  setPassword(password) {
    localStorage.setItem('admin_password', password);
  }

  clearPassword() {
    localStorage.removeItem('admin_password');
  }

  isAuthenticated() {
    return !!this.getPassword();
  }

  // Health check
  async healthCheck() {
    const response = await this.client.get('/health');
    return response.data;
  }

  // Personas
  async getPersonas(status = null) {
    const params = status ? { status } : {};
    const response = await this.client.get('/api/personas', { params });
    return response.data;
  }

  async getPersona(personaId) {
    const response = await this.client.get(`/api/personas/${personaId}`);
    return response.data;
  }

  async createPersona(data) {
    const response = await this.client.post('/api/personas', data);
    return response.data;
  }

  async deletePersona(personaId) {
    const response = await this.client.delete(`/api/personas/${personaId}`);
    return response.data;
  }

  // File uploads
  async uploadFiles(personaId, collectionType, files) {
    const formData = new FormData();
    files.forEach(file => {
      formData.append('files', file);
    });

    const response = await this.client.post(
      `/api/personas/${personaId}/upload/${collectionType}`,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      }
    );
    return response.data;
  }

  async getFiles(personaId, collectionType = null) {
    const params = collectionType ? { collection_type: collectionType } : {};
    const response = await this.client.get(`/api/personas/${personaId}/files`, { params });
    return response.data;
  }

  // Ingestion
  async triggerIngestion(personaId) {
    const response = await this.client.post(`/api/personas/${personaId}/ingest`);
    return response.data;
  }

  async getIngestionStatus(personaId) {
    const response = await this.client.get(`/api/personas/${personaId}/ingestion/status`);
    return response.data;
  }

  async retryIngestion(personaId) {
    const response = await this.client.post(`/api/personas/${personaId}/ingestion/retry`);
    return response.data;
  }

  async clearIngestionJobs(personaId) {
    const response = await this.client.delete(`/api/personas/${personaId}/ingestion/jobs`);
    return response.data;
  }
}

export default new ApiClient();
