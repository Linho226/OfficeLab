export type FileItem = {
  id: string
  parent_id: string | null
  name: string
  kind: 'folder' | 'file'
}

export type Checkpoint = {
  items: FileItem[]
  processed_event_ids: string[]
  observed_actions: string[]
}

export type Scenario = {
  code: string
  title: string
  runtime: string
  version: number
  schema_version: string
  locale: string
  instructions: string[]
  initial_state: { root_id: string; items: FileItem[] }
  allowed_actions: string[]
  hints_count: number
}

export type Attempt = {
  id: string
  scenario: Pick<Scenario, 'code' | 'version' | 'title' | 'instructions' | 'initial_state'>
  status: string
  score: number | null
  checkpoint: Checkpoint
  hints: Array<{ level: number; text: string }>
  hints_count: number
  evaluation: Evaluation | null
}

export type AttemptSummary = { id: string; updated_at: string; version: number }

export type Evaluation = {
  attempt_id: string
  score: number
  passed: boolean
  criteria: Array<{
    code: string
    passed: boolean
    points_awarded: number
    points_available: number
    feedback: string | null
  }>
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  headers.set('Accept', 'application/json')
  if (options.body) headers.set('Content-Type', 'application/json')
  const csrfToken = readCookie('csrftoken')
  if (csrfToken) headers.set('X-CSRFToken', csrfToken)

  const response = await fetch(path, {
    ...options,
    headers,
    credentials: 'same-origin',
  })
  if (response.status === 204) return undefined as T

  const payload = await response.json()
  if (!response.ok) {
    const detail =
      typeof payload.detail === 'string'
        ? payload.detail
        : Object.values(payload).flat().join(' ')
    throw new Error(detail || 'Une erreur inattendue est survenue.')
  }
  return payload as T
}

function readCookie(name: string): string | null {
  const prefix = `${name}=`
  const cookie = document.cookie
    .split(';')
    .map((value) => value.trim())
    .find((value) => value.startsWith(prefix))
  return cookie ? decodeURIComponent(cookie.slice(prefix.length)) : null
}

export function newEventId(): string {
  return crypto.randomUUID()
}
