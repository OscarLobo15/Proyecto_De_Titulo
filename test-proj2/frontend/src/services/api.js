import axios from 'axios';

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  timeout: 10000,
});

export async function getHealth() {
  const { data } = await api.get('/health');
  return data;
}

export async function getCurrentUser() {
  const { data } = await api.get('/users/me');
  return data;
}

