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
