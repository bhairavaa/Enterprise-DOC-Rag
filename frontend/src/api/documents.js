import { apiDelete, apiGet, apiPostForm } from './client'

export function listDocuments() {
  return apiGet('/documents')
}

export function deleteDocument(documentId) {
  return apiDelete(`/documents/${documentId}`)
}

export function uploadDocument(file, { department, docType, tags } = {}) {
  const formData = new FormData()
  formData.append('file', file)
  if (department) formData.append('department', department)
  if (docType) formData.append('doc_type', docType)
  if (tags) formData.append('tags', tags)
  return apiPostForm('/documents/upload', formData)
}
