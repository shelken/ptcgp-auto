import { buildQuery } from '../../lib/api'

export function buildAccountPlansQuery(lang: string) {
  return buildQuery({ lang })
}

export function buildPackConfigQuery(lang: string) {
  return buildQuery({ lang })
}

export function buildPlanEditorQuery(lang: string, planId: number | null) {
  return buildQuery({ lang, plan_id: planId ?? undefined })
}

export function buildTaskAccountOptionsQuery(keyword: string) {
  const normalized = keyword.trim()
  return buildQuery({ q: normalized || undefined })
}
