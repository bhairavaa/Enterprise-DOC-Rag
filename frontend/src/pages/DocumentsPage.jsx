import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { deleteDocument, listDocuments, uploadDocument } from '../api/documents'
import { useAuthStore } from '../store/authStore'

const STATUS_STYLES = {
  completed: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300',
  processing: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300',
  queued: 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300',
  failed: 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300',
  deleted: 'bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400',
}

const IN_FLIGHT_STATUSES = new Set(['queued', 'processing'])

// How long to keep polling after any upload, on top of the "a row is
// currently processing" check. Covers two gaps a pure status-based check
// misses: the task sitting in the Celery/Redis queue before a row exists
// at all, and the moment between one queued file finishing and the next
// one's row appearing (the --pool=solo worker processes one at a time, so
// back-to-back uploads queue up) -- both can otherwise land exactly between
// polls and silently stop refreshing until a manual reload.
const UPLOAD_POLL_GRACE_MS = 15000

export default function DocumentsPage() {
  const apiKey = useAuthStore((s) => s.apiKey)
  const queryClient = useQueryClient()
  const [department, setDepartment] = useState('')
  const [docType, setDocType] = useState('')
  const [tags, setTags] = useState('')
  const [file, setFile] = useState(null)
  const [pollUntil, setPollUntil] = useState(0)

  const { data: documents, isLoading } = useQuery({
    queryKey: ['documents', apiKey],
    queryFn: () => listDocuments(),
    enabled: Boolean(apiKey),
    // Ingestion runs asynchronously in a Celery worker (see backend
    // app/worker/tasks.py) — poll so newly-uploaded rows and their status
    // (queued -> processing -> completed) show up without a manual refresh.
    refetchInterval: (query) => {
      const hasInFlightRow = query.state.data?.some((d) => IN_FLIGHT_STATUSES.has(d.status))
      return hasInFlightRow || Date.now() < pollUntil ? 2000 : false
    },
  })

  const uploadMutation = useMutation({
    mutationFn: () => uploadDocument(file, { department, docType, tags }),
    onSuccess: () => {
      setFile(null)
      setPollUntil(Date.now() + UPLOAD_POLL_GRACE_MS)
      queryClient.invalidateQueries({ queryKey: ['documents', apiKey] })
      queryClient.invalidateQueries({ queryKey: ['facets', apiKey] })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (documentId) => deleteDocument(documentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents', apiKey] })
      queryClient.invalidateQueries({ queryKey: ['facets', apiKey] })
    },
  })

  function handleSubmit(e) {
    e.preventDefault()
    if (!file) return
    uploadMutation.mutate()
  }

  function handleDelete(doc) {
    if (window.confirm(`Delete "${doc.file_name}"? This removes it from the index and can't be undone.`)) {
      deleteMutation.mutate(doc.id)
    }
  }

  if (!apiKey) {
    return (
      <div className="flex h-[calc(100vh-8rem)] flex-col items-center justify-center rounded-lg border border-dashed border-slate-300 text-sm text-slate-400 dark:border-slate-700">
        <p>
          Set an API key in{' '}
          <Link to="/settings" className="underline">
            Settings
          </Link>{' '}
          to manage documents.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <form
        onSubmit={handleSubmit}
        className="flex flex-wrap items-end gap-3 rounded-lg border border-slate-200 p-4 dark:border-slate-800"
      >
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-slate-500">File</label>
          <input
            type="file"
            accept=".pdf,.docx,.pptx"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="text-sm"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-slate-500">Department</label>
          <input
            value={department}
            onChange={(e) => setDepartment(e.target.value)}
            placeholder="engineering"
            className="rounded-md border border-slate-300 px-2 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-900"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-slate-500">Doc type</label>
          <input
            value={docType}
            onChange={(e) => setDocType(e.target.value)}
            placeholder="policies"
            className="rounded-md border border-slate-300 px-2 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-900"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-slate-500">Tags (comma-separated)</label>
          <input
            value={tags}
            onChange={(e) => setTags(e.target.value)}
            placeholder="hr, onboarding"
            className="rounded-md border border-slate-300 px-2 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-900"
          />
        </div>
        <button
          type="submit"
          disabled={!file || uploadMutation.isPending}
          className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-40 dark:bg-slate-100 dark:text-slate-900"
        >
          {uploadMutation.isPending ? 'Ingesting…' : 'Upload & ingest'}
        </button>
        {uploadMutation.isError && (
          <p className="w-full text-xs text-red-500">{uploadMutation.error.message}</p>
        )}
        {uploadMutation.isSuccess && (
          <p className="w-full text-xs text-emerald-600">
            Queued — it'll appear below immediately and update as ingestion progresses.
          </p>
        )}
      </form>

      <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-800">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-slate-200 text-xs uppercase text-slate-500 dark:border-slate-800">
            <tr>
              <th className="px-4 py-2">File</th>
              <th className="px-4 py-2">Department</th>
              <th className="px-4 py-2">Doc type</th>
              <th className="px-4 py-2">Tags</th>
              <th className="px-4 py-2">Version</th>
              <th className="px-4 py-2">Chunks</th>
              <th className="px-4 py-2">Status</th>
              <th className="px-4 py-2" />
            </tr>
          </thead>
          <tbody>
            {documents?.map((doc) => (
              <tr key={doc.id} className="border-b border-slate-100 dark:border-slate-900">
                <td className="px-4 py-2 font-medium">{doc.file_name}</td>
                <td className="px-4 py-2 text-slate-500">{doc.department ?? '—'}</td>
                <td className="px-4 py-2 text-slate-500">{doc.doc_type ?? '—'}</td>
                <td className="px-4 py-2 text-slate-500">{doc.tags?.join(', ') || '—'}</td>
                <td className="px-4 py-2 text-slate-500">v{doc.current_version}</td>
                <td className="px-4 py-2 text-slate-500">{doc.num_chunks}</td>
                <td className="px-4 py-2">
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs ${STATUS_STYLES[doc.status] ?? ''}`}
                  >
                    {doc.status}
                  </span>
                </td>
                <td className="px-4 py-2 text-right">
                  <button
                    type="button"
                    onClick={() => handleDelete(doc)}
                    disabled={deleteMutation.isPending && deleteMutation.variables === doc.id}
                    className="text-xs text-slate-400 hover:text-red-600 disabled:opacity-40 dark:hover:text-red-400"
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!isLoading && !documents?.length && (
          <p className="p-4 text-center text-sm text-slate-400">
            No documents ingested yet for this tenant.
          </p>
        )}
      </div>
    </div>
  )
}
