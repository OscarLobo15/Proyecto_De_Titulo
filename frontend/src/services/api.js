import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  timeout: 30000,
});

export async function getOptions() {
  const { data } = await api.get('/options');
  return data;
}

export async function generateProject(payload) {
  const { data } = await api.post('/generate', payload);
  return data;
}

export async function analyzeProject(message) {
  const { data } = await api.post('/api/ai/analyze-project', { message }, { timeout: 310000 });
  return data;
}

export async function generateProjectWithAI(payload) {
  const { data } = await api.post('/api/ai/generate-project', payload, { timeout: 310000 });
  return data;
}

export async function planProject(payload) {
  const { data } = await api.post('/api/ai/plan-project', payload, { timeout: 310000 });
  return data;
}

export async function extractPdf(file, options = {}) {
  const form = new FormData();
  form.append('file', file);
  const { data } = await api.post('/api/ai/extract-pdf', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: options.onUploadProgress,
    timeout: 180000,
  });
  return data;
}
