<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import { getReachabilityArea, type ReachabilityArea } from '@/api/platformClient'
import { LIFE_CIRCLE_SERVICES } from '@/data/memberDemoContent'

const ORIGIN_ID = 'venue-huanan-bank-conference-center'
const originLabel = '華南銀行國際會議中心・臺北市信義區松仁路 123 號'
const travelMode = ref<'pedestrian' | 'scooter'>('pedestrian')
const thresholdMinutes = ref<10 | 15>(10)
const area = ref<ReachabilityArea | null>(null)
const loading = ref(false)
const error = ref('')
const locationState = ref<'idle' | 'requesting' | 'granted' | 'denied'>('idle')
const locationMessage = ref('')
const ORIGIN_POINT = { lon: 121.5654, lat: 25.0339 }
const LOCATION_POINTS: Record<string, { lon: number; lat: number }> = {
  'loc-01-01': { lon: 121.5588, lat: 25.0353 },
  'loc-02-01': { lon: 121.5668, lat: 25.0347 },
  'loc-03-01': { lon: 121.5708, lat: 25.0362 },
  'loc-08-01': { lon: 121.5762, lat: 25.0382 },
  'loc-09-01': { lon: 121.5810, lat: 25.0317 },
}

type Coordinate = [number, number]

const polygonCoordinates = computed<Coordinate[]>(() => {
  const coordinates = (area.value?.geometry as { coordinates?: unknown } | undefined)?.coordinates
  if (!Array.isArray(coordinates) || !Array.isArray(coordinates[0])) return []
  return (coordinates[0] as unknown[]).filter((point): point is Coordinate => (
    Array.isArray(point) && typeof point[0] === 'number' && typeof point[1] === 'number'
  ))
})

const mapBounds = computed(() => {
  const points = [...polygonCoordinates.value, [ORIGIN_POINT.lon, ORIGIN_POINT.lat] as Coordinate]
  const longs = points.map((point) => point[0])
  const lats = points.map((point) => point[1])
  const minLon = Math.min(...longs, ORIGIN_POINT.lon - 0.002)
  const maxLon = Math.max(...longs, ORIGIN_POINT.lon + 0.002)
  const minLat = Math.min(...lats, ORIGIN_POINT.lat - 0.002)
  const maxLat = Math.max(...lats, ORIGIN_POINT.lat + 0.002)
  return { minLon, maxLon, minLat, maxLat }
})

function project(point: { lon: number; lat: number }) {
  const bounds = mapBounds.value
  const x = ((point.lon - bounds.minLon) / (bounds.maxLon - bounds.minLon)) * 100
  const y = 100 - ((point.lat - bounds.minLat) / (bounds.maxLat - bounds.minLat)) * 100
  return { x: Math.round(x * 10) / 10, y: Math.round(y * 10) / 10 }
}

const polygonPoints = computed(() => polygonCoordinates.value.map(([lon, lat]) => {
  const point = project({ lon, lat })
  return `${point.x},${point.y}`
}).join(' '))

const originMarker = computed(() => project(ORIGIN_POINT))
const osmUrl = 'https://www.openstreetmap.org/?mlat=25.0339&mlon=121.5654#map=15/25.0339/121.5654'

const reachableServices = computed(() => {
  const providers = new Set(area.value?.locations.map((location) => location.providerId) ?? [])
  return LIFE_CIRCLE_SERVICES.filter((service) => providers.has(service.providerId))
})

function locationMarker(id: string) {
  return project(LOCATION_POINTS[id] ?? ORIGIN_POINT)
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    area.value = await getReachabilityArea({
      originId: ORIGIN_ID,
      travelMode: travelMode.value,
      thresholdMinutes: thresholdMinutes.value,
    })
  } catch (reason) {
    area.value = null
    error.value = reason instanceof Error ? reason.message : '目前無法載入生活圈資料。'
  } finally {
    loading.value = false
  }
}

