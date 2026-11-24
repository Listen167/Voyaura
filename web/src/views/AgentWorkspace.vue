<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import {
  ArrowLeft,
  ArrowRight,
  BookOpen,
  Check,
  ChevronRight,
  CircleCheck,
  Compass,
  History,
  LoaderCircle,
  MapPin,
  Plus,
  RefreshCw,
  Route,
  ShieldCheck,
  Sparkles,
  Trash2,
  CalendarDays,
  ChevronDown,
  Clock3,
  ListChecks,
  Map,
  Sun,
  Wallet,
  SlidersHorizontal,
  CircleAlert,
  ArrowUpRight,
} from 'lucide-vue-next'
import { ApiClientError } from '../api/client'
import {
  confirmAgentRun,
  createAgentRun,
  editAgentDraft,
  getAgentCapabilities,
  getAgentRun,
  listAgentRuns,
  previewAgentConfirmation,
} from '../api/agent'
import type {
  AgentCapabilities,
  AgentRun,
  Confirmation,
  RunCreate,
  UserCandidate,
} from '../api/agent'
import AgentRouteMap from '../components/AgentRouteMap.vue'
import UiButton from '../components/UiButton.vue'
import UiStatus from '../components/UiStatus.vue'
import AgentWorkflowSteps from '../components/AgentWorkflowSteps.vue'
import { destinations } from '../content/discovery'
import {
  PRACTICE_MARKER,
  canUsePlannerPractice,
  isPracticeRequest,
  practiceBrief as createPracticeBrief,
} from '../content/plannerPractice'
import type { DiscoveryIntent } from '../content/discovery'

const props = defineProps<{
  initialKind?: 'plan' | 'story'
  initialCity?: string
  initialIntent?: DiscoveryIntent | null
  initialDate?: string
  initialRunId?: string
  confirmLeave?: () => Promise<boolean>
  navigateKind?: (kind: 'plan' | 'story', cityAdcode: string) => void
  archiveCities?: Array<{ adcode: string; name_zh: string }>
}>()
const emit = defineEmits<{
  back: []
  connect: []
  routeTools: []
  memories: []
  dirtyChange: [dirty: boolean]
}>()
const mode = ref<'plan' | 'story'>(props.initialKind ?? 'plan')
const defaultCities = [
  { code: '440100', name: '广州市' },
  { code: '330100', name: '杭州市' },
  { code: '310000', name: '上海市' },
  { code: '110000', name: '北京市' },
  { code: '510100', name: '成都市' },
  { code: '350200', name: '厦门市' },
]
const cities = computed(() => [
  ...new globalThis.Map(
    [
      ...defaultCities,
      ...(props.archiveCities ?? []).map((city) => ({
        code: city.adcode,
        name: city.name_zh,
      })),
    ].map((city) => [city.code, city]),
  ).values(),
])
const cityCode = ref(
  props.initialIntent?.cityAdcode ?? props.initialCity ?? '440100',
)
const goal = ref(props.initialIntent?.goal ?? '')
const localDate = new Date(Date.now() - new Date().getTimezoneOffset() * 60000)
  .toISOString()
  .slice(0, 10)
const startDate = ref(
  props.initialDate && /^\d{4}-\d{2}-\d{2}$/.test(props.initialDate)
    ? props.initialDate
    : localDate,
)
const days = ref(props.initialIntent?.days ?? 2)
const budget = ref<number | ''>('')
const dailyStart = ref('09:00')
const dailyEnd = ref('18:00')
const transport = ref<RunCreate['transport']>('transit')
const pace = ref<RunCreate['pace']>(props.initialIntent?.pace ?? 'relaxed')
const interests = ref(props.initialIntent?.interests?.join('，') ?? '')
const mustVisit = ref('')
const allowExternal = ref(false)
const allowModel = ref(false)
const allowMemory = ref(false)
const candidates = ref<
  Array<
    Omit<UserCandidate, 'longitude' | 'latitude'> & {
      longitude: number | ''
      latitude: number | ''
    }
  >
