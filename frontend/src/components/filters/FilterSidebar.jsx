import { useQuery } from '@tanstack/react-query'
import { getFacets } from '../../api/filters'
import { useAuthStore } from '../../store/authStore'
import { useFilterStore } from '../../store/filterStore'

function FacetGroup({ title, values, selected, onToggle }) {
  if (!values?.length) return null
  return (
    <div className="mb-4">
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
        {title}
      </h3>
      <div className="flex flex-col gap-1.5">
        {values.map((value) => (
          <label key={value} className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={selected.includes(value)}
              onChange={() => onToggle(value)}
              className="h-3.5 w-3.5 rounded border-slate-300 text-slate-900 focus:ring-slate-500 dark:border-slate-600 dark:bg-slate-800"
            />
            <span className="text-slate-700 dark:text-slate-300">{value}</span>
          </label>
        ))}
      </div>
    </div>
  )
}

export default function FilterSidebar() {
  const apiKey = useAuthStore((s) => s.apiKey)
  const { department, docType, tags, toggleDepartment, toggleDocType, toggleTag, clearFilters } =
    useFilterStore()

  const { data: facets } = useQuery({
    queryKey: ['facets', apiKey],
    queryFn: () => getFacets(),
    enabled: Boolean(apiKey),
  })

  const hasActiveFilters = department.length + docType.length + tags.length > 0

  return (
    <aside className="w-56 shrink-0 border-r border-slate-200 px-4 py-4 dark:border-slate-800">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold">Filters</h2>
        {hasActiveFilters && (
          <button
            type="button"
            onClick={clearFilters}
            className="text-xs text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
          >
            Clear
          </button>
        )}
      </div>
      <FacetGroup
        title="Department"
        values={facets?.department}
        selected={department}
        onToggle={toggleDepartment}
      />
      <FacetGroup
        title="Doc type"
        values={facets?.doc_type}
        selected={docType}
        onToggle={toggleDocType}
      />
      <FacetGroup title="Tags" values={facets?.tags} selected={tags} onToggle={toggleTag} />
      {!facets?.department?.length && !facets?.doc_type?.length && !facets?.tags?.length && (
        <p className="text-xs text-slate-400">No facets yet — ingest some documents first.</p>
      )}
    </aside>
  )
}
