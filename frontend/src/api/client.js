import { useAuthStore } from '../store/authStore'

export const API_BASE = '/api/v1'

function authHeaders() {
  const apiKey = useAuthStore.getState().apiKey
  return apiKey ? { 'X-API-Key': apiKey } : {}
}

export async function apiGet(path, params = {}) {
  const query = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ''),
  ).toString()
  const url = `${API_BASE}${path}${query ? `?${query}` : ''}`
  const response = await fetch(url, { headers: authHeaders() })
  if (!response.ok) {
    throw new Error(`GET ${path} failed: ${response.status}`)
  }
  return response.json()
}

export async function apiPost(path, body) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(body),
  })
  if (!response.ok) {
    throw new Error(`POST ${path} failed: ${response.status}`)
  }
  return response.json()
}

export async function apiPatch(path, body) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(body),
  })
  if (!response.ok) {
    throw new Error(`PATCH ${path} failed: ${response.status}`)
  }
  return response.json()
}

export async function apiDelete(path) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'DELETE',
    headers: authHeaders(),
  })
  if (!response.ok) {
    throw new Error(`DELETE ${path} failed: ${response.status}`)
  }
  return response.json()
}

export async function apiPostForm(path, formData) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: authHeaders(),
    body: formData,
  })
  if (!response.ok) {
    throw new Error(`POST ${path} failed: ${response.status}`)
  }
  return response.json()
}