function requestSingleUseLocation() {
  if (!navigator.geolocation) {
    locationState.value = 'denied'
    locationMessage.value = '這個瀏覽器不支援定位；目前仍使用會場固定起點。'
    return
  }
  locationState.value = 'requesting'
  locationMessage.value = ''
  navigator.geolocation.getCurrentPosition(
    (position) => {
      // The coordinate is intentionally not assigned anywhere or sent to the API.
      void position
      locationState.value = 'granted'
      locationMessage.value = '已取得這次頁面的單次定位；座標不會保存，生活圈仍以會場固定起點計算。'
    },
    () => {
      locationState.value = 'denied'
      locationMessage.value = '未取得定位；沒有保存座標，生活圈仍以會場固定起點計算。'
    },
    { enableHighAccuracy: false, maximumAge: 0, timeout: 10000 },
  )
}

watch([travelMode, thresholdMinutes], () => void load())
onMounted(() => void load())
</script>

<template>
  <section class="member-page reachability-page" data-testid="reachability-page">
    <header class="page-heading">
      <p class="eyebrow">Demo 生活圈</p>
      <h1>從會場找生活服務</h1>
      <p class="page-lead">只顯示會員前往 Provider／Location 的時間可達範圍；到府服務使用另一套 Provider Service Area 判斷。</p>
    </header>

    <section class="panel reachability-controls" aria-labelledby="reachability-controls-title">
      <h2 id="reachability-controls-title">起點與條件</h2>
      <p><strong>起點</strong>：{{ originLabel }}</p>
      <div class="reachability-control-grid">
        <label>
          <span>交通方式</span>
          <select v-model="travelMode" data-testid="reachability-mode">
            <option value="pedestrian">步行</option>
            <option value="scooter">機車</option>
          </select>
        </label>
        <label>
          <span>時間門檻</span>
          <select v-model.number="thresholdMinutes" data-testid="reachability-threshold">
            <option :value="10">10 分鐘</option>
            <option :value="15">15 分鐘</option>
          </select>
        </label>
      </div>
      <div class="location-consent">
        <button
          type="button"
          class="button secondary inline"
          data-testid="single-use-location"
          :disabled="locationState === 'requesting'"
          @click="requestSingleUseLocation"
        >
          {{ locationState === 'requesting' ? '正在請求單次定位…' : '只使用這次定位' }}
        </button>
        <p class="muted">定位只在你主動按下後請求；不寫入 Session、帳號或瀏覽器儲存。</p>
        <p v-if="locationMessage" data-testid="location-privacy-status" role="status">{{ locationMessage }}</p>
      </div>
    </section>

    <p v-if="loading" class="panel" role="status">正在載入經確認的 Demo 生活圈…</p>
    <p v-else-if="error" class="panel reachability-warning" role="alert">
      <strong>目前沒有可驗證的生活圈範圍</strong>
      <span>{{ error }}</span>
      <small>不顯示未審核的座標、即時路況或導航；資料補齊後可在同一個畫面切換步行／機車與 10／15 分鐘。</small>
    </p>

    <section v-if="area" class="reachability-result" aria-live="polite">
      <div class="panel reachability-map" data-testid="reachability-map" aria-label="生活圈 GeoJSON 範圍">
        <div class="section-title-row">
          <h2>可達範圍</h2>
          <span class="status-badge">{{ area.isDemo ? 'Demo 固定資料' : 'Provider 資料' }}</span>
        </div>
        <p>起點：{{ originLabel }}</p>
        <p><strong>{{ area.travelMode === 'pedestrian' ? '步行' : '機車' }}・{{ area.thresholdMinutes }} 分鐘</strong></p>
        <p class="source-note">來源：{{ area.source }}・{{ area.realTime ? '含即時資料' : '非即時路況' }}・{{ area.navigation ? '可導航' : '不提供導航' }}</p>
        <div class="reachability-visual" data-testid="reachability-map-visual" role="img" :aria-label="`${area.travelMode === 'pedestrian' ? '步行' : '機車'} ${area.thresholdMinutes} 分鐘固定示意範圍`">
          <svg viewBox="0 0 100 100" aria-hidden="true">
            <defs><pattern id="reachability-grid" width="10" height="10" patternUnits="userSpaceOnUse"><path d="M 10 0 L 0 0 0 10" fill="none" stroke="currentColor" stroke-opacity=".16" stroke-width=".5" /></pattern></defs>
            <rect width="100" height="100" fill="url(#reachability-grid)" />
            <path d="M -8 78 C 20 64 33 69 52 52 S 82 26 108 22" class="reachability-street major" />
            <path d="M 14 -8 C 25 18 31 34 26 55 S 31 82 42 108" class="reachability-street" />
            <path d="M 77 -8 C 69 22 74 42 68 61 S 73 84 89 108" class="reachability-street" />
            <path d="M -8 34 C 17 39 39 29 58 35 S 84 49 108 45" class="reachability-street" />
            <polygon v-if="polygonPoints" :points="polygonPoints" class="reachability-polygon" />
            <g v-for="location in area.locations" :key="location.id" class="reachability-location-marker">
              <circle :cx="locationMarker(location.id).x" :cy="locationMarker(location.id).y" r="2.4" />
              <text :x="locationMarker(location.id).x + 3" :y="locationMarker(location.id).y + 1">{{ location.name.replace('信義服務點', '') }}</text>
              <title>{{ location.name }}</title>
            </g>
            <g class="reachability-origin-marker"><circle :cx="originMarker.x" :cy="originMarker.y" r="3.2" /><text :x="originMarker.x + 3" :y="originMarker.y - 3">會場起點</text></g>
          </svg>
          <div class="reachability-map-caption"><span>● 會場起點</span><span>● Catalog 據點</span><a :href="osmUrl" target="_blank" rel="noreferrer">用 OpenStreetMap 查看位置 ↗</a></div>
        </div>
        <p class="geometry-fact">GeoJSON geometry：{{ area.geometry.type ?? 'unknown' }}・固定示意範圍，不代表導航路線</p>
      </div>
      <section class="panel" aria-labelledby="reachable-provider-title">
        <h2 id="reachable-provider-title">範圍內 Provider／Location</h2>
        <ul v-if="area.locations.length" class="plain-list" data-testid="reachable-location-list">
          <li v-for="location in area.locations" :key="location.id">
            <strong>{{ location.name }}</strong>
            <span class="muted">{{ location.address ?? location.id }}</span>
          </li>
        </ul>
        <p v-else class="muted">這個條件目前沒有已確認的據點。</p>

        <div class="reachability-services" aria-labelledby="reachable-service-title">
          <div class="section-title-row">
            <h3 id="reachable-service-title">生活圈內可以直接用的服務</h3>
            <span class="status-badge">{{ reachableServices.length }} 項</span>
          </div>
          <div v-if="reachableServices.length" class="reachable-service-grid">
            <article
              v-for="service in reachableServices"
              :key="service.id"
              class="reachable-service-card"
              data-testid="reachable-service-card"
            >
              <span class="reachable-service-category">{{ service.category }}</span>
              <h4>{{ service.title }}</h4>
              <p>{{ service.detail }}</p>
              <strong>{{ service.priceLabel }}</strong>
              <RouterLink class="button inline" :to="service.to">查看服務</RouterLink>
            </article>
          </div>
          <p v-else class="muted">目前這個時間門檻沒有對應的服務卡片。</p>
        </div>
      </section>
    </section>
  </section>
