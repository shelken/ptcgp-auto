export interface BootstrapOptions {
  rarities: string[]
  card_types: string[]
  elements: string[]
  card_sets: Array<{ code: string; display_name: string }>
  packs: Array<{ name: string; display_name: string }>
}

export interface BootstrapResponse {
  lang: string
  t: Record<string, string>
  options: BootstrapOptions
  assets: {
    card_proxy_base_url: string
    card_cdn_base_url: string
  }
}
