import { apiGet } from './client'

export function getFacets() {
  return apiGet('/filters/facets')
}
