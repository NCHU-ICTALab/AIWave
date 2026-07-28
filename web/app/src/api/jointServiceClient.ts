export type JointServiceStatus = 'draft' | 'collecting' | 'proposal_review' | 'assigned' | 'in_progress' | 'completed'

export interface JointProposal {
  id: string
  vendorId: string
  vendorName: string
  badge: string
  items: Array<{ name: string; amount: number }>
  total: number
  perUnit: number
  availableSlots: string[]
  strengths: string[]
  concerns: string[]
  score: number
  source: string
  sourceLabel: string
}

export interface JointServiceCampaign {
  id: number
  communityId: string
  title: string
  serviceId: string
  status: JointServiceStatus
  statusLabel: string
  demand: {
    householdCount: number
    unitCount: number
    equipment?: Array<{ label: string; count: number }>
    timePreferences?: Array<{ label: string; households: number }>
    specialRequirements?: string[]
    privacy?: string
    sourceLabel?: string
  }
  draft: { notification?: string; questionnaire?: string[]; generatedBy?: string; serviceContext?: string }
  proposals: JointProposal[]
  selectedProposalId: string | null
  selectedProposal: JointProposal | null
  events: Array<{ type: string; actor: string; detail: string; occurredAt: string }>
  dataNotice: string
  myParticipation?: {
    units: number
    equipment: string
    preferredSlot: string
    specialRequirement: string | null
    consentVersion: string
    consentedAt: string
  } | null
}

export class JointServiceApiError extends Error {
  constructor(readonly status: number, message: string) {
    super(message)
    this.name = 'JointServiceApiError'
  }
}

interface ClientOptions { fetcher?: typeof fetch; baseUrl?: string; accountId?: string | null }

export function createJointServiceClient(options: ClientOptions = {}) {
  const baseUrl = options.baseUrl ?? '/api/v1'
  async function request<T>(path: string, role: 'user' | 'manager' | 'partner', init: RequestInit = {}): Promise<T> {
    const response = await (options.fetcher ?? globalThis.fetch)(`${baseUrl}${path}`, {
      ...init,
      credentials: 'same-origin',
      headers: {
        Accept: 'application/json', 'Content-Type': 'application/json', 'X-Role': role,
        ...(options.accountId ? { 'X-Account-Id': options.accountId } : {}), ...init.headers,
      },
    })
    if (!response.ok) {
      const payload = await response.json().catch(() => ({})) as { detail?: string }
      throw new JointServiceApiError(response.status, payload.detail ?? '聯合服務操作未完成，請稍後再試。')
    }
    return ((await response.json()) as { data: T }).data
  }

  return {
    residentList: () => request<JointServiceCampaign[]>('/groups/joint-services', 'user'),
    join: (campaignId: number, input: {
      units: number; equipment: string; preferredSlot: string; specialRequirement?: string
    }) => request<JointServiceCampaign>(`/community/joint-services/${campaignId}/join`, 'user', {
      method: 'POST',
      body: JSON.stringify({
        units: input.units, equipment: input.equipment, preferred_slot: input.preferredSlot,
        special_requirement: input.specialRequirement || null, consent: true,
      }),
    }),
    managerList: () => request<JointServiceCampaign[]>('/community/joint-services', 'manager'),
    create: (title: string) => request<JointServiceCampaign>('/community/joint-services', 'manager', {
      method: 'POST', body: JSON.stringify({ title, service_id: 'service-aircon' }),
    }),
    publish: (campaignId: number) => request<JointServiceCampaign>(
      `/community/joint-services/${campaignId}/publish`, 'manager', { method: 'POST' },
    ),
    prepareProposals: (campaignId: number) => request<JointServiceCampaign>(
      `/community/joint-services/${campaignId}/prepare-proposals`, 'manager', { method: 'POST' },
    ),
    assign: (campaignId: number, proposalId: string) => request<JointServiceCampaign>(
      `/community/joint-services/${campaignId}/assign`, 'manager',
      { method: 'POST', body: JSON.stringify({ proposal_id: proposalId }) },
    ),
    partnerList: () => request<JointServiceCampaign[]>('/vendor/joint-services', 'partner'),
    start: (campaignId: number) => request<JointServiceCampaign>(
      `/vendor/joint-services/${campaignId}/start`, 'partner', { method: 'POST' },
    ),
    complete: (campaignId: number, note: string) => request<JointServiceCampaign>(
      `/vendor/joint-services/${campaignId}/complete`, 'partner',
      { method: 'POST', body: JSON.stringify({ note }) },
    ),
  }
}
