import { apiGet, apiPatch } from './client'

export function listConversations() {
  return apiGet('/conversations')
}

export function getConversationMessages(conversationId) {
  return apiGet(`/conversations/${conversationId}/messages`)
}

export function renameConversation(conversationId, title) {
  return apiPatch(`/conversations/${conversationId}`, { title })
}
