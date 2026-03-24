declare module '*.css'

declare global {
  interface Window {
    htmx?: {
      process: (node: Element) => void
      trigger: (node: Element, eventName: string) => void
    }
  }
}

export {}
