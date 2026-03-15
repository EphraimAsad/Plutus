import axios, { AxiosError, AxiosRequestConfig } from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 200000, // 200 seconds
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor to add auth token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor to handle auth errors
api.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

// Auth API
export const authApi = {
  login: async (email: string, password: string) => {
    const response = await api.post('/auth/login', { email, password })
    return response.data
  },
  me: async () => {
    const response = await api.get('/auth/me')
    return response.data
  },
}

// Sources API
export const sourcesApi = {
  list: async (activeOnly = true) => {
    const response = await api.get('/sources', { params: { active_only: activeOnly } })
    return response.data
  },
  get: async (id: string) => {
    const response = await api.get(`/sources/${id}`)
    return response.data
  },
  create: async (data: any) => {
    const response = await api.post('/sources', data)
    return response.data
  },
  update: async (id: string, data: any) => {
    const response = await api.put(`/sources/${id}`, data)
    return response.data
  },
  createSchemaMapping: async (sourceId: string, data: any) => {
    const response = await api.post(`/sources/${sourceId}/schema-mapping`, data)
    return response.data
  },
  delete: async (id: string) => {
    await api.delete(`/sources/${id}`)
  },
}

// Ingestion API
export const ingestionApi = {
  upload: async (sourceId: string, file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    const response = await api.post(`/ingestion/upload?source_id=${sourceId}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return response.data
  },
  listJobs: async (params?: { source_id?: string; status?: string; limit?: number; offset?: number }) => {
    const response = await api.get('/ingestion/jobs', { params })
    return response.data
  },
  getJob: async (jobId: string) => {
    const response = await api.get(`/ingestion/jobs/${jobId}`)
    return response.data
  },
  deleteJob: async (jobId: string) => {
    await api.delete(`/ingestion/jobs/${jobId}`)
  },
}

// Reconciliation API
export const reconciliationApi = {
  createRun: async (data: { name: string; left_source_id: string; right_source_id: string; parameters?: any }) => {
    const response = await api.post('/reconciliation/runs', data)
    return response.data
  },
  createDuplicateDetection: async (data: { name: string; source_id: string; parameters?: any }) => {
    const response = await api.post('/reconciliation/duplicate-detection', data)
    return response.data
  },
  listRuns: async (params?: { status?: string; limit?: number; offset?: number }) => {
    const response = await api.get('/reconciliation/runs', { params })
    return response.data
  },
  getRun: async (runId: string) => {
    const response = await api.get(`/reconciliation/runs/${runId}`)
    return response.data
  },
  getSummary: async (runId: string) => {
    const response = await api.get(`/reconciliation/runs/${runId}/summary`)
    return response.data
  },
  getMatches: async (runId: string, params?: any) => {
    const response = await api.get(`/reconciliation/runs/${runId}/matches`, { params })
    return response.data
  },
  getConfirmedMatches: async (runId: string, params?: any) => {
    const response = await api.get(`/reconciliation/runs/${runId}/confirmed-matches`, { params })
    return response.data
  },
  getUnmatched: async (runId: string, params?: any) => {
    const response = await api.get(`/reconciliation/runs/${runId}/unmatched`, { params })
    return response.data
  },
  getCandidateRecords: async (candidateId: string) => {
    const response = await api.get(`/reconciliation/candidates/${candidateId}/records`)
    return response.data
  },
  resolveCandidate: async (candidateId: string, decision: string, note?: string) => {
    const response = await api.post(`/reconciliation/candidates/${candidateId}/resolve`, null, {
      params: { decision, resolution_note: note },
    })
    return response.data
  },
  deleteRun: async (runId: string) => {
    await api.delete(`/reconciliation/runs/${runId}`)
  },
}

// Exceptions API
export const exceptionsApi = {
  list: async (params?: {
    status?: string
    severity?: string
    exception_type?: string
    assigned_to?: string
    limit?: number
    offset?: number
  }) => {
    const response = await api.get('/exceptions', { params })
    return response.data
  },
  get: async (id: string) => {
    const response = await api.get(`/exceptions/${id}`)
    return response.data
  },
  assign: async (id: string, assigneeId: string) => {
    const response = await api.post(`/exceptions/${id}/assign?assignee_id=${assigneeId}`)
    return response.data
  },
  resolve: async (id: string, note?: string) => {
    const response = await api.post(`/exceptions/${id}/resolve`, { resolution_note: note })
    return response.data
  },
  dismiss: async (id: string, note?: string) => {
    const response = await api.post(`/exceptions/${id}/dismiss`, { resolution_note: note })
    return response.data
  },
  escalate: async (id: string, note?: string) => {
    const response = await api.post(`/exceptions/${id}/escalate`, { resolution_note: note })
    return response.data
  },
  getNotes: async (id: string) => {
    const response = await api.get(`/exceptions/${id}/notes`)
    return response.data
  },
  addNote: async (id: string, content: string) => {
    const response = await api.post(`/exceptions/${id}/notes`, { content })
    return response.data
  },
}

// Reports API
export const reportsApi = {
  create: async (data: { report_type: string; title: string; filters?: any; parameters?: any }) => {
    const response = await api.post('/reports', data)
    return response.data
  },
  list: async (params?: { report_type?: string; status?: string; limit?: number; offset?: number }) => {
    const response = await api.get('/reports', { params })
    return response.data
  },
  get: async (id: string) => {
    const response = await api.get(`/reports/${id}`)
    return response.data
  },
  download: async (id: string) => {
    const response = await api.get(`/reports/${id}/download`, { responseType: 'blob' })
    return response.data
  },
  delete: async (id: string) => {
    await api.delete(`/reports/${id}`)
  },
}

// Anomaly API
export const anomalyApi = {
  list: async (params?: {
    anomaly_type?: string
    severity?: string
    reviewed?: boolean
    limit?: number
    offset?: number
  }) => {
    const response = await api.get('/anomalies', { params })
    return response.data
  },
  get: async (id: string) => {
    const response = await api.get(`/anomalies/${id}`)
    return response.data
  },
  review: async (id: string, note?: string) => {
    const response = await api.post(`/anomalies/${id}/review`, { review_note: note })
    return response.data
  },
  dismiss: async (id: string, note?: string) => {
    const response = await api.post(`/anomalies/${id}/dismiss`, { review_note: note })
    return response.data
  },
}

// AI Explanations API
export const aiApi = {
  requestExceptionExplanation: async (exceptionId: string) => {
    const response = await api.post(`/ai-explanations/exception/${exceptionId}`)
    return response.data
  },
  requestReportExplanation: async (reportId: string) => {
    const response = await api.post(`/ai-explanations/report/${reportId}`)
    return response.data
  },
  requestAnomalyExplanation: async (anomalyId: string) => {
    const response = await api.post(`/ai-explanations/anomaly/${anomalyId}`)
    return response.data
  },
  get: async (id: string) => {
    const response = await api.get(`/ai-explanations/${id}`)
    return response.data
  },
}

// Audit API
export const auditApi = {
  list: async (params?: {
    action_type?: string
    entity_type?: string
    actor_user_id?: string
    limit?: number
    offset?: number
  }) => {
    const response = await api.get('/audit', { params })
    return response.data
  },
  getEntityHistory: async (entityType: string, entityId: string) => {
    const response = await api.get(`/audit/${entityType}/${entityId}`)
    return response.data
  },
}

// Users API
export const usersApi = {
  list: async () => {
    const response = await api.get('/users')
    return response.data
  },
  get: async (id: string) => {
    const response = await api.get(`/users/${id}`)
    return response.data
  },
  create: async (data: any) => {
    const response = await api.post('/users', data)
    return response.data
  },
  update: async (id: string, data: any) => {
    const response = await api.put(`/users/${id}`, data)
    return response.data
  },
  changePassword: async (currentPassword: string, newPassword: string) => {
    const response = await api.post('/users/me/change-password', {
      current_password: currentPassword,
      new_password: newPassword,
    })
    return response.data
  },
}
