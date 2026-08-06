import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { getConversationMessages, listConversations, renameConversation } from '../../api/conversations'
import { useAuthStore } from '../../store/authStore'
import { useChatStore } from '../../store/chatStore'

export default function ConversationHistory() {
  const apiKey = useAuthStore((s) => s.apiKey)
  const { conversationId, setConversationId, loadMessages, startNewConversation } = useChatStore()
  const queryClient = useQueryClient()
  const [editingId, setEditingId] = useState(null)
  const [draftTitle, setDraftTitle] = useState('')

  const { data: conversations, refetch } = useQuery({
    queryKey: ['conversations', apiKey],
    queryFn: () => listConversations(),
    enabled: Boolean(apiKey),
  })

  async function openConversation(id) {
    setConversationId(id)
    const messages = await getConversationMessages(id)
    loadMessages(
      messages.map((m) => ({ role: m.role, content: m.content, citations: m.citations ?? [] })),
    )
  }

  function handleNewConversation() {
    startNewConversation()
    refetch()
  }

  function startEditing(conversation, e) {
    e.stopPropagation()
    setEditingId(conversation.id)
    setDraftTitle(conversation.title || '')
  }

  async function commitEdit(id) {
    setEditingId(null)
    await renameConversation(id, draftTitle)
    queryClient.invalidateQueries({ queryKey: ['conversations', apiKey] })
  }

  function handleEditKeyDown(e) {
    if (e.key === 'Enter') {
      e.preventDefault()
      e.currentTarget.blur()
    } else if (e.key === 'Escape') {
      e.preventDefault()
      setEditingId(null)
    }
  }

  return (
    <aside className="w-56 shrink-0 border-l border-slate-200 px-4 py-4 dark:border-slate-800">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold">Conversations</h2>
        <button
          type="button"
          onClick={handleNewConversation}
          className="text-xs text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
        >
          + New
        </button>
      </div>
      <div className="flex flex-col gap-1">
        {conversations?.map((conversation) => (
          <div
            key={conversation.id}
            className={`group flex items-center gap-1 rounded-md px-2 py-1.5 text-xs ${
              conversation.id === conversationId
                ? 'bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900'
                : 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800'
            }`}
          >
            {editingId === conversation.id ? (
              <input
                autoFocus
                value={draftTitle}
                maxLength={100}
                onChange={(e) => setDraftTitle(e.target.value)}
                onBlur={() => commitEdit(conversation.id)}
                onKeyDown={handleEditKeyDown}
                onClick={(e) => e.stopPropagation()}
                className="w-full rounded border border-slate-400 bg-white px-1 py-0.5 text-xs text-slate-900 outline-none dark:bg-slate-950 dark:text-slate-100"
              />
            ) : (
              <>
                <button
                  type="button"
                  onClick={() => openConversation(conversation.id)}
                  className="min-w-0 flex-1 truncate text-left"
                >
                  {conversation.title || 'Untitled conversation'}
                </button>
                <button
                  type="button"
                  onClick={(e) => startEditing(conversation, e)}
                  title="Rename"
                  className="shrink-0 opacity-0 group-hover:opacity-100"
                >
                  ✎
                </button>
              </>
            )}
          </div>
        ))}
        {!conversations?.length && (
          <p className="text-xs text-slate-400">No conversations yet.</p>
        )}
      </div>
    </aside>
  )
}