</template>

<style scoped>
.reachability-page {
  display: grid;
  gap: var(--space-5);
}
.reachability-controls {
  display: grid;
  gap: 0.75rem;
}
.reachability-controls p {
  margin: 0;
}
.reachability-control-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-4);
}
.reachability-control-grid label {
  display: grid;
  gap: 0.3rem;
  font-weight: 800;
}
.reachability-control-grid select {
  min-height: var(--tap);
  padding: 0.45rem 0.6rem;
  border: 2px solid var(--ink);
  border-radius: 12px;
  background: var(--surface);
}
.location-consent {
  display: grid;
  gap: 0.35rem;
  padding-top: 0.25rem;
  border-top: 1px solid color-mix(in srgb, var(--ink) 25%, transparent);
}
.location-consent p {
  margin: 0;
}
.location-consent .button {
  justify-self: start;
}
.reachability-result {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(18rem, 0.8fr);
  gap: var(--space-5);
}
.reachability-map {
  min-height: 20rem;
  background: var(--blue);
}
.reachability-visual {
  margin-top: 1rem;
  padding: .6rem;
  border: 2px solid var(--ink);
  border-radius: 14px;
  background: color-mix(in srgb, var(--surface) 68%, transparent);
}
.reachability-visual svg {
  display: block;
  width: 100%;
  height: 14rem;
  color: var(--ink);
}
.reachability-polygon {
  fill: color-mix(in srgb, var(--mint) 60%, transparent);
  stroke: var(--ink);
  stroke-width: .8;
  stroke-linejoin: round;
}
.reachability-street {
  fill: none;
  stroke: color-mix(in srgb, var(--ink) 28%, transparent);
  stroke-width: 1.1;
  stroke-linecap: round;
}
.reachability-street.major {
  stroke: color-mix(in srgb, var(--ink) 44%, transparent);
  stroke-width: 2.1;
}
.reachability-location-marker circle {
  fill: var(--peach);
  stroke: var(--ink);
  stroke-width: .8;
}
.reachability-location-marker text {
  fill: var(--ink);
  font-size: 2.2px;
  font-weight: 900;
}
.reachability-origin-marker circle {
  fill: var(--accent, #ff725c);
  stroke: var(--ink);
  stroke-width: 1;
}
.reachability-origin-marker text {
  font-size: 3px;
  font-weight: 900;
}
.reachability-map-caption {
  display: flex;
  gap: .75rem;
  flex-wrap: wrap;
  align-items: center;
  font-size: .72rem;
  font-weight: 800;
}
.reachability-map-caption a { color: var(--ink); }
.status-badge {
  padding: 0.25rem 0.55rem;
  border: 2px solid var(--ink);
  border-radius: 999px;
  background: var(--yellow, #fde68a);
  font-size: var(--text-sm);
  font-weight: 800;
}
.geometry-fact {
  margin-top: .8rem;
  font-family: var(--font-mono);
  font-size: var(--text-sm);
}
.reachability-warning {
  display: grid;
  gap: 0.4rem;
  background: var(--accent-soft);
}
.reachability-warning span,
.reachability-warning small {
  display: block;
}
.reachability-services {
  display: grid;
  gap: .65rem;
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 2px dashed var(--ink);
}
.reachability-services h3 {
  margin: 0;
  font-size: 1rem;
}
.reachable-service-grid {
  display: grid;
  gap: .65rem;
}
.reachable-service-card {
  display: grid;
  gap: .3rem;
  padding: .75rem;
  border: 2px solid var(--ink);
  border-radius: 12px;
  background: var(--mint);
  box-shadow: 2px 2px 0 var(--ink);
}
.reachable-service-category {
  color: var(--muted);
  font-size: .72rem;
  font-weight: 900;
}
.reachable-service-card h4,
.reachable-service-card p {
  margin: 0;
}
.reachable-service-card h4 {
  font-size: .98rem;
}
.reachable-service-card p {
  color: var(--muted);
  font-size: .82rem;
}
.reachable-service-card strong {
  font-size: .82rem;
}
.reachable-service-card .button {
  justify-self: start;
  margin-top: .2rem;
}
@media (max-width: 720px) {
  .reachability-control-grid,
  .reachability-result {
    grid-template-columns: 1fr;
  }
  .reachability-map {
    min-height: 14rem;
  }
}
</style>
