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
/** '' = 正常使用 API；'offline' = 後端真的連不上；'empty' = 後端回了空範圍。 */
const fallbackReason = ref<'' | 'offline' | 'empty'>('')
const locationState = ref<'idle' | 'requesting' | 'granted' | 'denied'>('idle')
const locationMessage = ref('')
const ORIGIN_POINT = { lon: 121.5654, lat: 25.0339 }
/**
 * Location id → 示意座標。id 必須對齊目錄投影（`fake_upstreams/partner_seed.py`
 * 的 `loc-<brand>-NN`）；沒列到的 id 會走 `fallbackPoint()`，不會塌回起點。
 */
const LOCATION_POINTS: Record<string, { lon: number; lat: number }> = {
  'loc-711-shop-01': { lon: 121.5669, lat: 25.0324 },
  'loc-711-c2c-01': { lon: 121.5636, lat: 25.0322 },
  'loc-cosmed-01': { lon: 121.5688, lat: 25.0356 },
  'loc-prince-electric-01': { lon: 121.5628, lat: 25.0347 },
  'loc-duskin-01': { lon: 121.5708, lat: 25.0362 },
  'loc-foodomo-01': { lon: 121.5710, lat: 25.0330 },
  'loc-21plus-01': { lon: 121.5598, lat: 25.0372 },
  'loc-blackcat-01': { lon: 121.5744, lat: 25.0300 },
  'loc-smile-01': { lon: 121.5580, lat: 25.0296 },
  'loc-iopenmall-01': { lon: 121.5772, lat: 25.0384 },
  'loc-ibon-ticket-01': { lon: 121.5560, lat: 25.0338 },
}

/**
 * 沒有明確座標時的決定性 fallback：把 id 雜湊成起點附近的一個角度＋半徑，
 * 讓未列入的據點仍然落在地圖上（而不是整疊在「會場起點」）。
 */
function fallbackPoint(id: string): { lon: number; lat: number } {
  let hash = 7
  for (let index = 0; index < id.length; index += 1) {
    hash = (hash * 31 + id.charCodeAt(index)) % 100003
  }
  const angle = (hash % 360) * (Math.PI / 180)
  const radius = 0.0018 + (Math.floor(hash / 360) % 6) * 0.0006
  return {
    lon: ORIGIN_POINT.lon + Math.cos(angle) * radius * 1.15,
    lat: ORIGIN_POINT.lat + Math.sin(angle) * radius,
  }
}

type Coordinate = [number, number]

const VIRTUAL_BLOCKS = [
  { x: 5, y: 9, width: 16, height: 14, label: '晴光里', tone: 'mint' },
  { x: 28, y: 7, width: 18, height: 18, label: '森林公園', tone: 'green' },
  { x: 56, y: 8, width: 18, height: 15, label: '日光市場', tone: 'peach' },
  { x: 81, y: 7, width: 14, height: 18, label: '河畔宅', tone: 'blue' },
  { x: 5, y: 63, width: 20, height: 18, label: '社區學苑', tone: 'blue' },
  { x: 32, y: 68, width: 16, height: 14, label: '中庭廣場', tone: 'yellow' },
  { x: 56, y: 65, width: 19, height: 18, label: '生活工坊', tone: 'peach' },
  { x: 82, y: 64, width: 13, height: 17, label: '安居街', tone: 'mint' },
]

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
const commuteRingRadius = computed(() => {
  const threshold = area.value?.thresholdMinutes ?? thresholdMinutes.value
  if (threshold === 15) return travelMode.value === 'scooter' ? 43 : 36
  return travelMode.value === 'scooter' ? 34 : 26
})

const reachableServices = computed(() => {
  const providers = new Set(area.value?.locations.map((location) => location.providerId) ?? [])
  return LIFE_CIRCLE_SERVICES.filter((service) => providers.has(service.providerId))
})

function locationMarker(id: string) {
  return project(LOCATION_POINTS[id] ?? fallbackPoint(id))
}