>([])
const capabilities = ref<AgentCapabilities | null>(null)
const capabilitiesUnavailable = ref(false)
const mapAvailabilityNote = computed(() =>
  capabilities.value
    ? capabilities.value.amap_configured
      ? ''
      : '当前服务尚未配置地图查询，可补充已知地点。'
    : capabilitiesUnavailable.value
      ? '暂时无法读取服务状态，工具可用性以实际执行结果为准。'
      : '正在读取工具服务状态。',
)
const history = ref<AgentRun[]>([])
const run = ref<AgentRun | null>(null)
let alive = true
const activeDay = ref(1)
const busy = ref(false)
const error = ref('')
const errorCode = ref('')
const confirmation = ref<Confirmation | null>(null)
const acknowledged = ref(false)
const editTitle = ref('')
const editStory = ref('')
const revisedEnd = ref('18:00')
const pendingRequest = ref<RunCreate | null>(null)
const showHistory = ref(false)
const resultAnchor = ref<HTMLElement | null>(null)
const briefAnchor = ref<HTMLElement | null>(null)
const confirmationAnchor = ref<HTMLElement | null>(null)
const candidateDetails = ref<HTMLDetailsElement | null>(null)
const editingBrief = ref(false)
const resultTab = ref<'schedule' | 'map' | 'execution'>('schedule')
const practiceBackup = ref<ReturnType<typeof captureBrief> | null>(null)
const practiceEnabled = canUsePlannerPractice()
const practiceNotice = ref<HTMLElement | null>(null)
const inputPractice = computed(
  () =>
    mode.value === 'plan' &&
    isPracticeRequest({ goal: goal.value, candidates: candidates.value }),
)
const resultPractice = computed(
  () => run.value?.kind === 'plan' && isPracticeRequest(run.value.request),
)
const hasLocalPlace = computed(() =>
  candidates.value.some(
    (c) =>
      c.name.trim() &&
      c.longitude !== '' &&
      c.latitude !== '' &&
      Number.isFinite(Number(c.longitude)) &&
      Number.isFinite(Number(c.latitude)),
  ),
)
const needsPlaceSource = computed(
  () =>
    mode.value === 'plan' &&
    !hasPlan.value &&
    !inputPractice.value &&
    !hasLocalPlace.value &&
    (!capabilities.value?.amap_configured || !allowExternal.value),
)
const placeSourceExplanation = computed(() =>
  capabilities.value
    ? capabilities.value.amap_configured
      ? '目前还没有候选地点，也尚未授权在线查询。请补充自己的地点，或在下方允许查询高德。'
      : '当前尚未连接在线地点查询。只填写目的地和旅行想法，还不能生成具体站点；勾选查询授权也不会自动接通服务。'
    : capabilitiesUnavailable.value
      ? '暂时无法确认地点服务状态。你可以补充自己的地点，或稍后重试。'
      : '正在读取地点服务状态。请稍候，或补充自己的地点。',
)
function captureBrief() {
  return {
    goal: goal.value,
    cityCode: cityCode.value,
    startDate: startDate.value,
    days: days.value,
    budget: budget.value,
    dailyStart: dailyStart.value,
    dailyEnd: dailyEnd.value,
    transport: transport.value,
    pace: pace.value,
    interests: interests.value,
    mustVisit: mustVisit.value,
    allowExternal: allowExternal.value,
    allowModel: allowModel.value,
    candidates: candidates.value.map((c) => ({ ...c })),
  }
}
function briefFingerprint() {
  const {
    allowExternal: _external,
    allowModel: _model,
    ...content
  } = captureBrief()
  return JSON.stringify(content)
}
const briefBaseline = ref(briefFingerprint())
const unsavedChanges = computed(() => {
  const briefVisible =
    !run.value || editingBrief.value || run.value.status === 'needs_input'
  const storyEdited =
    run.value?.kind === 'story' &&
    (editTitle.value !== run.value.title ||
      editStory.value !== (run.value.result.story_body ?? ''))
  const scheduleEdited =
    run.value?.kind === 'plan' &&
    revisedEnd.value !== String(run.value.request.daily_end ?? '18:00')
  return (
    (briefVisible && briefFingerprint() !== briefBaseline.value) ||
    storyEdited ||
    scheduleEdited
  )
})
watch(unsavedChanges, (value) => emit('dirtyChange', value), {
  immediate: true,
})
function chooseMode(kind: 'plan' | 'story') {
  if (kind === mode.value) return
  if (props.navigateKind) props.navigateKind(kind, cityCode.value)
  else mode.value = kind
}
async function loadPracticeBrief() {
  if (!practiceEnabled || busy.value) return
  if (!inputPractice.value) practiceBackup.value = captureBrief()
  const example = createPracticeBrief()
  goal.value = example.goal
  cityCode.value = example.cityAdcode
  startDate.value = localDate
  days.value = 2
  budget.value = ''
  dailyStart.value = '09:00'
  dailyEnd.value = '18:00'
  transport.value = 'walking'
  pace.value = 'relaxed'
  interests.value = ''
  mustVisit.value = ''
  candidates.value = example.candidates.map((c) => ({ ...c }))
  allowExternal.value = false
  allowModel.value = false
  allowMemory.value = false
  run.value = null
  pendingRequest.value = null
  error.value = ''
  errorCode.value = ''
  selectedStopId.value = null
  editingBrief.value = false
  clearConfirmation()
  await nextTick()
  if (candidateDetails.value) candidateDetails.value.open = false
  scrollTo(practiceNotice.value)
}
async function restorePreviousBrief() {
  if (busy.value || !practiceBackup.value) return
  const previous = practiceBackup.value
  goal.value = previous.goal
  cityCode.value = previous.cityCode
  startDate.value = previous.startDate
  days.value = previous.days
  budget.value = previous.budget
  dailyStart.value = previous.dailyStart
  dailyEnd.value = previous.dailyEnd
  transport.value = previous.transport
  pace.value = previous.pace
  interests.value = previous.interests
  mustVisit.value = previous.mustVisit
  candidates.value = previous.candidates.map((c) => ({ ...c }))
  allowExternal.value = previous.allowExternal
  allowModel.value = previous.allowModel
  practiceBackup.value = null
  run.value = null
  pendingRequest.value = null
  error.value = ''
  errorCode.value = ''
  selectedStopId.value = null
  editingBrief.value = false
  clearConfirmation()
  await nextTick()
  scrollTo(briefAnchor.value)
}
const splitQuery = window.matchMedia?.('(min-width: 1280px)')
const isWideScreen = ref(splitQuery?.matches ?? false)
const selectedStopId = ref<string | null>(null)
const mapPanel = ref<HTMLElement | null>(null)
function syncSplitScreen(event: MediaQueryListEvent) {
  isWideScreen.value = event.matches
}
const interestOptions = [
  '自然风光',
  '历史街区',
  '博物馆',
  '美食',
  '海边',
  '公园',
]
const hasPlan = computed(
  () =>
    run.value?.kind === 'plan' &&
    !['needs_input', 'failed', 'running'].includes(run.value.status) &&
    !!run.value.result.days?.some((day) => day.stops.length > 0),
)
const inlineMap = computed(
  () =>
    hasPlan.value &&
    isWideScreen.value &&
    resultTab.value === 'schedule' &&
    !editingBrief.value,
)
const mapVisible = computed(
  () => hasPlan.value && (inlineMap.value || resultTab.value === 'map'),
)
const contextCityCode = computed(() =>
  hasPlan.value
    ? String(run.value?.request.city_adcode ?? cityCode.value)
    : cityCode.value,
)
const contextCity = computed(
  () =>
    cities.value.find((c) => c.code === contextCityCode.value)?.name ??
    '这段旅程',
)
const contextPhoto = computed(() =>
  destinations.find((d) => d.adcode === contextCityCode.value),
)
const summaryGoal = computed(() =>
  hasPlan.value ? String(run.value?.request.goal ?? goal.value) : goal.value,
)
const summaryDate = computed(() =>
  hasPlan.value ? String(run.value?.request.start_date ?? '') : startDate.value,
)
const summaryDays = computed(() =>
  hasPlan.value
    ? Number(run.value?.request.days ?? run.value?.result.days?.length ?? 0)
    : days.value,
)
const placeCount = computed(
  () =>
    run.value?.result.days?.reduce(
      (total, day) => total + day.stops.length,
      0,
    ) ?? 0,
)
const taskPhase = computed(() => {
  if (busy.value && pendingRequest.value) return 'working'
  if (run.value?.status === 'confirmed') return 'saved'
  if (run.value?.status === 'running') return 'working'
  if (run.value?.status === 'needs_input' || run.value?.status === 'failed')
    return 'blocked'
  if (run.value) return 'review'
  return 'brief'
})
async function onResultTabKeydown(event: KeyboardEvent) {
  if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return
  const views = ['schedule', 'map', 'execution'] as const
  const index = views.indexOf(resultTab.value)
  const next =
    event.key === 'Home'
      ? 0
      : event.key === 'End'
        ? 2
        : (index + (event.key === 'ArrowRight' ? 1 : -1) + views.length) %
          views.length
  const tabs = event.currentTarget as HTMLElement
  event.preventDefault()
  resultTab.value = views[next]!
  await nextTick()
  tabs.querySelectorAll<HTMLButtonElement>('[role=tab]')[next]?.focus()
}
function scrollTo(element: HTMLElement | null) {
  element?.scrollIntoView?.({
    block: 'start',
    behavior: window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
      ? 'instant'
      : 'smooth',
  })
}
async function openBrief() {
  editingBrief.value = true
  await nextTick()
  scrollTo(briefAnchor.value)
}
async function openCandidates() {
  if (hasPlan.value) editingBrief.value = true
  await nextTick()
  if (candidateDetails.value) candidateDetails.value.open = true
  await nextTick()
  scrollTo(candidateDetails.value)
}
function toggleInterest(value: string) {
  const selected = split(interests.value)
  interests.value = (
    selected.includes(value)
      ? selected.filter((i) => i !== value)
      : selected.length < 3
        ? [...selected, value]
        : selected
  ).join('，')
}
function historyStatus(value: AgentRun['status']) {
  return {
    running: '执行中',
    needs_input: '待补充',
    awaiting_confirmation: '草案',
    confirmed: '已保存',
    failed: '未完成',
  }[value]
}
function checkLabel(value: string) {
  return (
    (
      {
        pass: '通过',
        passed: '通过',
        warning: '待核实',
        unknown: '未知',
        fail: '未通过',
        failed: '未通过',
      } as Record<string, string>
    )[value] ?? value
  )
}
function restoreBrief(value: AgentRun) {
  const q = value.request
  if (typeof q.goal === 'string') goal.value = q.goal
  if (typeof q.city_adcode === 'string') cityCode.value = q.city_adcode
  if (typeof q.start_date === 'string') startDate.value = q.start_date
  if (typeof q.days === 'number') days.value = q.days
  budget.value = typeof q.budget_yuan === 'number' ? q.budget_yuan : ''
  if (typeof q.daily_start === 'string') dailyStart.value = q.daily_start
  if (typeof q.daily_end === 'string') dailyEnd.value = q.daily_end
  if (
    q.transport === 'walking' ||
    q.transport === 'transit' ||
    q.transport === 'driving'
  )
    transport.value = q.transport
  if (q.pace === 'relaxed' || q.pace === 'balanced') pace.value = q.pace
  interests.value = Array.isArray(q.interests)
    ? q.interests.filter((i) => typeof i === 'string').join('，')
    : ''
  mustVisit.value = Array.isArray(q.must_visit)
    ? q.must_visit.filter((i) => typeof i === 'string').join('，')
    : ''
  candidates.value = Array.isArray(q.candidates)
    ? q.candidates.map((c) => ({ ...c }))
    : []
  allowExternal.value = false
  allowModel.value = false
  allowMemory.value = false
}
const canSave = computed(
  () =>
    run.value?.status === 'awaiting_confirmation' &&
    !['conflict', 'information_missing'].includes(
      run.value.result.verification_status,
    ),
)
const currentDay = computed(
  () =>
    run.value?.result.days?.find((d) => d.day === activeDay.value) ??
    run.value?.result.days?.[0],
)
const selectedStop = computed(() =>
  currentDay.value?.stops.find(
    (stop) => stop.candidate_id === selectedStopId.value,
  ),
)
watch(activeDay, () => {
  if (!selectedStop.value) selectedStopId.value = null
})
async function locateStop(id: string) {
  if (!currentDay.value?.stops.some((stop) => stop.candidate_id === id)) return
  selectedStopId.value = id
  if (!inlineMap.value) {
    resultTab.value = 'map'
    await nextTick()
    scrollTo(mapPanel.value)
  }
}
function selectMapStop(point: { day: number; candidateId: string }) {
  const day = run.value?.result.days?.find((day) => day.day === point.day)
  if (!day?.stops.some((stop) => stop.candidate_id === point.candidateId))
    return
  activeDay.value = point.day
  selectedStopId.value = point.candidateId
}
async function revealSelectedStop() {
  if (!selectedStop.value) return
  resultTab.value = 'schedule'
  await nextTick()
  const item = Array.from(
    resultAnchor.value?.querySelectorAll<HTMLElement>('[data-stop-id]') ?? [],
  ).find((el) => el.dataset.stopId === selectedStopId.value)
  item?.scrollIntoView?.({
    block: 'nearest',
    behavior: window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
      ? 'instant'
      : 'smooth',
  })
}
const statusText = computed(() => {
  if (run.value?.status === 'confirmed') return '已保存到私人档案'
  if (run.value?.status === 'running') return '任务正在执行 · 可稍后刷新'
  if (run.value?.status === 'failed') return '本次整理未完成 · 查看执行记录'
  return {
    validated: '已通过当前约束检查',
    conditional: '条件草案 · 仍需核实',
    conflict: '约束冲突 · 需要调整',
    information_missing: '信息不足 · 请补充',
  }[run.value?.result.verification_status ?? 'information_missing']
})
const sourceLabel = (source: string) =>
  source === 'amap' ? '高德查询' : '你提供的地点'
