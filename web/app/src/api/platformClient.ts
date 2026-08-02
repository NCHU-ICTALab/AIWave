// M4 Platform API client:目錄探索、TaskDraft、試算、Booking/Order、付款、
// 通知與行事曆。所有型別鏡射 api/platform_core.py 的回應;後端是唯一權威。
import { request, stableIdempotencyKey } from './http'

const BASE = '/api/v1/platform'

// ── 目錄 ────────────────────────────────────────────

export interface CatalogProvider {
  id: string
  name: string
  scene: 'food' | 'med' | 'home' | 'move' | 'pre' | 'fun' | string
  summary: string | null
  rating: number | null
  reviewCount: number | null
  placeholder: boolean
  seedVersion: string
  syncedAt: string
}

export interface CatalogLocation {
  id: string
  providerId: string
  name: string
  countyName?: string
  districtName?: string
  address?: string
  phone?: string
}

export interface CatalogOffering {
  id: string
  providerId: string
  name: string
  domainType: string | null
  fulfillmentKind: 'booking' | 'commerce'
  basePrice: number
  currency: string
  pricingUnit: string | null
  cancelPolicyHours: number | null
  description: string | null
}

export interface CatalogResource {
  id: string
  providerId: string
  name: string
  kind: string | null
}

export interface CatalogSlot {
  id: string
  providerId: string
  offeringId: string
  locationId: string | null
  resourceId: string | null
  startsAt: string
  endsAt: string
  status: string
  capacity: number
}

export interface CatalogProviderDetail extends CatalogProvider {
  locations: CatalogLocation[]
  offerings: CatalogOffering[]
  resources: CatalogResource[]
}

export function listProviders(scene?: string): Promise<CatalogProvider[]> {
  return request(`${BASE}/catalog/providers`, { query: { scene } })
}

/** tier-2 目錄陳列:統一體系品牌卡,不可下單(2026-07-31 兩層制)。 */
export interface ListedBrand {
  id: string
  name: string
  scene: string
  company: string
  url: string
  note: string
  tags: string[]
  transactable: false
  source: string
}

export function listListings(scene?: string): Promise<ListedBrand[]> {
  return request(`${BASE}/catalog/listings`, { query: { scene } })
}

export function getProvider(providerId: string): Promise<CatalogProviderDetail> {
  return request(`${BASE}/catalog/providers/${encodeURIComponent(providerId)}`)
}

export function listAvailability(params: {
  providerId: string
  offeringId?: string
  startsAfter?: string
  startsBefore?: string
}): Promise<CatalogSlot[]> {
  return request(`${BASE}/catalog/availability`, { query: { ...params } })
}

// ── v4 時間可達生活圈／到府服務範圍 ───────────────────

export interface ReachabilityArea {
  originId: string
  travelMode: 'pedestrian' | 'scooter' | string
  thresholdMinutes: number
  geometry: Record<string, unknown>
  eligibleLocationIds: string[]
  locations: CatalogLocation[]
  source: string
  calculatedAt: string | null
  isDemo: boolean
  realTime: boolean
  navigation: boolean
}

export interface ProviderServiceAreaResult {
  providerId: string
  decision: 'provider_service_area' | string
  eligible: boolean
  county?: string
  district?: string
  serviceArea?: Record<string, unknown>
  reason?: string
  source: string
}

export function getReachabilityArea(params: {
  originId: string
  travelMode: 'pedestrian' | 'scooter'
  thresholdMinutes: 10 | 15
}): Promise<ReachabilityArea> {
  return request(`${BASE}/reachability/area`, { query: {
    originId: params.originId,
    travelMode: params.travelMode,
    thresholdMinutes: params.thresholdMinutes,
  } })
}

export function getProviderServiceArea(params: {
  providerId: string
  county: string
  district: string
}): Promise<ProviderServiceAreaResult> {
  return request(`${BASE}/provider-service-areas/${encodeURIComponent(params.providerId)}`, {
    query: { county: params.county, district: params.district },
  })
}

// ── v4 主動照護／可編輯生活任務包／成果投影 ──────────────

