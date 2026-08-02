// M8 Agent client:與手動 UI 共用同一批 Platform API 服務;
// 對話與草稿都持久化在後端,側欄與 AI 頁讀寫同一份。
import { request } from './http'

const BASE = '/api/v1/platform'

export interface AgentProposal {
  id: string
  providerId: string
  providerName: string
  offeringId: string
  offeringName: string
  fulfillmentKind: 'booking' | 'commerce' | string
  basePrice: number
  slot: { id: string; startsAt: string; endsAt: string } | null
  reasons: string[]
}

export interface AgentSubtask {
  id: string
  goal: string
  domain: string | null
  time: { date: string | null; endDate: string | null; echo: string | null } | null
  status: 'resolved' | 'clarify' | 'fields' | 'ready' | 'submitted' | string
  clarify: string | null
  clarifyOptions: Array<{ domain: string; label: string }>
  proposals: AgentProposal[]
  selected: AgentProposal | null
  draftId: string | null
  missingFields: string[]
  quote?: { payable: number; subtotal: number }
  subjectType: string | null
  subjectId: string | null
}

export interface AgentMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface AgentToolResult {
  actionId: string
  status: string
  facts: Record<string, unknown>
  cards: Array<Record<string, unknown>>
  warnings: string[]
  retryPolicy?: string
  auditRef?: string | null
}

export interface AgentCitation {
  articleId: string
  section?: string
  title?: string
  updatedAt?: string
  domain?: string
}

export interface AgentLastTurn {
  intent?: string
  citedKnowledge?: AgentCitation[]
  toolResults?: AgentToolResult[]
  groundedResponse?: {
    answer?: string
    source?: string
    warnings?: string[]
    reason?: string
  } | null
}

export interface AgentSession {
  id: string
  title?: string
  status?: 'active' | 'waiting_confirmation' | 'task_created' | 'archived' | string
  summary?: string
  messages: AgentMessage[]
  subtasks: AgentSubtask[]
  awaiting: 'clarify' | 'option' | 'fields' | 'grant' | null
  grantId: string | null
  pendingGrantId?: string | null
  activeTaskPackageId?: string | null
  archivedAt?: string | null
  version?: number
  createdAt?: string
  updatedAt?: string
  lastTurn?: AgentLastTurn | null
}

export type AgentSessionSummary = Pick<AgentSession,
  'id' | 'title' | 'status' | 'summary' | 'pendingGrantId' | 'archivedAt' | 'version' | 'createdAt' | 'updatedAt'
>

export interface AgentTurnResult {
  session: AgentSession
  stages: string[]
}

export type AgentAction =
  | { type: 'clarify_option'; subtaskId: string; domain: string; label: string }
  | { type: 'select_option'; subtaskId: string; optionId: string }
  | { type: 'approve_grant' }
  | { type: 'revoke_grant' }

export function sendAgentMessage(input: {
  sessionId?: string | null
  message?: string
  action?: AgentAction
}): Promise<AgentTurnResult> {
  return request(`${BASE}/agent/messages`, {
    body: {
      session_id: input.sessionId ?? null,
      message: input.message ?? null,
      action: input.action ?? null,
    },
  })
}

/**
 * 串流版:先逐行收到可驗證階段(如「查詢可用方案與時段」),最後收到完整結果。
 * onStage 每收到一個階段就呼叫;回傳最終 AgentTurnResult。
 */
export async function sendAgentMessageStream(
  input: { sessionId?: string | null; message?: string; action?: AgentAction },
  onStage: (stage: string) => void,
): Promise<AgentTurnResult> {
  const { currentAuthorizationHeaders } = await import('../stores/session')
  const response = await fetch(`${BASE}/agent/messages/stream`, {
    method: 'POST',
    headers: {
      Accept: 'application/x-ndjson',
      'Content-Type': 'application/json',
      ...currentAuthorizationHeaders(),
    },
    body: JSON.stringify({
      session_id: input.sessionId ?? null,
      message: input.message ?? null,
      action: input.action ?? null,
    }),
  })
  if (!response.ok || !response.body) {
    throw new Error(`Agent 回應失敗(${response.status})`)
  }
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let result: AgentTurnResult | null = null
  for (;;) {
    const { value, done } = await reader.read()
    if (value) buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''
    for (const line of lines) {
      if (!line.trim()) continue
      const parsed = JSON.parse(line) as { stage?: string; result?: { data?: AgentTurnResult } & AgentTurnResult }
      if (parsed.stage) onStage(parsed.stage)
      if (parsed.result) result = (parsed.result as { data?: AgentTurnResult }).data ?? (parsed.result as AgentTurnResult)
    }
    if (done) break
  }
  if (!result) throw new Error('Agent 串流沒有回傳結果')
  return result
}

export function getLatestAgentSession(): Promise<AgentSession | null> {
  return request(`${BASE}/agent/sessions/latest`)
}

export function getAgentSessions(includeArchived = false): Promise<AgentSessionSummary[]> {
  return request(`${BASE}/agent/sessions`, { query: { include_archived: includeArchived } })
}

export function createAgentSession(title?: string): Promise<AgentSession> {
  return request(`${BASE}/agent/sessions`, {
    body: { title: title?.trim() || null },
  })
}

export function renameAgentSession(sessionId: string, title: string, expectedVersion: number): Promise<AgentSession> {
  return request(`${BASE}/agent/sessions/${encodeURIComponent(sessionId)}`, {
    method: 'PATCH',
    body: { title, expected_version: expectedVersion },
  })
}

export function archiveAgentSession(sessionId: string, expectedVersion: number): Promise<AgentSession> {
  return request(`${BASE}/agent/sessions/${encodeURIComponent(sessionId)}/archive`, {
    body: { expected_version: expectedVersion },
  })
}

export function restoreAgentSession(sessionId: string, expectedVersion: number): Promise<AgentSession> {
  return request(`${BASE}/agent/sessions/${encodeURIComponent(sessionId)}/restore`, {
    body: { expected_version: expectedVersion },
  })
}

export function getAgentSession(sessionId: string): Promise<AgentSession> {
  return request(`${BASE}/agent/sessions/${encodeURIComponent(sessionId)}`)
}

export interface ExecutionGrant {
  id: string
  providerIds: string[]
  windowStart: string
  windowEnd: string
  budgetLimit: number
  pointsLimit: number
  status: 'proposed' | 'approved' | 'revoked' | 'expired' | string
  expiresAt: string
  summary: string
}

export function getExecutionGrant(grantId: string): Promise<ExecutionGrant> {
  return request(`${BASE}/agent/grants/${encodeURIComponent(grantId)}`)
}
