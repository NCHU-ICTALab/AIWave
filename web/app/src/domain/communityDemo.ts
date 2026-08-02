export type DemoSupplierType = 'external' | 'group'

export type DemoGroupBuyStatus = 'draft' | 'open' | 'achieved' | 'pickup' | 'completed' | 'closed' | 'failed'

export type DemoRepairStatus = 'received' | 'assigned' | 'in_progress' | 'completed'

export interface CommunityProfile {
  id: string
  name: string
  address: string
  builtYear: number
  buildings: string
  floors: string
  households: number
  parking: string
  evChargers: number
  facilities: string[]
  propertyManager: string
  managementHours: string
}

export interface DemoAnnouncement {
  id: string
  title: string
  body: string
  publishedAt: string
  category: 'maintenance' | 'notice' | 'meeting' | 'group-buy'
}

export interface DemoPackage {
  id: string
  carrier: string
  arrivedAt: string
  trackingLast4: string
  pickupCode: string
  status: 'waiting'
}

export interface DemoRepair {
  id: string
  subject: string
  location: string
  reportedAt: string
  status: DemoRepairStatus
  statusLabel: string
  note: string
}

export interface DemoMaintenance {
  id: string
  name: string
  lastServicedAt: string
  nextDueAt: string
  status: 'on_track' | 'overdue'
  statusLabel: string
}

export interface DemoFacilityReservation {
  id: string
  facility: string
  date: string
  time: string
  resident: string
}

export interface DemoServiceOffer {
  id: string
  name: string
  marketPrice: number
  communityPrice: number
  note: string
}

export interface DemoGroupBuyVariant {
  id: string
  label: string
  price: number
}

export interface DemoGroupBuyJoin {
  householdId: string
  displayName: string
  householdLabel: string
  variantId: string
  variantLabel: string
  quantity: number
  amount: number
  joinedAt: string
}

export interface DemoGroupBuy {
  id: string
  name: string
  description: string
  marketPrice: number
  variants: DemoGroupBuyVariant[]
  thresholdUnits: number
  seededProgressUnits: number
  progressUnits: number
  pickupLocation: string
  expectedArrival: string
  closeAt: string
  supplierType: DemoSupplierType
  supplierName: string
  supplierFeeRate: number
  status: DemoGroupBuyStatus
  statusLabel: string
  published: boolean
  publishedAt: string | null
  joins: DemoGroupBuyJoin[]
}

export interface DemoOrder {
  id: string
  groupBuyId: string
  groupBuyName: string
  householdId: string
  displayName: string
  householdLabel: string
  variantId: string
  variantLabel: string
  quantity: number
  amount: number
  status: 'joined'
  joinedAt: string
}

export interface DemoWikiEntry {
  id: string
  category: string
  title: string
  keywords: string[]
  shortAnswer: string
  fullRule: string
  source: string
  updatedAt: string
  relatedQuestions: string[]
}

export interface DemoCommunityAnswer {
  query: string
  matched: boolean
  shortAnswer: string
  fullRule: string
  source: string | null
  updatedAt: string | null
  relatedQuestions: string[]
  wikiEntryId: string | null
}

export interface DemoUnansweredQuestion {
  id: string
  query: string
  householdId: string
  askedAt: string
  status: 'new' | 'to_supplement'
}

export interface DemoWikiAnalytics {
  queryRanking: Array<{ query: string; count: number }>
  latestQueries: string[]
  unanswered: DemoUnansweredQuestion[]
}

export interface DemoResidentDashboard {
  community: CommunityProfile
  resident: {
    householdId: string
    displayName: string
    householdLabel: string
    householdMembers: string
    residenceType: string
    pastGroupBuys: number
  }
  announcements: DemoAnnouncement[]
  packages: DemoPackage[]
  repairs: DemoRepair[]
  maintenance: DemoMaintenance[]
  reservations: DemoFacilityReservation[]
  activeGroupBuys: DemoGroupBuy[]
  groupBuyHistory: DemoGroupBuy[]
  serviceOffers: DemoServiceOffer[]
}

export interface DemoCommitteeDashboard {
  community: CommunityProfile
  manager: { displayName: string; householdLabel: string; term: string }
  draftGroupBuy: DemoGroupBuy | null
  groupBuys: DemoGroupBuy[]
  orders: DemoOrder[]
  ordersByHousehold: Array<{
    householdId: string
    householdLabel: string
    displayName: string
    amount: number
    items: DemoOrder[]
  }>
  variantSummary: Array<{ variantLabel: string; quantity: number; amount: number }>
  wiki: DemoWikiAnalytics
  kpis: {
    groupBuyRevenue: number
    externalCommission: number
    openGroupBuys: number
    savedForResidents: number
  }
}

export interface DemoSubscriptionSummary {
  householdCount: number
  standardPlanLabel: string
  standardMonthlyFee: number
  trialMonthlyFee: number
  residentSavings: number
  netBenefit: number
  externalSupplierFeeRate: number
  groupSupplierFeeRate: number
  trialMonths: string
  hardware: string
}

export interface PublishDemoGroupBuyInput {
  name?: string
  description?: string
  marketPrice?: number
  variants?: DemoGroupBuyVariant[]
  thresholdUnits?: number
  pickupLocation?: string
  expectedArrival?: string
  closeAt?: string
  supplierType?: DemoSupplierType
  supplierName?: string
}

export interface UpdateDemoGroupBuyInput {
  name?: string
  marketPrice?: number
  thresholdUnits?: number
  pickupLocation?: string
  expectedArrival?: string
  closeAt?: string
}

export interface JoinGroupBuyInput {
  groupBuyId: string
  variantId: string
  quantity: number
  householdId: string
  displayName?: string
  householdLabel?: string
}

export const DEMO_HOUSEHOLD_ID = 'household-wang-xiaoming'
export const DEMO_MANAGER_HOUSEHOLD_LABEL = 'A 棟 8F-1'