export interface CareMessage {
  id: string
  candidateId: string
  state: 'delivered' | 'ignored' | 'snoozed' | 'closed' | string
  deliveredAt: string
  actedAt: string | null
  action: string | null
  candidate: {
    id: string
    eventId: string
    kind: string
    reason: string
    evidence: {
      dataUsed?: string[]
      source?: string
      isDemo?: boolean
      noBackgroundTracking?: boolean
      guideStatus?: string
      actions?: string[]
    }
    status: string
  }
  guide?: {
    status: string
    title?: string
    message: string
    source: string
    updatedAt?: string
    reviewedBy?: string
    steps?: Array<{ id: string; title: string; body: string }>
    preparationItems?: Array<{
      id: string
      name: string
      necessity: 'common-required' | 'optional' | 'convenience' | 'cooperation-recommendation' | string
      quantityBasis?: string
      cooperationLabel?: string
      estimatedPoints?: number
    }>
    pointsEstimate?: { min: number; max: number; label: string }
    warnings?: string[]
    suggestedActions?: Array<{ type: string; label: string }>
    commercialBoundary?: string
  }
}

export function listCareMessages(includeClosed = false): Promise<CareMessage[]> {
  return request(`${BASE}/care/messages`, { query: { include_closed: includeClosed } })
}

export function actOnCareMessage(
  messageId: string,
  action: 'ignore' | 'snooze' | 'close' | 'open_guide',
): Promise<CareMessage> {
  return request(`${BASE}/care/messages/${encodeURIComponent(messageId)}/actions`, {
    body: { action },
  })
}

export interface TaskPackageItem {
  id: string
  position: number
  taskDraftId: string | null
  sourceSubtaskId: string
  providerId: string
  providerName: string
  offeringId: string
  offeringName: string
  amount: number
  points: number
  startsAt: string | null
  endsAt: string | null
  status: string
  details: { proposalOptions?: Array<Record<string, unknown>>; [key: string]: unknown }
  lastError: string | null
  version: number
}

export interface TaskPackage {
  id: string
  source: { type: string; id: string }
  beneficiary: Record<string, unknown>
  serviceLocation: Record<string, unknown>
  status: string
  grantId: string | null
  version: number
  totalAmount: number
  totalPoints: number
  providerIds: string[]
  selectedItemIds: string[]
  taskDraftRefs: string[]
  items: TaskPackageItem[]
}

export function listTaskPackages(): Promise<TaskPackage[]> {
  return request(`${BASE}/agent/task-packages`)
}

export function patchTaskPackageItem(
  packageId: string,
  itemId: string,
  input: {
    expectedVersion: number
    operation: 'update' | 'pause' | 'resume' | 'remove' | 'replace_provider'
    changes?: Record<string, unknown>
  },
): Promise<TaskPackage> {
  return request(`${BASE}/agent/task-packages/${encodeURIComponent(packageId)}/items/${encodeURIComponent(itemId)}`, {
    method: 'PATCH',
    body: {
      expected_version: input.expectedVersion,
      operation: input.operation,
      changes: input.changes ?? {},
    },
  })
}

export interface MemberOutcome {
  id: string
  packageId: string | null
  subjectType: string
  subjectId: string
  providerId: string | null
  amount: number
  status: string
  summary: string
  eventId: string
  createdAt: string
}

export interface AchievementUnlock {
  key: string
  title: string
  outcomeId: string
  unlockedAt: string
}

export interface DemoRewardEntry {
  id: string
  campaignId: string
  subjectType: string
  subjectId: string
  kind: 'grant' | 'reversal' | string
  amount: number
  pointsEntryId: string | null
  reversesEntryId: string | null
  createdAt: string
}

export interface MemberOutcomeProjection {
  outcomes: MemberOutcome[]
  achievements: AchievementUnlock[]
  rewards: DemoRewardEntry[]
  note: string
}

export function getMemberOutcomes(): Promise<MemberOutcomeProjection> {
  return request(`${BASE}/outcomes`)
}

// ── 試算 ────────────────────────────────────────────

export interface Quote {
  offeringId: string
  offeringName: string | null
  currency: string
  unitPrice: number
  quantity: number
  subtotal: number
  pointsBalance: number
  maxRedeemablePoints: number
  pointsToRedeem: number
  pointsDiscount: number
  payable: number
  ruleSummary: string
}

export function createQuote(input: {
  offeringId: string
  quantity?: number
  pointsToRedeem?: number
}): Promise<Quote> {
  return request(`${BASE}/quotes`, {
    body: {
      offering_id: input.offeringId,
      quantity: input.quantity ?? 1,
      points_to_redeem: input.pointsToRedeem ?? 0,
    },
  })
}

// ── TaskDraft ──────────────────────────────────────

