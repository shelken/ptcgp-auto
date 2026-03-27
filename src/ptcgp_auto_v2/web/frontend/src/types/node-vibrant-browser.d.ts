declare module 'node-vibrant/browser' {
  export interface VibrantSwatch {
    rgb: [number, number, number]
  }

  export interface VibrantPalette {
    Vibrant?: VibrantSwatch | null
    LightVibrant?: VibrantSwatch | null
    DarkVibrant?: VibrantSwatch | null
    Muted?: VibrantSwatch | null
    LightMuted?: VibrantSwatch | null
    DarkMuted?: VibrantSwatch | null
  }

  export interface VibrantBuilder {
    getPalette(): Promise<VibrantPalette>
  }

  export const Vibrant: {
    from(source: string | HTMLImageElement): VibrantBuilder
  }
}
