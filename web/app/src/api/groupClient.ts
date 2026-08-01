export interface GroupMember {
  accountId: string
  displayName: string
  role: 'admin' | 'member'
  roleLabel: string
  joinedAt?: string
}

export interface MemberGroup {
  id: string
  name: string
  inviteCode: string
  myRole: 'admin' | 'member'
  myRoleLabel: string
  memberCount?: number
  members: GroupMember[]
  createdAt: string
  updatedAt?: string
}

interface ClientOptions {
  fetcher?: typeof fetch
  baseUrl?: string
  accountId: string | null
}

export function createGroupClient(options: ClientOptions) {
  const baseUrl = options.baseUrl ?? '/api/v1'
  const operationKey = (action: string, value: string) =>
    `web:group:${action}:${value.trim().toLocaleLowerCase('zh-TW').replace(/\s+/g, '-')}`

  async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const response = await (options.fetcher ?? globalThis.fetch)(`${baseUrl}${path}`, {
      ...init,
      credentials: 'same-origin',
      headers: {
        Accept: 'application/json', 'Content-Type': 'application/json',
        ...currentAuthorizationHeaders(),
        ...init.headers,
      },
    })
    if (!response.ok) {
      const payload = await response.json().catch(() => ({})) as { detail?: string }
      throw new Error(typeof payload.detail === 'string' ? payload.detail : '群組操作未完成，請稍後再試。')
    }
    return ((await response.json()) as { data: T }).data
  }

  return {
    list: () => request<MemberGroup[]>('/groups'),
    create: (payload: { name: string; display_name: string }) =>
      request<MemberGroup>('/groups', {
        method: 'POST', headers: { 'Idempotency-Key': operationKey('create', payload.name) },
        body: JSON.stringify(payload),
      }),
    join: (payload: { invite_code: string; display_name: string }) =>
      request<MemberGroup>('/groups/join', {
        method: 'POST', headers: { 'Idempotency-Key': operationKey('join', payload.invite_code) },
        body: JSON.stringify(payload),
      }),
    rename: (groupId: string, name: string) =>
      request<MemberGroup>(`/groups/${encodeURIComponent(groupId)}`, {
        method: 'PATCH', headers: { 'Idempotency-Key': operationKey(`rename-${groupId}`, name) },
        body: JSON.stringify({ name }),
      }),
    leave: (groupId: string) => request<MemberGroup>(
      `/groups/${encodeURIComponent(groupId)}/members/me`, {
        method: 'DELETE', headers: { 'Idempotency-Key': operationKey('leave', groupId) },
      },
    ),
  }
}
import { currentAuthorizationHeaders } from '@/stores/session'