export interface TaskDraft {
  id: string
  domainType: string
  status: 'drafting' | 'ready' | 'confirmed' | 'abandoned'
  values: Record<string, unknown>
  provenance: Record<string, string>
  version: number
  resultSubjectType: string | null
  resultSubjectId: string | null
  updatedAt: string
}

export function createDraft(input: {
  domainType: string
  values: Record<string, unknown>
  source?: 'user' | 'agent' | 'profile' | 'provider_default'
}): Promise<TaskDraft> {
  return request(`${BASE}/task-drafts`, {
    body: { domain_type: input.domainType, values: input.values, source: input.source ?? 'user' },
    idempotencyKey: stableIdempotencyKey('draft-create', {
      domainType: input.domainType,
      values: input.values,
      at: Date.now(),
    }),
  })
}

export function listDrafts(): Promise<TaskDraft[]> {
  return request(`${BASE}/task-drafts`)
}

export function getDraft(draftId: string): Promise<TaskDraft> {
  return request(`${BASE}/task-drafts/${encodeURIComponent(draftId)}`)
}

export function updateDraft(
  draftId: string,
  input: { expectedVersion: number; values: Record<string, unknown> },
): Promise<TaskDraft & { ignoredFields?: string[] }> {
  return request(`${BASE}/task-drafts/${encodeURIComponent(draftId)}`, {
    method: 'PATCH',
    body: { expected_version: input.expectedVersion, values: input.values, source: 'user' },
  })
}

export function transitionDraft(
  draftId: string,
  input: { expectedVersion: number; status: TaskDraft['status'] },
): Promise<TaskDraft> {
  return request(`${BASE}/task-drafts/${encodeURIComponent(draftId)}/transition`, {
    body: { expected_version: input.expectedVersion, status: input.status },
  })
}

export interface DraftSubmitResult {
  draft: TaskDraft
  subjectType: 'booking' | 'commerce_order'
  subjectId: string
  booking?: Booking
  order?: CommerceOrder
  idempotentReplay?: boolean
}

export function submitDraft(draftId: string, expectedVersion: number): Promise<DraftSubmitResult> {
  return request(`${BASE}/task-drafts/${encodeURIComponent(draftId)}/submit`, {
    body: { expected_version: expectedVersion },
    idempotencyKey: `draft-submit-${draftId}`,
  })
}

// ── Booking / CommerceOrder ────────────────────────

export interface StatusEvent {
  id: string
  type: string
  fromStatus: string | null
  toStatus: string
  actorRole: string
  note: string | null
  occurredAt: string
}

export interface Booking {
  id: string
  providerId: string
  locationId: string
  offeringId: string
  resourceId: string | null
  slotId: string
  startsAt: string
  endsAt: string
  status: string
  version: number
  /** 履約必要欄位(個資最小化;submit 時依 domain required_fields 過濾) */
  details?: Record<string, unknown> | null
  events: StatusEvent[]
  providerSync?: { syncStatus: string; lastError: string | null }
  refunds?: PaymentRecord[]
}

export interface CommerceOrderItem {
  offeringId: string
  name: string
  quantity: number
  unitPrice: number
  amount: number
}

export interface CommerceOrder {
  id: string
  providerId: string
  items: CommerceOrderItem[]
  subtotal: number
  discount: number
  total: number
  status: string
  version: number
  events: StatusEvent[]
  refunds?: PaymentRecord[]
}

export function listBookings(): Promise<Booking[]> {
  return request(`${BASE}/bookings`)
}

export function getBooking(bookingId: string): Promise<Booking> {
  return request(`${BASE}/bookings/${encodeURIComponent(bookingId)}`)
}

export function retryBookingSync(bookingId: string): Promise<Booking> {
  return request(`${BASE}/bookings/${encodeURIComponent(bookingId)}/provider-sync`, {
    method: 'POST',
    body: {},
  })
}

export function transitionBooking(
  bookingId: string,
  input: { expectedVersion: number; status: string; note?: string },
  idempotencyKey: string,
): Promise<Booking> {
  return request(`${BASE}/bookings/${encodeURIComponent(bookingId)}/transition`, {
    body: { expected_version: input.expectedVersion, status: input.status, note: input.note ?? null },
    idempotencyKey,
  })
}

