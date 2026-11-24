import { request } from './client'

export interface UserCandidate {
  name: string
  longitude: number
  latitude: number
  address?: string
  stay_minutes?: number
  opening_start?: string | null
  opening_end?: string | null
  cost_yuan?: number | null
  must_visit?: boolean
}
export interface SelectedPoi {
  id: string
  name: string
}
export interface GuideReference {
  place_name: string
  excerpt: string
  source_url: string | null
}

export interface StayReference {
  from_minutes: number
  to_minutes: number
  source: string
  source_url: string | null
}

export interface RunCreate {
  client_request_id: string
  kind: 'plan' | 'story'
  goal: string
  city_adcode: string
  city_name: string
  start_date: string
  days: number
  daily_start: string
  daily_end: string
  budget_yuan: number | null
  transport: 'walking' | 'transit' | 'driving'
  pace: 'relaxed' | 'balanced'
  interests: string[]
  must_visit: string[]
  candidates: UserCandidate[]
  selected_pois?: SelectedPoi[]
  guide_references?: GuideReference[]
  allow_external: boolean
  allow_model: boolean
  allow_memory_access: boolean
  memory_ids: string[]
  chat_message?: string
  previous_run_id?: string
}
export interface AgentCandidate extends UserCandidate {
  id: string
  source: 'amap' | 'user_provided'
  verification: string
  source_url: string | null
  queried_at: string
}
export interface AgentStop {
  candidate_id: string
  name: string
  longitude: number
  latitude: number
  arrival: string
  departure: string
  stay_minutes: number
  stay_source?: 'guide_reference' | 'user_provided' | 'planning_assumption'
  stay_references?: StayReference[]
  timing_basis: 'provider' | 'planning_buffer' | 'user_schedule'
  source: string
}
export interface AgentDay {
  day: number
  date: string
  start: string
  end: string
  total_minutes: number
  stops: AgentStop[]
  legs: Array<{
    from_id: string
    to_id: string
    duration_minutes: number | null
    distance_meters: number | null
    source: string
    queried_at: string | null
    mode?: RunCreate['transport']
    instructions?: string[]
  }>
}
export interface AgentEvent {
  sequence: number
  at: string
  stage: string
  tool: string
  status: string
  message: string
  attempt: number
  duration_ms?: number
  details?: Record<string, unknown>
}
export interface AgentResult {
  intent_source: 'local_rules' | 'deepseek'
  verification_status: 'validated' | 'conditional' | 'conflict' | 'information_missing'
  summary: string
  warnings: string[]
  unknowns: string[]
  candidates?: AgentCandidate[]
  days?: AgentDay[]
  constraints?: Record<string, unknown>
  validation?: {
    checks: Array<{ code: string; status: string; message: string }>
    known_cost_yuan: number
    unknown_cost_count: number
  }
  source_memories?: Array<{
    id: string
    title: string
    body: string
    date: string
    city: string
    photo_count: number
    vlog_count: number
  }>
  story_body?: string
  chat?: Array<{ role: 'user' | 'assistant'; text: string }>
  city_guide?: { title: string; note: string; source: string; reference_url: string } | null
}
export interface AgentRun {
  id: string
  kind: 'plan' | 'story'
  status: 'running' | 'needs_input' | 'awaiting_confirmation' | 'confirmed' | 'failed'
  revision: number
  title: string
  request: Record<string, unknown>
  result: AgentResult
  events: AgentEvent[]
  created_at: string
  updated_at: string
  saved_artifact_id: string | null
}
export interface AgentCapabilities {
  amap_configured: boolean
  model_configured: boolean
  chat_model_configured?: boolean
  intent_default: string
  privacy_notice: string
  limits: Record<string, number>
  tools: string[]
}
export interface CompanionMessage {
  role: 'user' | 'assistant'
  text: string
  sources?: Array<{ label: string; url: string }>
}
export interface CompanionReply {
  text: string
  planning_request?: string | null
  choices?: Array<{ label: string; message: string }>
  sources?: CompanionMessage['sources']
  source: 'local' | 'deepseek'
}
export interface Confirmation {
  confirmation_token: string
  content_digest: string
  expires_at: string
  revision: number
  summary: string
  requires_unverified_acknowledgement: boolean
}
export interface DraftEdit {
  expected_revision: number
  title?: string
  story_body?: string
  excluded_candidate_ids?: string[]
  daily_end?: string
  guide_references?: GuideReference[]
}
export const getAgentCapabilities = () => request<AgentCapabilities>('/agent/capabilities')
export const sendCompanionMessage = (payload: {
  message: string
  city_adcode: string
  plan_id?: string
  history: Array<Pick<CompanionMessage, 'role' | 'text'>>
  allow_model: boolean
}) => request<CompanionReply>('/agent/companion', { method: 'POST', body: JSON.stringify(payload) })
export const listAgentRuns = () => request<{ items: AgentRun[] }>('/agent/runs')
export const getAgentRun = (id: string) =>
  request<AgentRun>(`/agent/runs/${encodeURIComponent(id)}`)
export const createAgentRun = (payload: RunCreate) =>
  request<AgentRun>('/agent/runs', { method: 'POST', body: JSON.stringify(payload) })
export const editAgentDraft = (id: string, payload: DraftEdit) =>
  request<AgentRun>(`/agent/runs/${encodeURIComponent(id)}/draft`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
export const previewAgentConfirmation = (run: AgentRun) =>
  request<Confirmation>(`/agent/runs/${encodeURIComponent(run.id)}/confirmation`, {
    method: 'POST',
    body: JSON.stringify({ expected_revision: run.revision }),
  })
export const confirmAgentRun = (run: AgentRun, proof: Confirmation, ack: boolean) =>
  request<AgentRun>(`/agent/runs/${encodeURIComponent(run.id)}/confirm`, {
    method: 'POST',
    body: JSON.stringify({
      expected_revision: run.revision,
      confirmation_token: proof.confirmation_token,
      content_digest: proof.content_digest,
      acknowledge_unverified: ack,
    }),
  })
