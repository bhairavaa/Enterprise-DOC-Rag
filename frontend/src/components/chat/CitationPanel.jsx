function locationLabel(citation) {
  if (citation.page_label) return `page ${citation.page_label}`
  if (citation.slide_number) return `slide ${citation.slide_number}`
  if (citation.section_title) return citation.section_title
  return null
}

export default function CitationPanel({ citations }) {
  if (!citations?.length) return null

  return (
    <div className="mt-2 flex flex-col gap-2 border-t border-slate-200 pt-2 dark:border-slate-800">
      {citations.map((citation) => (
        <div
          key={citation.index}
          id={`citation-${citation.index}`}
          className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-xs dark:border-slate-800 dark:bg-slate-900"
        >
          <div className="mb-1 flex items-center gap-1.5 font-medium text-slate-600 dark:text-slate-300">
            <span className="rounded bg-slate-900 px-1.5 py-0.5 text-[10px] text-white dark:bg-slate-100 dark:text-slate-900">
              {citation.index}
            </span>
            <span>{citation.source_file ?? 'Unknown source'}</span>
            {locationLabel(citation) && (
              <span className="text-slate-400">· {locationLabel(citation)}</span>
            )}
          </div>
          <p className="line-clamp-3 text-slate-500 dark:text-slate-400">{citation.text}</p>
        </div>
      ))}
    </div>
  )
}
