import { fetchEventSource } from '@microsoft/fetch-event-source'
import { API_BASE } from './client'
import { useAuthStore } from '../store/authStore'

/**
 * Streams a chat response. Calls onCitations once with the parsed citation
 * list, onToken for each streamed text delta, and onDone when the stream
 * finishes (cached: boolean). Returns an AbortController the caller can use
 * to cancel the stream early.
 */
export function streamChat({
  query,
  conversationId,
  department,
  docType,
  tags,
  onConversation,
  onCitations,
  onToken,
  onDone,
  onError,
}) {
  const controller = new AbortController()
  const apiKey = useAuthStore.getState().apiKey

  fetchEventSource(`${API_BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-API-Key': apiKey },
    body: JSON.stringify({
      query,
      conversation_id: conversationId ?? null,
      department: department?.length ? department : null,
      doc_type: docType?.length ? docType : null,
      tags: tags?.length ? tags : null,
    }),
    signal: controller.signal,
    openWhenHidden: true,
    async onopen(response) {
      if (!response.ok) {
        throw new Error(`Chat stream failed: ${response.status}`)
      }
    },
    onmessage(event) {
      const data = event.data ? JSON.parse(event.data) : null
      if (event.event === 'conversation') {
        onConversation?.(data?.id)
      } else if (event.event === 'citations') {
        onCitations?.(data ?? [])
      } else if (event.event === 'token') {
        onToken?.(data ?? '')
      } else if (event.event === 'done') {
        onDone?.(data ?? {})
      }
    },
    onerror(err) {
      onError?.(err)
      throw err // stop fetch-event-source's automatic retry
    },
  })

  return controller
}
