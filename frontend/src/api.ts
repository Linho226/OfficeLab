export type FileItem = {
  id: string
  parent_id: string | null
  name: string
  kind: 'folder' | 'file'
}

export type TrashEntry = {
  items: FileItem[]
  original_parent_id: string
}

export type HistorySnapshot = {
  items: FileItem[]
  trash?: Record<string, TrashEntry>
  observed_actions: string[]
}

export type Checkpoint = {
  items: FileItem[]
  trash?: Record<string, TrashEntry>
  processed_event_ids: string[]
  observed_actions: string[]
  undo_stack?: HistorySnapshot[]
  redo_stack?: HistorySnapshot[]
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
  scenario: Pick<Scenario, 'code' | 'version' | 'title' | 'instructions' | 'initial_state' | 'allowed_actions'>
  status: string
  score: number | null
  checkpoint: Checkpoint
  hints: Array<{ level: number; text: string }>
  hints_count: number
  evaluation: Evaluation | null
}

export type AttemptSummary = { id: string; updated_at: string; version: number; code: string; title: string }

export type Mission = {
  code: string
  title: string
  version: number
  instructions: string[]
  order: number
  passed: boolean
  best_score: number | null
  resume_id: string | null
}

export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) { super(message); this.status = status }
}

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

  let payload
  try { payload = await response.json() }
  catch { throw new ApiError('Le serveur ne répond pas correctement. Réessayez dans un instant.', response.status) }
  if (!response.ok) {
    const detail =
      typeof payload.detail === 'string'
        ? payload.detail
        : Object.values(payload).flat().join(' ')
    throw new ApiError(detail || 'Une erreur inattendue est survenue.', response.status)
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
