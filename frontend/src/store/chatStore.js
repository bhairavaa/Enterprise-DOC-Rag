import { create } from 'zustand'

export const useChatStore = create((set) => ({
  conversationId: null,
  messages: [], // { role: 'user' | 'assistant', content: string, citations?: [] }
  isStreaming: false,
  streamingText: '',
  streamingCitations: [],

  setConversationId: (id) => set({ conversationId: id }),
  loadMessages: (messages) => set({ messages }),
  startNewConversation: () =>
    set({ conversationId: null, messages: [], streamingText: '', streamingCitations: [] }),

  submitUserMessage: (query) =>
    set((s) => ({
      messages: [...s.messages, { role: 'user', content: query }],
      isStreaming: true,
      streamingText: '',
      streamingCitations: [],
    })),

  appendToken: (token) => set((s) => ({ streamingText: s.streamingText + token })),
  setStreamingCitations: (citations) => set({ streamingCitations: citations }),

  finishStreaming: () =>
    set((s) => ({
      messages: [
        ...s.messages,
        { role: 'assistant', content: s.streamingText, citations: s.streamingCitations },
      ],
      isStreaming: false,
      streamingText: '',
      streamingCitations: [],
    })),
}))