function clearConfirmation() {
  confirmation.value = null
  acknowledged.value = false
}
function useRun(value: AgentRun) {
  if (!alive) return
  value = {
    ...value,
    events: value.events ?? [],
    result: {
      ...value.result,
      intent_source: value.result?.intent_source ?? 'local_rules',
      verification_status:
        value.result?.verification_status ?? 'information_missing',
      summary:
        value.result?.summary ?? '任务尚无可用结果，请查看执行记录或刷新状态。',
      warnings: value.result?.warnings ?? [],
      unknowns: value.result?.unknowns ?? [],
    },
  }
  run.value = value
  editTitle.value = value.title
  editStory.value = value.result.story_body ?? ''
  revisedEnd.value = String(value.request.daily_end ?? '18:00')
  briefBaseline.value = briefFingerprint()
  activeDay.value = value.result.days?.[0]?.day ?? 1
  editingBrief.value = false
  resultTab.value = 'schedule'
  selectedStopId.value = null
  clearConfirmation()
  void nextTick(() => scrollTo(resultAnchor.value))
}
function reportError(e: unknown) {
  error.value = e instanceof Error ? e.message : '暂时无法完成，请稍后重试。'
  errorCode.value = e instanceof ApiClientError ? e.code : 'CLIENT_ERROR'
}
async function loadHistory() {
  try {
    history.value = (await listAgentRuns()).items
  } catch (e) {
    reportError(e)
  }
}
onMounted(async () => {
  splitQuery?.addEventListener?.('change', syncSplitScreen)
  if (props.initialRunId) busy.value = true
  const results = await Promise.allSettled([
    getAgentCapabilities(),
    listAgentRuns(),
  ])
  if (!alive) return
  if (results[0].status === 'fulfilled') capabilities.value = results[0].value
  else capabilitiesUnavailable.value = true
  if (results[1].status === 'fulfilled') history.value = results[1].value.items
  else reportError(results[1].reason)
  if (props.initialRunId) await restore(props.initialRunId)
})
onBeforeUnmount(() => {
  alive = false
  splitQuery?.removeEventListener?.('change', syncSplitScreen)
  emit('dirtyChange', false)
})
watch(
  () => props.initialKind,
  (v) => {
    if (v) {
      mode.value = v
      run.value = null
      clearConfirmation()
    }
  },
)
watch(
  () => props.initialCity,
  (v) => {
    if (v) cityCode.value = v
  },
)
watch(
  () => props.initialIntent,
  (value) => {
    if (!value) return
    goal.value = value.goal
    if (value.cityAdcode) cityCode.value = value.cityAdcode
    interests.value = value.interests?.join('，') ?? ''
    pace.value = value.pace ?? 'relaxed'
    days.value = value.days ?? 2
  },
)
watch(mode, () => {
  run.value = null
  error.value = ''
  allowModel.value = false
  allowExternal.value = false
  clearConfirmation()
})
watch(allowExternal, (value) => {
  if (!value) allowModel.value = false
})
function split(value: string) {
  return value
    .split(/[，,、]/)
    .map((s) => s.trim())
    .filter(Boolean)
    .slice(0, 3)
}
function addCandidate() {
  if (candidates.value.length < 12)
    candidates.value.push({
      name: '',
      longitude: '',
      latitude: '',
      stay_minutes: 60,
      cost_yuan: null,
      opening_start: null,
      opening_end: null,
      must_visit: false,
    })
}
function buildRequest(): RunCreate {
  return {
    client_request_id: crypto.randomUUID(),
    kind: mode.value,
    goal: goal.value.trim(),
    city_adcode: cityCode.value,
    city_name:
      cities.value.find((c) => c.code === cityCode.value)?.name ??
      cityCode.value,
    start_date: startDate.value,
    days: Number(days.value),
    daily_start: dailyStart.value,
    daily_end: dailyEnd.value,
    budget_yuan: budget.value === '' ? null : Number(budget.value),
    transport: transport.value,
    pace: pace.value,
    interests: split(interests.value),
    must_visit: split(mustVisit.value),
    candidates:
      mode.value === 'plan'
        ? candidates.value.map((c) => ({
            ...c,
            longitude: Number(c.longitude),
            latitude: Number(c.latitude),
            stay_minutes: Number(c.stay_minutes),
          }))
        : [],
    allow_external:
      mode.value === 'plan' && allowExternal.value && !inputPractice.value,
    allow_model:
      mode.value === 'plan' && allowModel.value && !inputPractice.value,
    allow_memory_access: mode.value === 'story' && allowMemory.value,
    memory_ids: [],
  }
}
async function submit(retry = false) {
  if (busy.value) return
  if (mode.value === 'story' && !allowMemory.value) {
    error.value = '请先授权读取选定城市与日期内的旅行记录。'
    return
  }
  if (!goal.value.trim()) {
    error.value = '先告诉小曦，这次想怎样旅行或整理回忆。'
    return
  }
  const payload =
    retry && pendingRequest.value ? pendingRequest.value : buildRequest()
  pendingRequest.value = payload
  busy.value = true
  error.value = ''
  errorCode.value = ''
  clearConfirmation()
  try {
    await nextTick()
    scrollTo(resultAnchor.value)
    let created = await createAgentRun(payload)
    if (
      payload.kind === 'plan' &&
      isPracticeRequest({
        goal: payload.goal,
        candidates: payload.candidates,
      }) &&
      ['awaiting_confirmation', 'needs_input'].includes(created.status) &&
      !created.title.startsWith(PRACTICE_MARKER)
    ) {
      created = await editAgentDraft(created.id, {
        expected_revision: created.revision,
        title: `${PRACTICE_MARKER} ${payload.city_name} · 虚拟地点规划`,
      })
    }
    useRun(created)
    pendingRequest.value = null
    await loadHistory()
  } catch (e) {
    reportError(e)
  } finally {
    busy.value = false
  }
}
async function restore(id: string) {
  if (
    unsavedChanges.value &&
    props.confirmLeave &&
    !(await props.confirmLeave())
  )
    return
  busy.value = true
  error.value = ''
  try {
    const value = await getAgentRun(id)
    if (!alive) return
    mode.value = value.kind
    await Promise.resolve()
    useRun(value)
    restoreBrief(value)
    briefBaseline.value = briefFingerprint()
    showHistory.value = false
  } catch (e) {
    reportError(e)
  } finally {
    busy.value = false
  }
}
async function editDraft(excluded?: string) {
  if (!run.value || busy.value) return
  busy.value = true
  error.value = ''
  clearConfirmation()
  try {
    const payload =
      run.value.kind === 'story'
        ? {
            expected_revision: run.value.revision,
            title: editTitle.value,
            story_body: editStory.value,
          }
        : {
            expected_revision: run.value.revision,
            daily_end: revisedEnd.value,
            ...(excluded
              ? {
                  excluded_candidate_ids: Array.from(
                    new Set([
                      ...(Array.isArray(
                        run.value.request.excluded_candidate_ids,
                      )
                        ? run.value.request.excluded_candidate_ids.filter(
                            (id): id is string => typeof id === 'string',
                          )
                        : []),
                      excluded,
                    ]),
                  ),
                }
              : {}),
          }
    useRun(await editAgentDraft(run.value.id, payload))
    await loadHistory()
  } catch (e) {
    reportError(e)
  } finally {
    busy.value = false
  }
}
async function previewSave() {
  if (!run.value) return
  busy.value = true
  error.value = ''
  try {
    confirmation.value = await previewAgentConfirmation(run.value)
    acknowledged.value = false
    await nextTick()
    scrollTo(confirmationAnchor.value)
    confirmationAnchor.value?.focus({ preventScroll: true })
  } catch (e) {
    reportError(e)
  } finally {
    busy.value = false
  }
}
async function save() {
  if (!run.value || !confirmation.value) return
  busy.value = true
  error.value = ''
  try {
    useRun(
      await confirmAgentRun(run.value, confirmation.value, acknowledged.value),
    )
    await loadHistory()
  } catch (e) {
    reportError(e)
  } finally {
    busy.value = false
  }
}
function eventLabel(status: string) {
  return (
    (
      {
        success: '完成',
        succeeded: '完成',
        failed: '未完成',
        error: '失败',
        started: '开始',
        retrying: '重试',
        skipped: '跳过',
        warning: '需留意',
        running: '执行中',
      } as Record<string, string>
    )[status] ?? status
  )
}
</script>

