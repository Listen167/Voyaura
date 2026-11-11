import AMapLoader from '@amap/amap-jsapi-loader'
import type { CityCandidate } from '../types'

interface AMapPointLike {
  getLng(): number
  getLat(): number
}

interface DistrictItem {
  adcode?: string
  name?: string
  level?: string
  center?: AMapPointLike
}

interface DistrictResult {
  districtList?: DistrictItem[]
}

interface LocalCityResult {
  adcode?: string
  city?: string
  province?: string
  bounds?: {
    getCenter(): AMapPointLike
  }
}

interface GeocoderResult {
  regeocode?: {
    addressComponent?: {
      province?: string
    }
  }
}

type CityServiceRuntime = typeof AMap & {
  CitySearch: new () => {
    getLocalCity(callback: (status: string, result: LocalCityResult | string) => void): void
  }
  DistrictSearch: new (options: Record<string, unknown>) => {
    search(
      keyword: string,
      callback: (status: string, result: DistrictResult | string) => void,
    ): void
  }
  Geocoder: new () => {
    getAddress(
      location: [number, number],
      callback: (status: string, result: GeocoderResult | string) => void,
    ): void
  }
}

async function loadCityServices(): Promise<CityServiceRuntime> {
  const key = import.meta.env.VITE_AMAP_KEY?.trim()
  const securityCode = import.meta.env.VITE_AMAP_SECURITY_CODE?.trim()
  if (!key || !securityCode) {
    throw new Error('AMAP_CONFIG_MISSING')
  }

  window._AMapSecurityConfig = { securityJsCode: securityCode }
  return (await AMapLoader.load({
    key,
    version: '2.0',
    plugins: ['AMap.CitySearch', 'AMap.DistrictSearch', 'AMap.Geocoder'],
  })) as CityServiceRuntime
}

function provinceAt(
  amap: CityServiceRuntime,
  longitude: number,
  latitude: number,
): Promise<string> {
  return new Promise((resolve) => {
    new amap.Geocoder().getAddress([longitude, latitude], (status, result) => {
      if (status !== 'complete' || typeof result === 'string') {
        resolve('中国')
        return
      }
      resolve(result.regeocode?.addressComponent?.province || '中国')
    })
  })
}

function coordinates(point?: AMapPointLike): [number, number] | null {
  if (!point) return null
  const longitude = point.getLng()
  const latitude = point.getLat()
  return Number.isFinite(longitude) && Number.isFinite(latitude)
    ? [longitude, latitude]
    : null
}

export async function locateCityByIp(): Promise<CityCandidate> {
  const amap = await loadCityServices()
  return new Promise((resolve, reject) => {
    new amap.CitySearch().getLocalCity((status, result) => {
      if (status !== 'complete' || typeof result === 'string') {
        reject(new Error('AMAP_IP_CITY_FAILED'))
        return
      }
      const center = coordinates(result.bounds?.getCenter())
      if (!result.adcode || !result.city || !center) {
        reject(new Error('AMAP_IP_CITY_INVALID'))
        return
      }
      resolve({
        adcode: result.adcode,
        city_name: result.city,
        province_name: result.province || result.city,
        longitude: center[0],
        latitude: center[1],
        source: 'ip',
      })
    })
  })
}

export async function searchCities(keyword: string): Promise<CityCandidate[]> {
  const query = keyword.trim()
  if (query.length < 2) return []

  const amap = await loadCityServices()
  return new Promise((resolve, reject) => {
    const districtSearch = new amap.DistrictSearch({
      level: 'city',
      subdistrict: 0,
      extensions: 'base',
      showbiz: false,
    })
    districtSearch.search(query, async (status, result) => {
      if (status !== 'complete' || typeof result === 'string') {
        reject(new Error('AMAP_CITY_SEARCH_FAILED'))
        return
      }
      const candidates = (result.districtList ?? [])
        .map((item): CityCandidate | null => {
          const center = coordinates(item.center)
          if (!item.adcode || !item.name || !center) return null
          return {
            adcode: item.adcode,
            city_name: item.name,
            province_name: item.level === 'province' ? item.name : '中国',
            longitude: center[0],
            latitude: center[1],
            source: 'manual',
          }
        })
        .filter((item): item is CityCandidate => item !== null)
      const enriched = await Promise.all(
        candidates.slice(0, 8).map(async (candidate) => ({
          ...candidate,
          province_name: await provinceAt(amap, candidate.longitude, candidate.latitude),
        })),
      )
      resolve(enriched)
    })
  })
}
