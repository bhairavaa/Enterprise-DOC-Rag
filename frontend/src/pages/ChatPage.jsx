import { useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import { streamChat } from '../api/chat'
import ChatInput from '../components/chat/ChatInput'
import MessageBubble from '../components/chat/MessageBubble'
import ConversationHistory from '../components/conversations/ConversationHistory'
import FilterSidebar from '../components/filters/FilterSidebar'
import { useAuthStore } from '../store/authStore'
import { useChatStore } from '../store/chatStore'
import { useFilterStore } from '../store/filterStore'

export default function ChatPage() {
  const apiKey = useAuthStore((s) => s.apiKey)
  const { department, docType, tags } = useFilterStore()
  const {
    conversationId,
    messages,
    isStreaming,
    streamingText,
    streamingCitations,
    setConversationId,
    submitUserMessage,
    appendToken,
    setStreamingCitations,
    finishStreaming,
  } = useChatStore()

  const scrollRef = useRef(null)

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingText])

  function handleSend(query) {
    submitUserMessage(query)

    streamChat({
      query,
      conversationId,
      department,
      docType,
      tags,
      onConversation: (id) => {
        if (id && id !== conversationId) setConversationId(id)
      },
      onCitations: setStreamingCitations,
      onToken: appendToken,
      onDone: finishStreaming,
      onError: (err) => {
        console.error('Chat stream error', err)
        finishStreaming()
      },
    })
  }

  if (!apiKey) {
    return (
      <div className="flex h-[calc(100vh-4.5rem)] flex-col items-center justify-center rounded-lg border border-dashed border-slate-300 text-sm text-slate-400 dark:border-slate-700">
        <p>
          Set an API key in{' '}
          <Link to="/settings" className="underline">
            Settings
          </Link>{' '}
          to start chatting.
        </p>
      </div>
    )
  }

  return (
    <div className="flex h-[calc(100vh-4.5rem)] gap-0 overflow-hidden rounded-lg border border-slate-200 dark:border-slate-800">
      <FilterSidebar />

      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="flex-1 space-y-3 overflow-y-auto p-4">
          {messages.length === 0 && !isStreaming && (
            <p className="text-center text-sm text-slate-400">
              Ask a question about your ingested documents.
            </p>
          )}
          {messages.map((message, i) => (
            <MessageBubble key={i} {...message} />
          ))}
          {isStreaming && (
            <MessageBubble
              role="assistant"
              content={streamingText}
              citations={streamingCitations}
            />
          )}
          <div ref={scrollRef} />
        </div>
        <ChatInput onSubmit={handleSend} disabled={isStreaming} />
      </div>

      <ConversationHistory />
    </div>
  )
}
