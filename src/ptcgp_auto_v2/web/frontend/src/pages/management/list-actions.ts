export function buildManagementListActionPayload({
  params,
  fields,
  missingValue
}: {
  params: Record<string, unknown>
  fields: string[]
  missingValue?: unknown
}): Record<string, unknown> {
  const payload: Record<string, unknown> = {}
  for (const field of fields) {
    const value = params[field]
    payload[field] = value === undefined ? missingValue : value
  }
  return payload
}
