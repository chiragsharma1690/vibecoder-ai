import axios from 'axios';
import { ConnectFormData, CreateTicketData } from '../types';

const apiClient = axios.create({
  baseURL: 'http://localhost:8000/api',
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true,
});

export const apiService = {
  connectWorkspace: (data: ConnectFormData) => apiClient.post('/connect', data),
  setBranch: (data: { branch_name: string }) => apiClient.post('/set-branch', data),
  createJiraTicket: (data: CreateTicketData) => apiClient.post('/jira/create', data),
  generatePlan: (data: { ticket_id: string; feedback?: string; previous_plan?: any }) => apiClient.post('/chat/plan', data),
  executePlan: (data: { ticket_id: string; plan: any; async_mode: boolean }) => apiClient.post('/chat/execute', data),
  pushCode: (data: { ticket_id: string }) => apiClient.post('/chat/push', data),
};