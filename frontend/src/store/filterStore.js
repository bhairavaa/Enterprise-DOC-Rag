import { create } from 'zustand'

function toggleValue(list, value) {
  return list.includes(value) ? list.filter((v) => v !== value) : [...list, value]
}

export const useFilterStore = create((set) => ({
  department: [],
  docType: [],
  tags: [],
  toggleDepartment: (value) => set((s) => ({ department: toggleValue(s.department, value) })),
  toggleDocType: (value) => set((s) => ({ docType: toggleValue(s.docType, value) })),
  toggleTag: (value) => set((s) => ({ tags: toggleValue(s.tags, value) })),
  clearFilters: () => set({ department: [], docType: [], tags: [] }),
}))
