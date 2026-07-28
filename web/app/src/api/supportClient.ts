export interface SupportDiagnostic {
  subject: { type: 'inquiry' | 'order'; id: string; status: string; statusLabel: string }
  issueText: string
  category: string
  categoryLabel: string
  priority: 'high' | 'medium' | 'normal'
  slaHours: number
  dueAt: string
  recommendedRoute: string
  evidence: string[]
  computedBy: 'deterministic_rules'
  diagnosisToken: string
  previewExpiresInSeconds: number
}

export interface SupportTicket {
  id: string
  accountId: string
  subjectType: 'inquiry' | 'order'
  subjectId: string
  category: string
  categoryLabel: string
  issueText: string
  status: 'open' | 'in_progress' | 'resolved'
  statusLabel: string
  priority: 'high' | 'medium' | 'normal'
  slaHours: number
  dueAt: string
  asOf?: string
  events: Array<{ type: string; actor: string; occurred_at: string; detail?: string | null }>
}

export class SupportApiError extends Error {
  constructor(readonly status: number, message: string) {
    super(message)
    this.name = 'SupportApiError'
  }
}

interface ClientOptions { fetcher?: typeof fetch; baseUrl?: string }

export function createSupportClient(options: ClientOptions = {}) {
  const baseUrl = options.baseUrl ?? '/api/v1'

  async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const fetcher = options.fetcher ?? globalThis.fetch
    const response = await fetcher(`${baseUrl}${path}`, {
      ...init,
      credentials: 'same-origin',
      headers: { Accept: 'application/json', 'Content-Type': 'application/json', ...init.headers },
    })
    if (!response.ok) {
      const payload = await response.json().catch(() => ({})) as { detail?: string }
      throw new SupportApiError(response.status, payload.detail ?? '客服服務暫時無法使用，請稍後再試。')
    }
    return ((await response.json()) as { data: T }).data
  }

  const identity = (accountId: string | null, role: 'user' | 'manager') => ({
    'X-Account-Id': accountId ?? '', 'X-Role': role,
  })
  const payload = (subjectId: string, issueText: string) => ({ subject_id: subjectId, issue_text: issueText })

  return {
    diagnose: (accountId: string, subjectId: string, issueText: string) =>
      request<SupportDiagnostic>('/support/diagnose', {
        method: 'POST', headers: identity(accountId, 'user'), body: JSON.stringify(payload(subjectId, issueText)),
      }),
    create: (accountId: string, subjectId: string, issueText: string, diagnosisToken: string) =>
      request<SupportTicket>('/support/tickets', {
        method: 'POST', headers: identity(accountId, 'user'),
        body: JSON.stringify({ ...payload(subjectId, issueText), diagnosis_token: diagnosisToken }),
      }),
    listMine: (accountId: string) =>
      request<SupportTicket[]>('/support/tickets', { headers: identity(accountId, 'user') }),
    queue: () => request<SupportTicket[]>('/support/queue', {
      headers: identity(null, 'manager'),
    }),
    start: (ticketId: string) =>
      request<SupportTicket>(`/support/tickets/${encodeURIComponent(ticketId)}/start`, {
        method: 'POST', headers: identity(null, 'manager'), body: JSON.stringify({}),
      }),
    resolve: (ticketId: string, note: string) =>
      request<SupportTicket>(`/support/tickets/${encodeURIComponent(ticketId)}/resolve`, {
        method: 'POST', headers: identity(null, 'manager'), body: JSON.stringify({ note }),
      }),
  }
}
