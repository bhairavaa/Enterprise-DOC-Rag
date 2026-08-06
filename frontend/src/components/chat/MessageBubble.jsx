import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import CitationPanel from './CitationPanel'

export default function MessageBubble({ role, content, citations }) {
  const isUser = role === 'user'

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-2xl rounded-lg px-4 py-2.5 text-sm ${
          isUser
            ? 'bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900'
            : 'bg-slate-100 text-slate-900 dark:bg-slate-800 dark:text-slate-100'
        }`}
      >
        {isUser ? (
          <p className="whitespace-pre-wrap">{content}</p>
        ) : (
          <div className="prose prose-sm prose-slate max-w-none dark:prose-invert prose-p:my-1.5">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{content || '…'}</ReactMarkdown>
          </div>
        )}
        {!isUser && <CitationPanel citations={citations} />}
      </div>
    </div>
  )
}
