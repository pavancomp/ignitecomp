import axios from 'axios'

const api = axios.create({ baseURL: 'https://ignitecomp.onrender.com/api/v1' })

api.interceptors.request.use(config => {
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  r => r,
  async err => {
    if (err.response?.status === 401) {
      const refresh = localStorage.getItem('refresh_token')
      if (refresh) {
        try {
          const res = await axios.post('/api/v1/auth/refresh', { refresh_token: refresh })
          localStorage.setItem('access_token', res.data.access_token)
          localStorage.setItem('refresh_token', res.data.refresh_token)
          err.config.headers.Authorization = `Bearer ${res.data.access_token}`
          return api(err.config)
        } catch {
          localStorage.clear()
          window.location.href = '/login'
        }
      }
    }
    return Promise.reject(err)
  }
)

export default api

// ── Helpers ────────────────────────────────────────────────────────────────

export const auth = {
  login: (username, password) => {
    const form = new URLSearchParams({ username, password })
    return axios.post('https://ignitecomp.onrender.com/api/v1/auth/token', form, { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } })
  },
  me: () => api.get('/auth/me'),
}

export const distributors = {
  list: (params) => api.get('/distributors', { params }),
  get: (id) => api.get(`/distributors/${id}`),
  create: (data) => api.post('/distributors', data),
  update: (id, data) => api.patch(`/distributors/${id}`, data),
  getCenters: (id) => api.get(`/distributors/${id}/centers`),
  activateCenters: (id, params) => api.post(`/distributors/${id}/centers`, null, { params }),
  tree: () => api.get('/distributors/tree/nodes'),
  getOrders: (id) => api.get(`/distributors/${id}/orders`),
  addOrder: (id, params) => api.post(`/distributors/${id}/orders`, null, { params }),
}

export const products = {
  list: () => api.get('/config/products'),
}

export const orders = {
  list: (params) => api.get('/orders', { params }),
  create: (data) => api.post('/orders', data),
  verify: (id) => api.post(`/orders/${id}/verify`),
  bulkVerify: (ids) => api.post('/orders/bulk-verify', ids),
}

export const cycles = {
  list: (params) => api.get('/cycles', { params }),
  get: (id) => api.get(`/cycles/${id}`),
  create: (data) => api.post('/cycles', data),
  close: (id) => api.post(`/cycles/${id}/close`),
  approve: (id) => api.post(`/cycles/${id}/approve`),
  commissions: (id, params) => api.get(`/cycles/${id}/commissions`, { params }),
}

export const compliance = {
  tdsReport: (fy) => api.get('/compliance/tds-report', { params: { financial_year: fy } }),
  gstFlags: (fy) => api.get('/compliance/gst-flags', { params: { financial_year: fy } }),
  wallet: (id, fy) => api.get(`/compliance/wallet/${id}`, { params: { financial_year: fy } }),
}

export const config = {
  getPlan: () => api.get('/config/plan'),
  updatePlan: (data) => api.patch('/config/plan', data),
  getRanks: () => api.get('/config/ranks'),
  updateRank: (id, data) => api.patch(`/config/ranks/${id}`, data),
}

export const sync = {
  ecom: (cycle_id, since) => api.post('/sync/ecom-orders', null, { params: { cycle_id, since } }),
  crm: (since) => api.post('/sync/crm-distributors', null, { params: { since } }),
}