export function cancelBooking(
  bookingId: string,
  input: { expectedVersion: number; note?: string },
): Promise<Booking> {
  return request(`${BASE}/bookings/${encodeURIComponent(bookingId)}/cancellation`, {
    body: { expected_version: input.expectedVersion, note: input.note ?? null },
    idempotencyKey: `cancel-${bookingId}-v${input.expectedVersion}`,
  })
}

export function requestReschedule(
  bookingId: string,
  input: { slotId: string; startsAt: string; endsAt: string; reason?: string },
): Promise<{ id: string; status: string }> {
  return request(`${BASE}/bookings/${encodeURIComponent(bookingId)}/reschedule-requests`, {
    body: {
      slot_id: input.slotId,
      starts_at: input.startsAt,
      ends_at: input.endsAt,
      reason: input.reason ?? null,
    },
    idempotencyKey: stableIdempotencyKey(`reschedule-${bookingId}`, input),
  })
}

export function reviewReschedule(
  requestId: string,
  accept: boolean,
): Promise<{ id: string; bookingId?: string; status: string }> {
  return request(`${BASE}/booking-reschedule-requests/${encodeURIComponent(requestId)}/review`, {
    body: { accept },
    idempotencyKey: `reschedule-review-${requestId}-${accept}`,
  })
}

export function listCommerceOrders(): Promise<CommerceOrder[]> {
  return request(`${BASE}/commerce-orders`)
}

export function transitionCommerceOrder(
  orderId: string,
  input: { expectedVersion: number; status: string; note?: string },
  idempotencyKey: string,
): Promise<CommerceOrder> {
  return request(`${BASE}/commerce-orders/${encodeURIComponent(orderId)}/transition`, {
    body: { expected_version: input.expectedVersion, status: input.status, note: input.note ?? null },
    idempotencyKey,
  })
}

export function cancelCommerceOrder(
  orderId: string,
  input: { expectedVersion: number; note?: string },
): Promise<CommerceOrder> {
  return request(`${BASE}/commerce-orders/${encodeURIComponent(orderId)}/cancellation`, {
    body: { expected_version: input.expectedVersion, note: input.note ?? null },
    idempotencyKey: `cancel-${orderId}-v${input.expectedVersion}`,
  })
}

// ── 付款 ────────────────────────────────────────────

export interface PaymentRecord {
  id: string
  subjectType: string
  subjectId: string
  amount: number
  pointsRedeemed: number
  refundedAmount: number
  refundedPoints: number
  status: string
  failureCode: string | null
  label: string
}

export function createPayment(input: {
  subjectType: 'booking' | 'commerce_order'
  subjectId: string
  amount: number
  pointsRedeemed?: number
  outcome: 'pending' | 'success' | 'failure'
}): Promise<PaymentRecord> {
  return request(`${BASE}/payments`, {
    body: {
      subject_type: input.subjectType,
      subject_id: input.subjectId,
      amount: input.amount,
      points_redeemed: input.pointsRedeemed ?? 0,
      outcome: input.outcome,
    },
    idempotencyKey: stableIdempotencyKey('payment', input),
  })
}

// ── 通知與行事曆 ─────────────────────────────────────

export interface NotificationRecord {
  id: string
  category: string
  title: string
  body: string
  deepLink: string | null
  readAt: string | null
  createdAt: string
}

export interface NotificationInbox {
  unreadCount: number
  items: NotificationRecord[]
  quietHoursActive: boolean
}

export function listNotifications(unreadOnly = false): Promise<NotificationInbox> {
  return request(`${BASE}/notifications`, { query: { unread_only: unreadOnly } })
}

export function markNotificationRead(notificationId: string): Promise<NotificationRecord> {
  return request(`${BASE}/notifications/${encodeURIComponent(notificationId)}/read`, {
    method: 'POST',
    body: {},
  })
}

export interface CalendarEvent {
  id: string
  title: string
  startsAt: string
  endsAt: string
  allDay: boolean
  note: string | null
  status: string
  source: { type: string; id: string | null }
  recurrence: Record<string, unknown> | null
}

export function listCalendarEvents(range?: { start?: string; end?: string }): Promise<CalendarEvent[]> {
  return request(`${BASE}/calendar/events`, { query: { ...range } })
}

export function createCalendarEvent(input: {
  title: string
  startsAt: string
  endsAt: string
  allDay?: boolean
  note?: string
  recurrence?: Record<string, unknown> | null
}): Promise<CalendarEvent> {
  return request(`${BASE}/calendar/events`, {
    body: {
      title: input.title,
      starts_at: input.startsAt,
      ends_at: input.endsAt,
      all_day: input.allDay ?? false,
      note: input.note ?? null,
      recurrence: input.recurrence ?? null,
    },
    idempotencyKey: stableIdempotencyKey('calendar-create', input),
  })
}