/** 圖例分組；顏色不是唯一區分，圖例文字與 <title> 都說明了同一件事。 */
const TONE_BY_PROVIDER: Record<string, 'repair' | 'cleaning' | 'convenience' | 'daily'> = {
  'vendor-prince-electric': 'repair',
  'vendor-duskin': 'cleaning',
  'vendor-smile': 'cleaning',
  'vendor-711-shop': 'convenience',
  'vendor-711-c2c': 'convenience',
  'vendor-iopenmall': 'convenience',
  'vendor-ibon-ticket': 'convenience',
  'vendor-blackcat': 'convenience',
  'vendor-foodomo': 'daily',
  'vendor-21plus': 'daily',
  'vendor-cosmed': 'daily',
  'vendor-uni-resort': 'daily',
}

const TONE_LABELS: Record<string, string> = {
  repair: '修繕',
  cleaning: '清潔・洗車',
  convenience: '超商取貨・寄件・票券',
  daily: '餐飲・藥妝',
}

function locationTone(providerId: string) {
  return TONE_BY_PROVIDER[providerId] ?? 'repair'
}

/** 據點名稱在目錄裡是「品牌 信義區服務點」，地圖上只留品牌避免標籤過長。 */
function shortLabel(name: string): string {
  return name.replace(/[\s・][^\s・]*服務點$/u, '').trim() || name
}

/**
 * 把標籤左右／上下交錯，~6 個點時才不會互相疊住；
 * 靠右的點改成向左對齊，避免文字被畫布切掉。
 */
const locationMarkers = computed(() => (area.value?.locations ?? []).map((location, index) => {
  const point = locationMarker(location.id)
  const flip = point.x > 62
  const tone = locationTone(location.providerId)
  return {
    id: location.id,
    name: location.name,
    address: location.address ?? location.id,
    tone,
    toneLabel: TONE_LABELS[tone] ?? '',
    x: point.x,
    y: point.y,
    labelX: flip ? point.x - 3.2 : point.x + 3.2,
    labelY: point.y + (index % 2 === 0 ? -2.4 : 3.6),
    anchor: flip ? 'end' : 'start',
    label: shortLabel(location.name),
  }
}))

function createVirtualArea(): ReachabilityArea {
  const wide = thresholdMinutes.value === 15
  const coordinates: Coordinate[] = wide
    ? [[121.559, 25.030], [121.573, 25.029], [121.578, 25.036], [121.570, 25.041], [121.558, 25.038], [121.559, 25.030]]
    : [[121.562, 25.032], [121.569, 25.031], [121.572, 25.036], [121.567, 25.039], [121.561, 25.036], [121.562, 25.032]]
  // Provider id 必須是目錄裡真的有的，否則「生活圈內可以直接用的服務」永遠是空的。
  const prince = { id: 'loc-prince-electric-01', providerId: 'vendor-prince-electric', name: '王子水電・晴光服務點', address: '虛擬示範路 1 號' }
  const duskin = { id: 'loc-duskin-01', providerId: 'vendor-duskin', name: 'DUSKIN 樂清・河畔服務點', address: '虛擬示範路 2 號' }
  const seven = { id: 'loc-711-shop-01', providerId: 'vendor-711-shop', name: '7-ELEVEN 日光森林門市・取貨服務', address: '虛擬示範路 3 號' }
  const c2c = { id: 'loc-711-c2c-01', providerId: 'vendor-711-c2c', name: '7-ELEVEN 交貨便・生活服務站', address: '虛擬示範路 5 號' }
  const cosmed = { id: 'loc-cosmed-01', providerId: 'vendor-cosmed', name: '康是美・社區藥妝服務點', address: '虛擬示範路 6 號' }
  const foodomo = { id: 'loc-foodomo-01', providerId: 'vendor-foodomo', name: 'foodomo 社區外送合作點', address: '虛擬示範路 8 號' }
  const locations = wide
    ? [prince, seven, c2c, cosmed, foodomo, duskin]
    : [prince, seven, c2c, cosmed, foodomo]
  return {
    originId: ORIGIN_ID,
    travelMode: travelMode.value,
    thresholdMinutes: thresholdMinutes.value,
    geometry: { type: 'Polygon', coordinates: [coordinates] },
    eligibleLocationIds: locations.map((location) => location.id),
    locations,
    source: 'virtual-life-circle',
    calculatedAt: '2026-08-02T10:00:00+08:00',
    isDemo: true,
    realTime: false,
    navigation: false,
  }
}

