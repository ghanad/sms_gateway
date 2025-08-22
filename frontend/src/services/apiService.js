import axios from 'axios';

const api = axios.create({
  baseURL: '/api'
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

const login = async (username, password) => {
  const response = await api.post('/auth/login', { username, password });
  return response.data;
};

const logout = async () => {
  await api.post('/auth/logout');
};

const getDashboardStats = async () => {
  const response = await api.get('/dashboard');
  return response.data;
};

const getMessages = async (filters) => {
  const response = await api.get('/messages', { params: filters });
  return response.data;
};

const getMessageDetails = async (trackingId) => {
  const response = await api.get(`/messages/${trackingId}`);
  return response.data;
};

const getUsers = async () => {
  const response = await api.get('/users');
  return response.data;
};

const createUser = async (userData) => {
  const response = await api.post('/users', userData);
  return response.data;
};

const updateUser = async (userId, userData) => {
  const response = await api.put(`/users/${userId}`, userData);
  return response.data;
};

const deleteUser = async (userId) => {
  await api.delete(`/users/${userId}`);
};

const activateUser = async (userId) => {
  await api.post(`/users/${userId}/activate`);
};

const deactivateUser = async (userId) => {
  await api.post(`/users/${userId}/deactivate`);
};

export default {
  login,
  logout,
  getDashboardStats,
  getMessages,
  getMessageDetails,
  getUsers,
  createUser,
  updateUser,
  deleteUser,
  activateUser,
  deactivateUser
};
