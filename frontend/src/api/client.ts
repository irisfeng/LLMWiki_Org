import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

// Inject auth token into every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Redirect to /login on 401
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      // Rewrite the message so any caller that surfaces error.message
      // shows something intelligible while the redirect happens.
      error.message = '登录已过期，请重新登录'
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export default api
