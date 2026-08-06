import { useState } from 'react'
import { useAuthStore } from '../store/authStore'

export default function SettingsPage() {
  const { apiKey, setApiKey } = useAuthStore()
  const [draft, setDraft] = useState(apiKey)

  function handleSubmit(e) {
    e.preventDefault()
    setApiKey(draft.trim())
  }

  return (
    <div className="max-w-md rounded-lg border border-slate-200 p-6 dark:border-slate-800">
      <h2 className="mb-1 text-sm font-semibold">API key</h2>
      <p className="mb-4 text-xs text-slate-500">
        Every request is scoped to whichever tenant this key belongs to — tenant, department, and
        tag access are all determined server-side by the key, never by anything sent from the
        browser. Ask an admin to issue one via <code>POST /api/v1/auth/api-keys</code>.
      </p>
      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          type="password"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="edr_..."
          className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900"
        />
        <button
          type="submit"
          className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white dark:bg-slate-100 dark:text-slate-900"
        >
          Save
        </button>
      </form>
      <p className="mt-3 text-xs text-slate-400">
        {apiKey ? `Active key: ${apiKey.slice(0, 12)}…` : 'No API key set.'}
      </p>
    </div>
  )
}
