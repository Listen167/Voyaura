/// <reference types="vite/client" />
/// <reference types="@amap/amap-jsapi-types" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string
  readonly VITE_AMAP_KEY?: string
  readonly VITE_AMAP_SECURITY_CODE?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

interface Window {
  _AMapSecurityConfig?: {
    securityJsCode: string
  }
  Loca?: {
    Container: new (options: { map: AMap.Map }) => {
      add(layer: unknown): void
      destroy(): void
    }
    GeoJSONSource: new (options: { data: GeoJSON.FeatureCollection }) => unknown
    PointLayer: new (options: Record<string, unknown>) => {
      setSource(source: unknown): void
      setStyle(style: Record<string, unknown>): void
    }
  }
}

declare namespace GeoJSON {
  interface Point {
    type: 'Point'
    coordinates: [number, number]
  }

  interface Feature {
    type: 'Feature'
    properties: Record<string, unknown>
    geometry: Point
  }

  interface FeatureCollection {
    type: 'FeatureCollection'
    features: Feature[]
  }
}