<template>
  <main
    class="agent-workspace"
    :class="{ 'showing-plan': hasPlan, 'story-workspace': mode === 'story', 'composing-brief': !run }"
    :aria-label="mode === 'story' ? '小曦旅行故事工作台' : '小曦旅行规划工作台'"
  >
    <div class="workspace-scroll">
      <div class="workspace-container">
        <header class="workspace-header">
          <div class="workspace-heading">
            <button
              class="icon-button back-button"
              type="button"
              :aria-label="mode === 'story' ? '返回城市记忆' : '返回发现首页'"
              @click="emit('back')"
            >
              <ArrowLeft :size="19" />
            </button>
            <div>

              <h1>
                {{
                  mode === 'plan'
                    ? '把心动，安排成旅程。'
                    : '把回忆，写成自己的故事。'
                }}
              </h1>
              <span
                v-if="unsavedChanges"
                class="workspace-edit-status"
                role="status"
                >有未提交的编辑</span
              >
            </div>
          </div>
          <div class="workspace-header-actions">
            <UiButton variant="secondary"
              class="history-toggle secondary-action"
              type="button"
              aria-label="最近任务"
              :aria-expanded="showHistory"
              :disabled="busy"
              @click="showHistory = !showHistory"
            >
              <History :size="16" /><span>最近任务</span
              ><b>{{ history.length }}</b>
            </UiButton>
          </div>
        </header>
        <section
          v-if="mode === 'story'"
          class="story-workflow-bar"
          aria-label="故事整理流程"
        >
          <span><b>01</b>选择城市与日期</span><ChevronRight :size="15" /><span
            ><b>02</b>授权读取与编辑</span
          ><ChevronRight :size="15" /><span><b>03</b>核对后保存</span>
        </section>
        <div v-if="mode === 'plan'" class="workflow-bar">
          <AgentWorkflowSteps :phase="taskPhase" />
        </div>
        <section
          v-if="inputPractice || resultPractice"
          ref="practiceNotice"
          class="practice-notice"
          aria-label="离线演练说明"
        >
          <span class="practice-label"
            ><Compass :size="15" />离线演练 · 虚拟地点</span
          >
          <p>使用四个虚拟地点运行本地规划；不调用在线模型或地图查询。</p>
          <small>主动开始后才创建演练任务，核对并确认后才保存，不点亮城市。</small>
          <UiButton variant="primary"
            v-if="inputPractice && (!run || editingBrief) && !pendingRequest"
            class="primary-action"
            type="submit"
            form="travel-brief"
            :disabled="busy"
          >
            开始演练<ArrowRight :size="15" /></UiButton><button
            v-if="practiceBackup"
            class="text-button"
            type="button"
            :disabled="busy"
            @click="restorePreviousBrief"
          >
            <ArrowLeft :size="14" />恢复我之前的输入
          </button>
        </section>
        <section v-if="showHistory" class="history-strip" aria-label="最近任务">
          <div>
            <div>

              <h2>接着上次的旅程</h2>
            </div>
            <button
              class="text-button"
              type="button"
              :disabled="busy"
              @click="loadHistory"
            >
              <RefreshCw :size="14" />刷新
            </button>
          </div>
          <p v-if="!history.length">还没有任务。第一段旅程，从下面开始。</p>
          <button
            v-for="item in history"
            :key="item.id"
            type="button"
            :disabled="busy"
            @click="restore(item.id)"
          >
            <span class="history-kind"
              ><Compass v-if="item.kind === 'plan'" :size="17" /><BookOpen
                v-else
                :size="17" /></span
            ><span>{{ item.title }}</span
            ><small
              >{{ historyStatus(item.status) }} · 第{{ item.revision }}版</small
            ><ChevronRight :size="16" />
          </button>
        </section>
        <div
          class="workspace-grid"
          :class="{
            'has-plan': hasPlan,
            'has-run': !!run,
            'editing-brief': editingBrief,
            'has-inline-map': inlineMap,
          }"
        >
          <aside class="brief-column">
            <section
              v-if="hasPlan && !editingBrief"
              class="journey-brief-card"
              aria-label="本次旅行条件"
            >
              <div
                class="journey-cover"
                :class="{ 'without-photo': !contextPhoto }"
              >
                <img
                  v-if="contextPhoto"
                  :src="contextPhoto.image"
                  :alt="contextPhoto.imageAlt"
                /><MapPin v-else :size="42" /><span
                  >这一站，{{ contextCity.replace(/市$/, '') }}</span
                ><small v-if="contextPhoto">目的地灵感图</small>
              </div>
              <div class="journey-brief-body">

                <h2>{{ summaryDays }} 天，按你的节奏。</h2>
                <p class="journey-goal">{{ summaryGoal }}</p>
                <dl>
                  <div>
                    <dt><CalendarDays :size="14" />出发</dt>
                    <dd>{{ summaryDate || '日期待补充' }}</dd>
                  </div>
                  <div>
                    <dt><MapPin :size="14" />安排</dt>
                    <dd>{{ placeCount }} 个地点</dd>
                  </div>
                  <div>
                    <dt><Clock3 :size="14" />每天</dt>
                    <dd>
                      {{ run?.request.daily_start ?? '待补充' }} —
                      {{ run?.request.daily_end ?? '待补充' }}
                    </dd>
                  </div>
                </dl>
                <UiButton variant="secondary"
                  class="secondary-action"
                  type="button"
                  :disabled="busy"
                  @click="openBrief"
                >
                  <SlidersHorizontal :size="15" />调整旅行条件
                </UiButton>
                <p class="summary-hint">调整条件后可以生成一份新草案。</p>
              </div>
            </section>
            <div
              v-show="!hasPlan || editingBrief"
              ref="briefAnchor"
              class="brief-editor"
            >
              <button
                v-if="hasPlan && editingBrief"
                class="text-button editor-back"
                type="button"
                :disabled="busy"
                @click="editingBrief = false"
              >
                <ArrowLeft :size="14" />返回当前草案
              </button>
              <div class="mode-switch" role="group" aria-label="任务类型">
                <button
                  :class="{ active: mode === 'plan' }"
                  :aria-pressed="mode === 'plan'"
                  type="button"
                  :disabled="busy"
                  @click="chooseMode('plan')"
                >
                  <Compass :size="16" />规划旅程</button
                ><button
                  :class="{ active: mode === 'story' }"
                  :aria-pressed="mode === 'story'"
                  type="button"
                  :disabled="busy"
                  @click="chooseMode('story')"
                >
                  <BookOpen :size="16" />整理故事
                </button>
              </div>
              <form
                id="travel-brief"
                class="travel-brief"
                :aria-busy="busy"
                @submit.prevent="submit(false)"
              >
                <fieldset class="brief-fields" :disabled="busy">
                  <section
                    class="brief-card wish-card"
                    data-chapter="01"
                    aria-labelledby="wish-title"
                  >
                    <header class="brief-card-heading">

                      <div>
                        <h2 id="wish-title">
                          {{
                            mode === 'plan'
                              ? '旅行想法'
                              : '回忆的线索'
                          }}
                        </h2>
                        <p v-if="mode === 'story'">保留你在旅途中亲自写下的细节。</p>
                      </div>
                      <Sparkles :size="19" />
                    </header>
                    <label class="field goal-field"
                      ><span>{{
                        mode === 'plan'
                          ? '这次想怎样旅行？'
                          : '想留下一段怎样的回忆？'
                      }}</span
                      ><textarea
                        v-model="goal"
                        required
                        minlength="2"
                        maxlength="1500"
                        rows="3"
                        :aria-label="
                          mode === 'plan'
                            ? '这次想怎样旅行？'
                            : '想留下一段怎样的回忆？'
                        "
                        :placeholder="
                          mode === 'plan'
                            ? '想去厦门走走老街、看看海，下午留点时间发呆，行程不要太赶…'
                            : '把这几天的旅行日记整理成一段故事，保留当时写下的细节…'
                        "
                      ></textarea>
                    </label>
                  </section>
                  <section class="brief-card" data-chapter="02" aria-labelledby="basic-title">
                    <header class="brief-card-heading">
                      <CalendarDays v-if="mode === 'plan'" :size="20" aria-hidden="true" />

                      <div>
                        <h2 id="basic-title">
                          {{
                            mode === 'plan'
                              ? '基本安排'
                              : '选好这一段回忆'
                          }}
                        </h2>
                        <p v-if="mode === 'story'">仅整理所选城市、日期范围内的记录。</p>
                      </div>
                    </header>
                    <div class="basic-fields">
                      <label class="field"
                        ><span><MapPin :size="14" />目的地</span
                        ><select v-model="cityCode" aria-label="目的地">
                          <option
                            v-for="city in cities"
                            :key="city.code"
                            :value="city.code"
                          >
                            {{ city.name }}
                          </option>
                          <option
                            v-if="!cities.some((c) => c.code === cityCode)"
                            :value="cityCode"
                          >
                            城市 {{ cityCode }}
                          </option>
                        </select></label
                      ><label class="field"
                        ><span
                          ><CalendarDays :size="14" />{{
                            mode === 'plan' ? '出发日期' : '回忆开始日期'
                          }}</span
                        ><input
                          v-model="startDate"
                          type="date"
                          required
                          :aria-label="
                            mode === 'plan' ? '出发日期' : '回忆开始日期'
                          " /></label
                      ><label class="field"
                        ><span
                          ><Clock3 :size="14" />{{
                            mode === 'plan' ? '旅行天数' : '回忆时间范围'
                          }}</span
                        ><select
                          v-model.number="days"
                          :aria-label="
                            mode === 'plan' ? '旅行天数' : '回忆时间范围'
                          "
                        >
                          <option v-for="n in 4" :key="n" :value="n">
                            {{ n }} 天
                          </option>
                        </select></label
                      ><label v-if="mode === 'plan'" class="field"
                        ><span><Wallet :size="14" />景点预算 / 元</span
                        ><input
                          v-model="budget"
                          type="number"
                          min="0"
                          max="1000000"
                          placeholder="暂不限定"
                          aria-label="景点预算 / 元"
                      /></label>
                    </div>
                    <p v-if="mode === 'plan'" class="field-note">
                      预算只核对已知景点费用，住宿、餐饮与交通另行安排。
                    </p>
                  </section>
                  <section v-if="needsPlaceSource" class="place-source-notice" aria-label="生成行程前的地点条件">
                    <UiStatus tone="warning">{{ capabilities?.amap_configured ? '请补充地点或授权在线查询' : '地点查询尚未连接' }}</UiStatus>
                    <p>补充想去的地点，或连接地点查询后继续安排行程。</p>
                    <div class="source-notice-actions"><UiButton variant="secondary" :disabled="busy" @click="openCandidates">补充自己的地点</UiButton><UiButton v-if="practiceEnabled" variant="tertiary" :disabled="busy" @click="loadPracticeBrief">填入离线演练条件<ArrowRight :size="16" /></UiButton></div>
                    <details><summary>地点来源与限制</summary><p>{{ placeSourceExplanation }} 没有地点来源时会返回“信息不足”。</p></details>
                  </section>
                  <template v-if="mode === 'plan'">
                    <section
                      class="brief-card preferences-card"
                      data-chapter="03"
                      aria-labelledby="preferences-title"
                    >
                      <header class="brief-card-heading">

                        <div>
                          <h2 id="preferences-title">留一点，属于你的偏好</h2>
                          <p>走快一点、慢一点，都由你决定。</p>
                        </div>
                      </header>
                      <div class="field-pair">
                        <label class="field"
                          ><span>出行方式</span
                          ><select v-model="transport" aria-label="出行方式">
                            <option value="transit">公交 / 地铁</option>
                            <option value="walking">步行</option>
                            <option value="driving">驾车</option>
                          </select></label
                        ><label class="field"
                          ><span>旅行节奏</span
                          ><select v-model="pace" aria-label="旅行节奏">
                            <option value="relaxed">慢一点，留些空白</option>
                            <option value="balanced">均衡安排</option>
                          </select></label
                        >
                      </div>
                      <label class="field interest-field"
                        ><span>想逛什么 <small>最多 3 项，逗号分隔</small></span
                        ><input
                          v-model="interests"
                          maxlength="240"
                          placeholder="博物馆，公园，历史街区"
                          aria-label="想逛什么"
                      /></label>
                      <div
                        class="interest-options"
                        role="group"
                        aria-label="旅行兴趣"
                      >
                        <button
                          v-for="item in interestOptions"
                          :key="item"
                          type="button"
                          :aria-pressed="split(interests).includes(item)"
                          :class="{ selected: split(interests).includes(item) }"
                          :disabled="
                            split(interests).length >= 3 &&
                            !split(interests).includes(item)
                          "
                          @click="toggleInterest(item)"
                        >
                          <Check
                            v-if="split(interests).includes(item)"
                            :size="12"
                          />{{ item }}
                        </button>
                      </div>
                      <details class="advanced-brief">
                        <summary>
                          <SlidersHorizontal :size="14" /><span>更细的安排</span
                          ><small>{{ dailyStart }} — {{ dailyEnd }}</small
                          ><ChevronDown :size="15" />
                        </summary>
                        <div class="advanced-fields">
                          <div class="field-pair">
                            <label class="field"
                              ><span>每天开始</span
                              ><input
                                v-model="dailyStart"
                                type="time"
                                required
                                aria-label="每天开始" /></label
                            ><label class="field"
                              ><span>每天结束</span
                              ><input
                                v-model="dailyEnd"
                                type="time"
                                required
                                aria-label="每天结束"
                            /></label>
                          </div>
                          <label class="field"
                            ><span>一定想去 <small>可选，最多 3 项</small></span
                            ><input
                              v-model="mustVisit"
                              maxlength="240"
                              placeholder="填写具体地点名称"
                              aria-label="一定想去"
                          /></label>
                        </div>
                      </details>
                    </section>
                    <section class="brief-card places-card">
                      <details
                        ref="candidateDetails"
                        class="candidate-input"
                        :open="candidates.length > 0"
                      >
                        <summary>
                          <span class="candidate-symbol"
                            ><MapPin :size="18" /></span
                          ><span
                            ><strong>我已有想去的地点</strong
                            ><small>{{
                              candidates.length
                                ? `已补充 ${candidates.length} 个地点`
                                : '有确定的地点？一起带进行程里。'
                            }}</small></span
                          ><ChevronDown :size="16" />
                        </summary>
                        <div class="candidate-content">
                          <p>
                            填写你掌握的地点与 GCJ-02
                            坐标。系统会标注“你提供”，未经地图核验。
                          </p>
                          <fieldset
                            v-for="(candidate, index) in candidates"
                            :key="index"
                          >
                            <legend>地点 {{ index + 1 }}</legend>
                            <button
                              class="remove-candidate icon-button"
                              type="button"
                              :aria-label="`移除地点${index + 1}`"
                              @click="candidates.splice(index, 1)"
                            >
                              <Trash2 :size="15" /></button
                            ><label class="field"
                              ><span>地点名称</span
                              ><input
                                v-model="candidate.name"
                                required
                                maxlength="100"
                                placeholder="填写真实地点名称"
                                aria-label="地点名称"
                            /></label>
                            <div class="field-pair">
                              <label class="field"
                                ><span>GCJ-02经度</span
                                ><input
                                  v-model.number="candidate.longitude"
                                  type="number"
                                  required
                                  step="any"
                                  min="73"
                                  max="136"
                                  aria-label="GCJ-02经度" /></label
                              ><label class="field"
                                ><span>GCJ-02纬度</span
                                ><input
                                  v-model.number="candidate.latitude"
                                  type="number"
                                  required
                                  step="any"
                                  min="3"
                                  max="54"
                                  aria-label="GCJ-02纬度"
                              /></label>
                            </div>
                            <div class="field-pair">
                              <label class="field"
                                ><span>停留 / 分钟</span
                                ><input
                                  v-model.number="candidate.stay_minutes"
                                  type="number"
                                  min="15"
                                  max="480"
                                  required
                                  aria-label="停留 / 分钟" /></label
                              ><label class="field"
                                ><span>已知票价 / 元</span
                                ><input
                                  v-model="candidate.cost_yuan"
                                  type="number"
                                  min="0"
                                  step="0.01"
                                  placeholder="未知"
                                  aria-label="已知票价 / 元"
                                  @change="
                                    candidate.cost_yuan =
                                      candidate.cost_yuan === null ||
                                      String(candidate.cost_yuan) === ''
                                        ? null
                                        : Number(candidate.cost_yuan)
                                  "
                              /></label>
                            </div>
                            <div class="field-pair">
                              <label class="field"
                                ><span>开放时间（可选）</span
                                ><input
                                  v-model="candidate.opening_start"
                                  type="time"
                                  aria-label="开放时间（可选）"
                                  @change="
                                    candidate.opening_start ||= null
                                  " /></label
                              ><label class="field"
                                ><span>闭馆时间（可选）</span
                                ><input
                                  v-model="candidate.opening_end"
                                  type="time"
                                  aria-label="闭馆时间（可选）"
                                  @change="candidate.opening_end ||= null"
                              /></label>
                            </div>
                            <label class="consent compact"
                              ><input
                                v-model="candidate.must_visit"
                                type="checkbox"
                              /><span>这是必去地点</span></label
                            >
                          </fieldset>
                          <UiButton variant="secondary"
                            class="secondary-action add-place"
                            type="button"
                            :disabled="candidates.length >= 12"
                            @click="addCandidate"
                          >
                            <Plus :size="15" />添加地点
                          </UiButton>
                        </div>
                      </details>
                    </section>
                    <section
                      class="brief-card permission-card"
                      aria-label="本次工具授权"
                    >
                      <div class="permission-heading">
                        <ShieldCheck :size="17" />
                        <h2>工具使用，由你决定</h2>
                      </div>
                      <label class="consent"
                        ><input
                          v-model="allowExternal"
                          type="checkbox"
                          :disabled="inputPractice"
                        /><span
                          >允许查询高德地点与路线<small
                            >会向高德发送目的地、地点和出行方式，可能消耗服务额度。{{
                              mapAvailabilityNote
                            }}</small
                          ></span
                        ></label
                      ><label
                        v-if="capabilities?.model_configured"
                        class="consent"
                        ><input
                          v-model="allowModel"
                          type="checkbox"
                          :disabled="!allowExternal || inputPractice"
                        /><span
                          >允许模型辅助理解本次需求<small
                            >只发送当前旅行需求，可能产生模型费用；不发送私人记忆。</small
                          ></span
                        ></label
                      >
                    </section>
                  </template>
                  <label v-else class="consent story-consent"
                    ><input
                      v-model="allowMemory"
                      type="checkbox"
                      required
                    /><span
                      >允许读取所选城市与日期的私人记录<small
                        >仅在本服务内整理文字、日期和可用影像数量；不读取照片内容、不向外部传输。</small
                      ></span
                    ></label
                  >
                  <div class="brief-submit">
                    <UiButton variant="primary"
                      class="primary-action"
                      type="submit"
                      :disabled="busy"
                    >
                      <LoaderCircle
                        v-if="busy"
                        class="spin"
                        :size="18"
                      /><Sparkles v-else :size="18" />{{
                        busy
                          ? '小曦正在整理…'
                          : mode === 'plan'
                            ? inputPractice
                              ? '生成离线演练草案'
                              : '一起安排这段旅程'
                            : '整理我的旅行故事'
                      }}<ArrowRight v-if="!busy" :size="17" />
                    </UiButton>
                    <p class="brief-footnote">
                      <ShieldCheck
                        :size="12"
                      />先生成草案，确认后才存入私人档案。
                    </p>
                  </div>
                </fieldset>
              </form>
            </div>
            <button
              v-if="mode === 'plan'"
              class="route-tools-entry text-button"
              type="button"
              :disabled="busy"
              @click="emit('routeTools')"
            >
              <Route :size="14" />城市接驳工具<ArrowUpRight :size="13" />
            </button>
          </aside>
          <section
            ref="resultAnchor"
            class="result-column"
            aria-live="polite"
            aria-label="小曦执行结果"
            :aria-busy="busy"
          >
            <div v-if="error" class="workspace-error" role="alert">
              <CircleAlert :size="20" />
              <div>
                <strong>{{ error }}</strong
                ><small v-if="errorCode">{{ errorCode }}</small
                ><button
                  v-if="errorCode.includes('AUTH') || errorCode === 'HTTP_401'"
                  class="text-button"
                  type="button"
                  @click="emit('connect')"
                >
                  连接私人档案</button
                ><button
                  v-else-if="pendingRequest"
                  class="text-button"
                  type="button"
                  :disabled="busy"
                  @click="submit(true)"
                >
                  重试同一任务
                </button>
              </div>
            </div>
            <div
              v-if="busy && !run"
              class="result-empty working-state"
              role="status"
            >
              <div class="working-symbol">
                <Sun :size="40" /><LoaderCircle class="spin" :size="76" />
              </div>

              <h2>正在把想法，<br />安排成一段旅程。</h2>
              <p>
                小曦正在核对输入、执行已授权工具并检查约束，完成后会显示草案与实际调用记录。
              </p>
              <span class="working-pill"
                ><span></span>正在等待本次任务结果</span
              >
            </div>
            <section
              v-else-if="!run && mode === 'story'"
              class="story-companion"
            >
              <div class="story-companion-copy">
                <h2>让一段旅程，<br />在记忆中重新展开。</h2>
                <p>
                  小曦只整理你授权的城市与日期中的已有记录。你可以查看原文、修改草稿，最后决定是否保存。
                </p>
              </div>
              <figure class="story-memory-frame">
                <img v-if="contextPhoto" :src="contextPhoto.image" :alt="contextPhoto.imageAlt" />
                <div v-else class="story-journal-cover" aria-hidden="true"></div>
                <figcaption><MapPin :size="17" /><span>{{ contextCity }}</span><small>{{ contextPhoto ? '目的地灵感图' : '所选城市' }}</small></figcaption>
              </figure>
              <div class="story-source-summary">
                <div class="story-selected-range"><CalendarDays :size="18" /><div><strong>所选整理范围</strong><span>{{ summaryDate }} · {{ summaryDays }} 天</span></div></div>
                <ul>
                  <li><BookOpen :size="17" />保留日期和原始文字来源</li>
                  <li>
                    <ShieldCheck :size="17" />在本服务内整理，不向外部传输
                  </li>
                  <li><Check :size="17" />没有记录时，会请你先补充</li>
                </ul>
              </div>
              <button type="button" class="journey-text-action" @click="emit('memories')">
                先翻阅城市记忆<ArrowRight :size="15" />
              </button>
            </section>
            <div v-else-if="!run" class="planning-companion">
              <div
                class="companion-photo"
                :class="{ 'without-photo': !contextPhoto }"
              >
                <img
                  v-if="contextPhoto"
                  :src="contextPhoto.image"
                  :alt="contextPhoto.imageAlt"
                />
                <div v-else class="companion-landscape" aria-hidden="true">
                  <Sun :size="48" /><span></span>
                </div>
                <div>

                  <h2>
                    {{ contextCity.replace(/市$/, '') }}，<br />值得慢慢走。
                  </h2>
                </div>
                <small v-if="contextPhoto">目的地灵感图</small>
              </div>
              <div class="companion-copy">
                <span class="companion-seal"><Sun :size="23" /></span>

                <h2>你负责心动，<br />我们一起安排。</h2>
                <p>
                  把想去的地方、喜欢的节奏告诉小曦。每天的安排与还要核实的细节，都会为你整理清楚。
                </p>
                <div class="brief-live-summary">
                  <span
                    ><CalendarDays :size="15" />{{ summaryDate }} ·
                    {{ summaryDays }} 天</span
                  ><span
                    ><Compass :size="15" />{{
                      pace === 'relaxed' ? '慢一点，留些空白' : '均衡安排'
                    }}</span
                  >
                </div>
                <p class="companion-bottom">
                  <ShieldCheck :size="13" />私人整理 · 确认后保存
                </p>
              </div>
            </div>
            <template v-else>
              <div v-if="busy" class="updating-banner" role="status">
                <LoaderCircle
                  class="spin"
                  :size="17"
                />小曦正在整理，完成后会更新此处。
              </div>
              <p v-if="hasPlan && editingBrief" class="editing-note">
                正在调整旅行条件。生成新草案后再核对保存，也可以返回当前草案。
              </p>
              <header class="result-heading">
                <div>

                  <h2>{{ run.title }}</h2>
                </div>
                <span class="revision-label">版本 {{ run.revision }}</span>
              </header>
              <div
                class="result-status"
                :class="[
                  run.result.verification_status,
                  { 'task-failed': run.status === 'failed' },
                ]"
              >
                <CircleCheck
                  v-if="
                    run.status === 'confirmed' ||
                    run.result.verification_status === 'validated'
                  "
                  :size="20"
                /><CircleAlert v-else :size="20" />
                <div>
                  <strong>{{ statusText }}</strong>
                  <p>{{ run.result.summary }}</p>
                </div>
                <span>{{
                  run.result.intent_source === 'deepseek'
                    ? '模型辅助理解'
                    : '本地规则整理'
                }}</span>
              </div>
              <UiButton variant="secondary"
                v-if="run.status === 'running'"
                class="secondary-action refresh-run"
                type="button"
                :disabled="busy"
                @click="restore(run.id)"
              >
                <RefreshCw :size="15" />刷新任务状态
              </UiButton>
              <template v-if="hasPlan">
                <div class="itinerary-facts">
                  <span><CalendarDays :size="15" />{{ summaryDate }} 出发</span
                  ><span><Clock3 :size="15" />{{ summaryDays }} 天行程</span
                  ><span><MapPin :size="15" />{{ placeCount }} 个地点</span
                  ><span
                    ><ShieldCheck :size="15" />{{
                      run.status === 'confirmed'
                        ? '已存入私人档案'
                        : '待你核对与确认'
                    }}</span
                  >
                </div>
                <div
                  class="result-tabs"
                  role="tablist"
                  aria-label="行程查看方式"
                  @keydown="onResultTabKeydown"
                >
                  <button
                    id="schedule-tab"
                    :tabindex="resultTab === 'schedule' ? 0 : -1"
                    type="button"
                    role="tab"
                    :aria-selected="resultTab === 'schedule'"
                    aria-controls="schedule-panel"
                    :class="{ active: resultTab === 'schedule' }"
                    @click="resultTab = 'schedule'"
                  >
                    <CalendarDays :size="16" />每日安排</button
                  ><button
                    id="map-tab"
                    :tabindex="resultTab === 'map' ? 0 : -1"
                    type="button"
                    role="tab"
                    :aria-selected="resultTab === 'map'"
                    aria-controls="map-panel"
                    :class="{ active: resultTab === 'map' }"
                    @click="resultTab = 'map'"
                  >
                    <Map :size="16" />地点地图</button
                  ><button
                    id="execution-tab"
                    :tabindex="resultTab === 'execution' ? 0 : -1"
                    type="button"
                    role="tab"
                    :aria-selected="resultTab === 'execution'"
                    aria-controls="execution-panel"
                    :class="{ active: resultTab === 'execution' }"
                    @click="resultTab = 'execution'"
                  >
                    <ListChecks :size="16" />执行记录<span>{{
                      run.events.length
                    }}</span>
                  </button>
                </div>
                <div class="plan-panels" :class="{ 'is-split': inlineMap }">
                  <section
                    id="schedule-panel"
                    v-show="resultTab === 'schedule'"
                    class="schedule-panel"
                    role="tabpanel"
                    aria-labelledby="schedule-tab"
                  >
                    <div class="day-tabs" role="group" aria-label="每日行程">
                      <button
                        v-for="day in run.result.days"
                        :key="day.day"
                        type="button"
                        :class="{ active: activeDay === day.day }"
                        :aria-pressed="activeDay === day.day"
                        @click="activeDay = day.day"
                      >
                        <small>第 {{ day.day }} 天</small
                        ><strong>{{
                          day.date.slice(5).replace('-', ' / ')
                        }}</strong
                        ><span>{{ day.stops.length }} 个地点</span>
                      </button>
                    </div>
                    <div v-if="currentDay" class="day-heading">
                      <div>

                        <h3>
                          第 {{ currentDay.day }} 天，慢慢走进{{
                            contextCity.replace(/市$/, '')
                          }}。
                        </h3>
                      </div>
                      <span>{{ currentDay.start }} — {{ currentDay.end }}</span>
                    </div>
                    <ol v-if="currentDay" class="day-timeline">
                      <li
                        v-for="(stop, index) in currentDay.stops"
                        :key="stop.candidate_id"
                        :data-stop-id="stop.candidate_id"
                        :class="{
                          'is-selected': selectedStopId === stop.candidate_id,
                        }"
                      >
                        <div class="stop-time">
                          <strong>{{ stop.arrival }}</strong
                          ><small>{{ stop.departure }}</small>
                        </div>
                        <button
                          class="stop-dot"
                          type="button"
                          :aria-label="`在地图中查看${stop.name}`"
                          :aria-pressed="selectedStopId === stop.candidate_id"
                          @click="locateStop(stop.candidate_id)"
                        >
                          {{ index + 1 }}
                        </button>
                        <article>
                          <div>
                            <h3>{{ stop.name }}</h3>
                            <button
                              v-if="run.status !== 'confirmed'"
                              class="text-button remove-stop"
                              type="button"
                              :disabled="busy"
                              :aria-label="`从草案移除${stop.name}`"
                              @click="editDraft(stop.candidate_id)"
                            >
                              <Trash2 :size="13" />移除
                            </button>
                          </div>
                          <p>
                            <span class="source-chip"
                              ><MapPin :size="11" />{{
                                sourceLabel(stop.source)
                              }}</span
                            ><span
                              ><Clock3 :size="11" />停留
                              {{ stop.stay_minutes }} 分钟</span
                            >
                          </p>
                          <small v-if="stop.timing_basis === 'planning_buffer'"
                            >时间含规划预留，交通尚需核实</small
                          ><small v-else>{{
                            index === 0
                              ? '按你设置的开始时间安排'
                              : '按已查询交通时间安排'
                          }}</small>
                        </article>
                      </li>
                      <li v-if="!currentDay.stops.length" class="empty-day">
                        这一天还没有安排地点，可继续补充。
                      </li>
                    </ol>
                    <div v-if="run.result.validation" class="budget-summary">
                      <span class="budget-symbol"><Wallet :size="20" /></span>
                      <div>
                        <small>景点费用，先心里有数</small
                        ><strong
                          >已知 ¥{{
                            run.result.validation.known_cost_yuan
                          }}</strong
                        >
                      </div>
                      <span
                        >{{
                          run.result.validation.unknown_cost_count
                        }}
                        项票价未知<br />不含住宿、餐饮与交通</span
                      >
                    </div>
                    <form
                      v-if="run.status !== 'confirmed'"
                      class="replan-form"
                      @submit.prevent="editDraft()"
                    >
                      <div>
                        <strong>给这一天，多留一点空白</strong
                        ><label
                          >想早点结束？<input
                            v-model="revisedEnd"
                            type="time"
                            required
                            aria-label="调整每天结束时间"
                        /></label>
                      </div>
                      <UiButton variant="secondary"
                        class="secondary-action"
                        type="submit"
                        :disabled="busy"
                      >
                        <RefreshCw :size="14" />重新安排并检查
                      </UiButton>
                    </form>
                  </section>
                  <section
                    id="map-panel"
                    ref="mapPanel"
                    v-show="mapVisible"
                    class="map-panel"
                    :class="{ 'map-panel--inline': inlineMap }"
                    :role="inlineMap ? 'region' : 'tabpanel'"
                    :aria-labelledby="
                      inlineMap ? 'inline-map-title' : 'map-tab'
                    "
                  >
                    <header class="panel-heading">
                      <div>

                        <h3 id="inline-map-title">
                          {{
                            inlineMap
                              ? `第 ${activeDay} 天 · 地点分布`
                              : '把沿途的地点，放在一起看。'
                          }}
                        </h3>
                        <p>
                          {{
                            inlineMap
                              ? '点选地图编号，对照当天的行程。'
                              : '地图展示地点与游览顺序，交通和导航信息仍需核实。'
                          }}
                        </p>
                      </div>
                      <button
                        v-if="inlineMap"
                        class="map-expand icon-button"
                        type="button"
                        aria-label="展开地点地图"
                        @click="resultTab = 'map'"
                      >
                        <ArrowUpRight :size="17" /></button
                      ><Map v-else :size="23" />
                    </header>
                    <AgentRouteMap
                      v-if="mapVisible"
                      :days="run.result.days ?? []"
                      :active-day="activeDay"
                      :allow-external="run.request.allow_external === true"
                      :selected-stop-id="selectedStopId"
                      :compact="inlineMap"
                      @select="selectMapStop"
                    />
                    <div
                      class="map-day-selector"
                      role="group"
                      aria-label="地图查看日期"
                    >
                      <button
                        v-for="day in run.result.days"
                        :key="day.day"
                        type="button"
                        :class="{ active: activeDay === day.day }"
                        :aria-pressed="activeDay === day.day"
                        @click="activeDay = day.day"
                      >
                        第 {{ day.day }} 天 · {{ day.stops.length }} 个地点
                      </button>
                    </div>
                    <div
                      v-if="selectedStop"
                      class="map-selection"
                      aria-live="polite"
                    >
                      <span class="selection-kicker"
                        ><MapPin :size="12" />与行程同步选中</span
                      >
                      <h4>{{ selectedStop.name }}</h4>
                      <p>
                        {{ selectedStop.arrival }} —
                        {{ selectedStop.departure }} ·
                        {{ sourceLabel(selectedStop.source) }}
                      </p>
                      <button
                        class="text-button"
                        type="button"
                        @click="revealSelectedStop"
                      >
                        查看对应行程<ArrowRight :size="13" />
                      </button>
                    </div>
                    <ol v-if="currentDay" class="map-stop-list">
                      <li
                        v-for="(stop, index) in currentDay.stops"
                        :key="stop.candidate_id"
                      >
                        <button
                          type="button"
                          :class="{
                            selected: selectedStopId === stop.candidate_id,
                          }"
                          :aria-pressed="selectedStopId === stop.candidate_id"
                          :aria-label="`选中地图地点${stop.name}`"
                          @click="
                            selectMapStop({
                              day: activeDay,
                              candidateId: stop.candidate_id,
                            })
                          "
                        >
                          <span>{{ index + 1 }}</span
                          ><span
                            ><strong>{{ stop.name }}</strong
                            ><small
                              >{{ stop.arrival }} ·
                              {{ sourceLabel(stop.source) }}</small
                            ></span
                          ><MapPin :size="13" />
                        </button>
                      </li>
                    </ol>
                    <p
                      v-if="currentDay && !currentDay.stops.length"
                      class="map-empty-day"
                    >
                      这一天还没有安排地点，地图保留其他日期的坐标供对照。
                    </p>
                  </section>
                </div></template
              >
              <template v-if="run.kind === 'story' && run.result.story_body"
                ><div class="story-paper">

                  <label
                    ><span>故事标题</span
                    ><input
                      v-model="editTitle"
                      maxlength="160"
                      :readonly="run.status === 'confirmed'" /></label
                  ><label
                    ><span>你的旅行故事</span
                    ><textarea
                      v-model="editStory"
                      maxlength="16000"
                      :readonly="run.status === 'confirmed'"
                      rows="14"
                    ></textarea></label
                  ><UiButton variant="secondary"
                    v-if="run.status !== 'confirmed'"
                    class="secondary-action"
                    type="button"
                    :disabled="busy"
                    @click="editDraft()"
                  >
                    保存草稿修改并重新检查</UiButton><small>{{
                    run.status === 'confirmed'
                      ? '已保存为独立私有快照；删除原记忆不会同步删除此故事。'
                      : '确认前请先保存你的修改。手动添加内容由你核实。'
                  }}</small>
                </div>
                <details class="source-records">
                  <summary>
                    查看
                    {{ run.result.source_memories?.length ?? 0 }} 条原始旅行记录
                  </summary>
                  <article
                    v-for="memory in run.result.source_memories"
                    :key="memory.id"
                  >
                    <small>{{ memory.date }} · {{ memory.city }}</small
                    ><strong>{{ memory.title }}</strong>
                    <p>{{ memory.body }}</p>
                    <span
                      >{{ memory.photo_count }} 张可用照片 ·
                      {{ memory.vlog_count }} 段Vlog</span
                    >
                  </article>
                </details></template
              >
              <section
                v-if="run.result.unknowns.length || run.result.warnings.length"
                class="unknown-card"
              >
                <span class="unknown-symbol"><CircleAlert :size="19" /></span>
                <div>
                  <h3>
                    {{
                      run.kind === 'story'
                        ? '保存前，再确认这些'
                        : '出发前，再确认这些'
                    }}
                  </h3>
                  <ul>
                    <li
                      v-for="(item, i) in [
                        ...run.result.unknowns,
                        ...run.result.warnings,
                      ]"
                      :key="i"
                    >
                      {{ item }}
                    </li>
                  </ul>
                </div>
              </section>
              <details
                v-if="run.result.validation?.checks.length"
                class="validation-card"
              >
                <summary>
                  <ShieldCheck :size="16" /><span>查看约束检查</span
                  ><small>{{ run.result.validation.checks.length }} 项</small
                  ><ChevronDown :size="15" />
                </summary>
                <p v-for="(item, i) in run.result.validation.checks" :key="i">
                  <span :class="item.status">{{ checkLabel(item.status) }}</span
                  >{{ item.message }}
                </p>
              </details>
              <section
                id="execution-panel"
                v-show="!hasPlan || resultTab === 'execution'"
                class="execution-card"
                :role="hasPlan ? 'tabpanel' : 'region'"
                :aria-labelledby="
                  hasPlan ? 'execution-tab' : 'execution-heading'
                "
              >
                <header>
                  <div>

                    <h3 id="execution-heading">小曦做了什么</h3>
                  </div>
                  <span>{{ run.events.length }} 条执行记录</span>
                </header>
                <p class="execution-intro">
                  以下是本次任务实际保留的调用与检查记录。未完成、重试和跳过的步骤也会如实显示。
                </p>
                <p v-if="!run.events.length" class="no-events">
                  本次任务暂未返回执行记录。
                </p>
                <ol>
                  <li v-for="event in run.events" :key="event.sequence">
                    <span class="event-dot" :class="event.status"
                      ><Check
                        v-if="
                          event.status === 'success' ||
                          event.status === 'succeeded'
                        "
                        :size="12"
                      /><CircleAlert
                        v-else-if="
                          event.status === 'failed' || event.status === 'error'
                        "
                        :size="12"
                      /><span v-else>{{ event.sequence }}</span></span
                    >
                    <div>
                      <div class="event-heading">
                        <p>{{ event.message }}</p>
                        <span :class="event.status">{{
                          eventLabel(event.status)
                        }}</span>
                      </div>
                      <small
                        >{{ event.tool
                        }}<template v-if="event.attempt > 1">
                          · 第{{ event.attempt }}次尝试</template
                        ><template v-if="event.duration_ms != null">
                          · {{ event.duration_ms }} ms</template
                        ></small
                      >
                      <details
                        v-if="
                          event.details && Object.keys(event.details).length
                        "
                      >
                        <summary>调用详情<ChevronDown :size="12" /></summary>
                        <pre>{{ JSON.stringify(event.details, null, 2) }}</pre>
                      </details>
                    </div>
                  </li>
                </ol>
              </section>
              <div
                v-if="run.status === 'confirmed'"
                class="saved-card"
                role="status"
              >
                <span><CircleCheck :size="26" /></span>
                <div>
                  <strong>{{
                    resultPractice
                      ? '演练草案已保存到当前档案。'
                      : `这段${run.kind === 'plan' ? '旅程' : '故事'}，已妥善收藏。`
                  }}</strong>
                  <p>保存在你的私人档案，可从“最近任务”重新打开。</p>
                </div>
                <ShieldCheck :size="20" />
              </div>
              <section
                v-else-if="confirmation"
                ref="confirmationAnchor"
                class="confirmation-card"
                role="region"
                aria-label="确认保存草案"
                tabindex="-1"
              >
                <div class="confirmation-heading">
                  <span><ShieldCheck :size="22" /></span>
                  <div>

                    <h3>把当前版本存入私人档案？</h3>
                  </div>
                </div>
                <p>{{ confirmation.summary }}</p>
                <p v-if="resultPractice" class="practice-save-note">
                  这是虚拟地点的离线演练。确认后会把带“离线演练”标记的草案保存到当前档案。
                </p>
                <p v-if="run.kind === 'story'">
                  保存后将形成独立故事副本；之后删除原记忆不会同步删除此副本。
                </p>
                <small
                  >第 {{ confirmation.revision }} 版 · 确认有效至
                  {{
                    new Date(confirmation.expires_at).toLocaleTimeString(
                      'zh-CN',
                    )
                  }}</small
                ><label
                  v-if="confirmation.requires_unverified_acknowledgement"
                  class="consent"
                  ><input v-model="acknowledged" type="checkbox" /><span>{{
                    run.kind === 'story'
                      ? '我了解记录和编辑内容未经独立事实核验，按条件草案保存。'
                      : '我了解仍有未核实信息，按条件草案保存，出行前自行确认。'
                  }}</span></label
                >
                <div class="confirmation-actions">
                  <UiButton variant="secondary"
                    class="secondary-action"
                    type="button"
                    :disabled="busy"
                    @click="clearConfirmation"
                  >
                    再看看</UiButton><UiButton variant="primary"
                    class="primary-action"
                    type="button"
                    :disabled="
                      busy ||
                      (confirmation.requires_unverified_acknowledgement &&
                        !acknowledged)
                    "
                    @click="save"
                  >
                    {{ busy ? '正在保存…' : '确认保存到私人档案' }}
                  </UiButton>
                </div>
              </section>
              <div v-else-if="canSave" class="save-action-card">
                <div>
                  <ShieldCheck :size="19" />
                  <p>
                    <strong>喜欢这份安排，就把它留下。</strong
                    ><span>核对当前版本后，再由你确认保存。</span>
                  </p>
                </div>
                <UiButton variant="primary"
                  class="primary-action save-preview"
                  type="button"
                  :disabled="
                    busy ||
                    editingBrief ||
                    (run.kind === 'story' &&
                      (editTitle !== run.title ||
                        editStory !== run.result.story_body))
                  "
                  @click="previewSave"
                >
                  <ShieldCheck :size="17" />核对并保存当前草案<ArrowRight
                    :size="17"
                  />
                </UiButton>
              </div>
              <div v-else-if="run.status !== 'running'" class="save-blocked">
                <CircleAlert :size="18" />
                <div>
                  <strong>{{
                    run.status === 'failed'
                      ? '本次任务还没有可保存的草案'
                      : '再补充一点，旅程就更完整'
                  }}</strong>
                  <p>补齐信息或解决冲突后，才能保存草案。</p>
                  <button
                    v-if="mode === 'plan'"
                    class="text-button"
                    type="button"
                    @click="openCandidates"
                  >
                    补充想去的地点<ArrowRight :size="14" />
                  </button>
                </div>
              </div>
            </template>
          </section>
        </div>
        <footer class="workspace-footer">
          <span
            >Voyaura
            <a href="/discover/credits.html" target="_blank" rel="noopener"
              >影像署名</a
            ></span
          ><span
            ><ShieldCheck :size="12" />不会自动购买、公开发布或点亮城市</span
          >
        </footer>
      </div>
    </div>
  </main>
</template>

<style scoped src="../styles/agent-workspace.css">

</style>