async function load() {
  loading.value = true
  error.value = ''
  fallbackReason.value = ''
  try {
    const loaded = await getReachabilityArea({
      originId: ORIGIN_ID,
      travelMode: travelMode.value,
      thresholdMinutes: thresholdMinutes.value,
    })
    // 後端的種子資料本來就是 `isDemo: true`（經確認的固定示意範圍），
    // 那不是「後端沒起來」，所以不能拿它當 fallback 條件；只有真的一個據點
    // 都沒有時才退回本地示意圖，並且要誠實說明原因。
    if (loaded.locations.length === 0) {
      area.value = createVirtualArea()
      fallbackReason.value = 'empty'
    } else {
      area.value = loaded
    }
  } catch (reason) {
    void reason
    area.value = createVirtualArea()
    fallbackReason.value = 'offline'
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
        <p v-if="fallbackReason" class="reachability-demo-notice" data-testid="reachability-offline-demo">
          {{ fallbackReason === 'offline'
            ? '目前連不上後端，改用完全虛擬的生活圈示意；道路、街區與服務點都是 Demo 資料。'
            : '後端這個條件沒有回傳任何據點，改用完全虛擬的生活圈示意；道路、街區與服務點都是 Demo 資料。' }}
        </p>
        <div class="reachability-visual" data-testid="reachability-map-visual" role="img" :aria-label="`${area.travelMode === 'pedestrian' ? '步行' : '機車'} ${area.thresholdMinutes} 分鐘固定示意範圍`">
          <svg viewBox="0 0 100 100" aria-hidden="true">
            <defs><pattern id="reachability-grid" width="10" height="10" patternUnits="userSpaceOnUse"><path d="M 10 0 L 0 0 0 10" fill="none" stroke="currentColor" stroke-opacity=".16" stroke-width=".5" /></pattern></defs>
            <rect width="100" height="100" fill="url(#reachability-grid)" />
            <g class="reachability-blocks">
              <g v-for="block in VIRTUAL_BLOCKS" :key="block.label" :class="`block-${block.tone}`">
                <rect :x="block.x" :y="block.y" :width="block.width" :height="block.height" rx="2" />
                <text :x="block.x + block.width / 2" :y="block.y + block.height / 2 + 1">{{ block.label }}</text>
              </g>
            </g>
            <path d="M -8 78 C 20 64 33 69 52 52 S 82 26 108 22" class="reachability-street major" />
            <path d="M 14 -8 C 25 18 31 34 26 55 S 31 82 42 108" class="reachability-street" />
            <path d="M 77 -8 C 69 22 74 42 68 61 S 73 84 89 108" class="reachability-street" />
            <path d="M -8 34 C 17 39 39 29 58 35 S 84 49 108 45" class="reachability-street" />
            <circle :cx="originMarker.x" :cy="originMarker.y" :r="commuteRingRadius" class="commute-ring" />
            <polygon v-if="polygonPoints" :points="polygonPoints" class="reachability-polygon" />
            <g v-for="marker in locationMarkers" :key="marker.id" :class="['reachability-location-marker', marker.tone]">
              <circle :cx="marker.x" :cy="marker.y" r="2.4" />
              <text :x="marker.labelX" :y="marker.labelY" :text-anchor="marker.anchor">{{ marker.label }}</text>
              <title>{{ marker.name }}（{{ marker.toneLabel }}）</title>
            </g>
            <g class="reachability-origin-marker"><circle :cx="originMarker.x" :cy="originMarker.y" r="3.2" /><text :x="originMarker.x + 3" :y="originMarker.y - 3">會場起點</text></g>
          </svg>
          <div class="reachability-map-caption"><span>● 會場起點</span><span class="legend-repair">● 修繕</span><span class="legend-cleaning">● 清潔・洗車</span><span class="legend-convenience">● 超商取貨・寄件・票券</span><span class="legend-daily">● 餐飲・藥妝</span><span>○ {{ area.thresholdMinutes }} 分鐘通勤圈</span></div>
        </div>
        <p class="geometry-fact">GeoJSON geometry：{{ area.geometry.type ?? 'unknown' }}・固定示意範圍，不代表導航路線</p>
      </div>
      <section class="panel" aria-labelledby="reachable-provider-title">
        <h2 id="reachable-provider-title">範圍內 Provider／Location</h2>
        <ul v-if="locationMarkers.length" class="plain-list" data-testid="reachable-location-list">
          <li v-for="marker in locationMarkers" :key="marker.id">
            <strong>{{ marker.name }}</strong>
            <span class="muted">{{ marker.toneLabel }}・{{ marker.address }}</span>
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
.reachability-blocks rect {
  stroke: color-mix(in srgb, var(--ink) 32%, transparent);
  stroke-width: .45;
}
.reachability-blocks text {
  fill: color-mix(in srgb, var(--ink) 62%, transparent);
  font-size: 1.55px;
  font-weight: 800;
  text-anchor: middle;
}
.block-mint rect { fill: color-mix(in srgb, var(--mint) 62%, transparent); }
.block-green rect { fill: color-mix(in srgb, #9bd5ad 52%, transparent); }
.block-peach rect { fill: color-mix(in srgb, var(--peach) 64%, transparent); }
.block-blue rect { fill: color-mix(in srgb, var(--blue) 66%, transparent); }
.block-yellow rect { fill: color-mix(in srgb, var(--yellow, #fde68a) 60%, transparent); }
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
.commute-ring {
  fill: color-mix(in srgb, var(--accent) 12%, transparent);
  stroke: var(--accent);
  stroke-width: 1.1;
  stroke-dasharray: 2.2 1.5;
}
.reachability-location-marker circle {
  fill: var(--peach);
  stroke: var(--ink);
  stroke-width: .8;
}
.reachability-location-marker.repair circle { fill: var(--accent, #ff725c); }
.reachability-location-marker.cleaning circle { fill: var(--lilac, #e6e6fa); }
.reachability-location-marker.convenience circle { fill: var(--yellow, #fde68a); }
.reachability-location-marker.daily circle { fill: var(--mint, #cdeedd); }
.reachability-location-marker text {
  fill: var(--ink);
  paint-order: stroke;
  stroke: var(--surface, #fff);
  stroke-width: 0.7px;
  stroke-linejoin: round;
  font-size: 2.2px;
  font-weight: 900;
}
.reachability-origin-marker circle {
  fill: var(--accent, #ff725c);
  stroke: var(--ink);
  stroke-width: 1;
}
.reachability-origin-marker text {
  paint-order: stroke;
  stroke: var(--surface, #fff);
  stroke-width: 0.9px;
  stroke-linejoin: round;
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
.reachability-map-caption .legend-repair { color: var(--accent-ink); }
.reachability-map-caption .legend-cleaning { color: var(--primary); }
.reachability-map-caption .legend-convenience { color: #8a5a00; }
.reachability-map-caption .legend-daily { color: #146c4a; }
.reachability-demo-notice {
  margin: .6rem 0 0;
  padding: .6rem .7rem;
  border: 2px solid var(--ink);
  border-radius: 12px;
  background: var(--yellow, #fde68a);
  color: var(--accent-ink);
  font-size: .78rem;
  font-weight: 800;
}
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
