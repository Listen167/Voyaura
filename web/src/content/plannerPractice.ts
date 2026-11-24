import type { UserCandidate } from '../api/agent'

export const PRACTICE_MARKER = '[离线演练]'

/** Practice input belongs to an explicitly enabled development/test environment. */
export function canUsePlannerPractice() {
  return import.meta.env.DEV && import.meta.env.VITE_ENABLE_PLANNER_PRACTICE === 'true'
}

export function isPracticeRequest(request: Record<string, unknown>) {
  return (
    (typeof request.goal === 'string' && request.goal.startsWith(PRACTICE_MARKER)) ||
    (Array.isArray(request.candidates) &&
      request.candidates.some(
        (candidate) =>
          candidate &&
          typeof candidate.name === 'string' &&
          candidate.name.startsWith(PRACTICE_MARKER),
      ))
  )
}

/** Virtual input for exercising the real local planner. These are not real POIs or travel records. */
export function practiceBrief() {
  const coordinates = [
    [113.32, 23.11],
    [113.3, 23.12],
    [113.31, 23.13],
    [113.29, 23.15],
  ] as const
  return {
    goal: `${PRACTICE_MARKER} 使用四个虚拟地点练习两天规划、地图联动与确认保存，不代表真实出游。`,
    cityAdcode: '440100',
    candidates: coordinates.map(
      ([longitude, latitude], index): UserCandidate => ({
        name: `${PRACTICE_MARKER} 虚拟地点${String.fromCharCode(65 + index)}`,
        longitude,
        latitude,
        stay_minutes: 60,
        cost_yuan: null,
        opening_start: null,
        opening_end: null,
        must_visit: false,
      }),
    ),
  }
}