// ── Provider workspace(partner staff) ──────────────

export function getProviderSnapshot(): Promise<Record<string, unknown>> {
  return request(`${BASE}/provider/snapshot`)
}

export interface ProviderSettlementFee {
  id: string
  subjectType: string
  subjectId: string
  kind: 'charge' | 'reversal' | string
  amount: number
  rateBps: number
  eventId: string
  reversalOf: string | null
  createdAt: string
}

export interface ProviderSettlement {
  providerId: string
  fees: ProviderSettlementFee[]
  netAmount: number
  rateBps: number
  dataSource: string
  officialRate: boolean
}

export function getProviderSettlement(): Promise<ProviderSettlement> {
  return request(`${BASE}/provider/settlement`)
}

export function getProviderCatalog(providerId?: string): Promise<Record<string, unknown>> {
  return request(`${BASE}/provider/catalog`, { query: { providerId } })
}

export function getProviderAvailability(params?: {
  offeringId?: string
}): Promise<CatalogSlot[]> {
  return request(`${BASE}/provider/availability`, { query: { ...params } })
}

/** 工作台接入廠商:整批回報可服務時段;標準接入回 409(availability 由廠商系統維護)。 */
export function saveProviderAvailability(slots: Array<Record<string, unknown>>): Promise<{
  saved: boolean
  sync: unknown
}> {
  return request(`${BASE}/provider/availability`, { method: 'PUT', body: { slots } })
}

// ── 社區公告 ─────────────────────────────────────

export interface CommunityAnnouncement {
  id: string
  communityId: string
  title: string
  body: string
  publishedBy: string
  publishedAt: string
}

export function listCommunityAnnouncements(communityId: string): Promise<CommunityAnnouncement[]> {
  return request(`/api/v1/platform/communities/${encodeURIComponent(communityId)}/announcements`)
}

export function publishCommunityAnnouncement(
  communityId: string,
  input: { title: string; body: string },
): Promise<CommunityAnnouncement> {
  return request(`/api/v1/platform/communities/${encodeURIComponent(communityId)}/announcements`, {
    body: input,
    idempotencyKey: stableIdempotencyKey(`announce-${communityId}`, input),
  })
}

// ── 平台管理(operator) ─────────────────────────────

export interface CatalogHealthRow {
  providerId: string
  seedVersion: string
  syncedAt: string
  offerings: number
  availableSlots: number
}

export function getCatalogHealth(): Promise<CatalogHealthRow[]> {
  return request(`${BASE}/catalog/health`)
}

export function syncCatalog(): Promise<{ status: string; providers?: unknown[] }> {
  return request(`${BASE}/catalog/sync`, { method: 'POST', body: {} })
}

export function resetDemo(): Promise<Record<string, unknown>> {
  return request(`${BASE}/demo/reset`, { method: 'POST', body: {} })
}

export interface DemoPersona {
  membershipId: string
  accountId: string
  displayName: string
  role: string
  demoWorkspaceId: string
  workspace: { id: string; kind: string; ownerRef: string; name: string }
}

export function listDemoPersonas(): Promise<DemoPersona[]> {
  return request('/api/v1/admin/demo-personas')
}

/** 重置單一固定 Demo persona 的個人 workspace(operator)。 */
export function resetPersonaWorkspace(membershipId: string): Promise<Record<string, unknown>> {
  return request(`${BASE}/admin/workspaces/${encodeURIComponent(membershipId)}/reset`, {
    method: 'POST',
    body: {},
  })
}

export interface UpstreamHealth {
  status: string
  seedVersion: string | null
  platformSeedVersions: string[]
  consistent?: boolean
}

export function getUpstreamHealth(): Promise<UpstreamHealth> {
  return request(`${BASE}/admin/upstream-health`)
}

/** 故障注入代理(operator;control key 只存在後端;一次性 fault)。 */
export function injectUpstreamFault(
  action: 'timeout' | 'http_503' | 'clear',
): Promise<{ action: string; result: unknown }> {
  return request(`${BASE}/admin/upstream-faults`, {
    body: { action, method: 'POST', path: '/partner/v1/bookings' },
    idempotencyKey: stableIdempotencyKey('fault', { action, at: Date.now() }),
  })
}
