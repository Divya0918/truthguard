import axios from 'axios';
import type {
  ChatResponse, ConversationSummary, ConversationDetail,
  Document, DocumentDetail,
  ConvAdminSummary, ConvAdminDetail, DashboardStats,
  ResolutionTask, Clarification,
} from '../types';

const api = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
});

// Attach JWT token to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('tg_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Redirect to /login on 401
api.interceptors.response.use(
  (r) => r,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('tg_token');
      localStorage.removeItem('tg_user');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// ─── Auth ──────────────────────────────────────────────────
export const auth = {
  login: async (email: string, password: string) => {
    const form = new FormData();
    form.append('username', email);
    form.append('password', password);
    const res = await api.post('/auth/token', form, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    });
    return res.data as { access_token: string; role: string; full_name: string };
  },
  register: async (email: string, full_name: string, password: string) => {
    const res = await api.post('/auth/register', { email, full_name, password });
    return res.data as { access_token: string; role: string; full_name: string };
  },
  me: async () => {
    const res = await api.get('/auth/me');
    return res.data;
  },
};

// ─── Chat ──────────────────────────────────────────────────
export const chat = {
  ask: async (question: string, conversation_id?: string): Promise<ChatResponse> => {
    const res = await api.post('/chat/ask', { question, conversation_id });
    return res.data;
  },
  listConversations: async (): Promise<ConversationSummary[]> => {
    const res = await api.get('/chat/conversations');
    return res.data;
  },
  getConversation: async (id: string): Promise<ConversationDetail> => {
    const res = await api.get(`/chat/conversations/${id}`);
    return res.data;
  },
};

// ─── Admin: Documents ──────────────────────────────────────
export const documents = {
  list: async (status?: string): Promise<Document[]> => {
    const res = await api.get('/admin/documents/', { params: status ? { status } : {} });
    return res.data;
  },
  get: async (id: string): Promise<DocumentDetail> => {
    const res = await api.get(`/admin/documents/${id}`);
    return res.data;
  },
  upload: async (formData: FormData): Promise<Document> => {
    const res = await api.post('/admin/documents/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data;
  },
  publish: async (id: string): Promise<Document> => {
    const res = await api.post(`/admin/documents/${id}/publish`);
    return res.data;
  },
  reject: async (id: string): Promise<Document> => {
    const res = await api.post(`/admin/documents/${id}/reject`);
    return res.data;
  },
  retry: async (id: string): Promise<Document> => {
    const res = await api.post(`/admin/documents/${id}/retry`);
    return res.data;
  },
  addPriorityEntry: async (question: string, answer: string, timestamp?: string): Promise<Document> => {
    const res = await api.post('/admin/documents/priority/entry', { question, answer, timestamp });
    return res.data;
  },
  getPriorityDetails: async (): Promise<DocumentDetail> => {
    const res = await api.get('/admin/documents/priority/details');
    return res.data;
  },
};

// ─── Admin: History ────────────────────────────────────────
export const history = {
  listConversations: async (): Promise<ConvAdminSummary[]> => {
    const res = await api.get('/admin/history/conversations');
    return res.data;
  },
  getConversation: async (id: string): Promise<ConvAdminDetail> => {
    const res = await api.get(`/admin/history/conversations/${id}`);
    return res.data;
  },
  stats: async (): Promise<DashboardStats> => {
    const res = await api.get('/admin/history/stats');
    return res.data;
  },
};

// ─── Admin: Resolution ─────────────────────────────────────
export const resolution = {
  listTasks: async (status?: string): Promise<ResolutionTask[]> => {
    const res = await api.get('/admin/resolution/tasks', { params: status ? { status } : {} });
    return res.data;
  },
  getTask: async (id: string): Promise<ResolutionTask> => {
    const res = await api.get(`/admin/resolution/tasks/${id}`);
    return res.data;
  },
  createClarification: async (taskId: string, answer: string): Promise<Clarification> => {
    const res = await api.post(`/admin/resolution/tasks/${taskId}/clarify`, { answer });
    return res.data;
  },
  updateClarification: async (taskId: string, clarId: string, answer: string): Promise<Clarification> => {
    const res = await api.put(`/admin/resolution/tasks/${taskId}/clarify/${clarId}`, { answer });
    return res.data;
  },
  approveClarification: async (taskId: string, clarId: string): Promise<Clarification> => {
    const res = await api.post(`/admin/resolution/tasks/${taskId}/clarify/${clarId}/approve`);
    return res.data;
  },
  publishClarification: async (taskId: string, clarId: string): Promise<Clarification> => {
    const res = await api.post(`/admin/resolution/tasks/${taskId}/clarify/${clarId}/publish`);
    return res.data;
  },
  getClarification: async (taskId: string): Promise<Clarification | null> => {
    const res = await api.get(`/admin/resolution/tasks/${taskId}/clarification`);
    return res.data;
  },
  resolvePriority: async (taskId: string, answer: string, timestamp?: string): Promise<ResolutionTask> => {
    const res = await api.post(`/admin/resolution/tasks/${taskId}/resolve-priority`, { answer, timestamp });
    return res.data;
  },
  uploadPolicy: async (taskId: string, formData: FormData): Promise<{ document_id: string; task_id: string; status: string }> => {
    const res = await api.post(`/admin/resolution/tasks/${taskId}/upload-policy`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data;
  },
};

export default api;
