export function tr(t: Record<string, string>, key: string, fallback: string): string {
  return t[key] ?? fallback
}
