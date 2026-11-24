import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import AgentWorkspace from './AgentWorkspace.vue'
import AgentRouteMap from '../components/AgentRouteMap.vue'
import { PRACTICE_MARKER } from '../content/plannerPractice'
import * as api from '../api/agent'
import type { AgentRun } from '../api/agent'
import { searchAttractions } from '../api/poi'
import type { PoiSearchResult } from '../types'

vi.mock('../api/agent', () => ({
  getAgentCapabilities: vi.fn(),
  listAgentRuns: vi.fn(),
  createAgentRun: vi.fn(),
  getAgentRun: vi.fn(),
  editAgentDraft: vi.fn(),
  previewAgentConfirmation: vi.fn(),
  confirmAgentRun: vi.fn(),
}))
vi.mock('../api/poi', () => ({ searchAttractions: vi.fn() }))
const fixture = (): AgentRun => ({
  id: 'test-run',
  kind: 'plan',
  status: 'awaiting_confirmation',
  revision: 1,
  title: '明确的测试行程',
  request: { daily_end: '18:00', allow_external: false },
  created_at: '2026-11-22T00:00:00Z',
  updated_at: '2026-11-22T00:00:00Z',
  saved_artifact_id: null,
  result: {
    intent_source: 'local_rules',
    verification_status: 'conditional',
    summary: '本测试使用显式夹具，不代表在线地图。',
    warnings: [],
    unknowns: ['交通时间未核实'],
    candidates: [],
    days: [
      {
        day: 1,
        date: '2026-12-01',
        start: '09:00',
        end: '10:00',
        total_minutes: 60,
        legs: [],
        stops: [
          {
            candidate_id: 'c1',
            name: '夹具地点',
            longitude: 113.3,
            latitude: 23.1,
            arrival: '09:00',
            departure: '10:00',
            stay_minutes: 60,
            timing_basis: 'user_schedule',
            source: 'user_provided',
          },
        ],
      },
    ],
    validation: { checks: [], known_cost_yuan: 0, unknown_cost_count: 1 },
  },
  events: [],
})
function button(wrapper: ReturnType<typeof mount>, text: string) {
  const found = wrapper.findAll('button').find((b) => b.text().includes(text))
  if (!found) throw new Error(`找不到按钮 ${text}`)
  return found
}
function wideScreen() {
  let listener: ((event: MediaQueryListEvent) => void) | undefined
  const remove = vi.fn()
  vi.stubGlobal('matchMedia', (query: string) => ({
    matches: query.includes('1280'),
    media: query,
    addEventListener: (
      _type: string,
      callback: (event: MediaQueryListEvent) => void,
    ) => {
      if (query.includes('1280')) listener = callback
    },
    removeEventListener: remove,
  }))
  return {
    remove,
    resize: async (matches: boolean) => {
      listener?.({ matches } as MediaQueryListEvent)
      await flushPromises()
    },
  }
}
afterEach(() => vi.unstubAllGlobals())
beforeEach(() => {
  vi.resetAllMocks()
  vi.mocked(api.getAgentCapabilities).mockResolvedValue({
    amap_configured: false,
    model_configured: false,
    intent_default: 'local_rules',
    privacy_notice: '',
    limits: {},
    tools: [],
  })
  vi.mocked(api.listAgentRuns).mockResolvedValue({ items: [] })
  vi.mocked(api.createAgentRun).mockResolvedValue(fixture())
})
describe('小曦工作流交互边界（明确测试替身）', () => {
  it('按城市搜索并选择高德地点，使用地点 ID 生成草案', async () => {
    vi.mocked(api.getAgentCapabilities).mockResolvedValue({
      amap_configured: true,
      model_configured: false,
      intent_default: 'local_rules',
      privacy_notice: '',
      limits: {},
      tools: [],
    })
    vi.mocked(searchAttractions).mockResolvedValue({
      items: [{ id: 'POI-TEST', name: '测试动物园', address: '测试街道' }],
    } as PoiSearchResult)
    const wrapper = mount(AgentWorkspace)
    await flushPromises()
    expect(wrapper.find('.manual-coordinate-entry').attributes('open')).toBeUndefined()
    await wrapper.find('input[type=search]').setValue('测试动物园')
    await button(wrapper, '搜索高德').trigger('click')
    await flushPromises()
    expect(searchAttractions).toHaveBeenCalledWith(expect.objectContaining({
      keywords: '测试动物园', city_adcode: '440100',
    }))
    await wrapper.find('button[aria-label="加入测试动物园"]').trigger('click')
    expect(wrapper.find('[aria-label="已选必去地点"]').text()).toContain('测试动物园')
    expect(button(wrapper, '用高德生成行程').exists()).toBe(true)
    await wrapper.find('form.travel-brief').trigger('submit')
    await flushPromises()
    expect(api.createAgentRun).toHaveBeenCalledWith(expect.objectContaining({
      goal: '广州市 2 日游',
      candidates: [],
      selected_pois: [{ id: 'POI-TEST', name: '测试动物园' }],
      allow_external: true,
    }))
  })

  it('直达历史任务只读取并恢复原输入，授权默认关闭，不自动执行或确认', async () => {
    const run = {
      ...fixture(),
      request: {
        goal: '明确历史测试输入',
        city_adcode: '350200',
        daily_end: '18:00',
        allow_external: true,
        allow_model: true,
      },
    }
    vi.mocked(api.getAgentRun).mockResolvedValue(run)
    const wrapper = mount(AgentWorkspace, { props: { initialRunId: run.id } })
    await flushPromises()
    expect(api.getAgentRun).toHaveBeenCalledWith(run.id)
    expect(api.createAgentRun).not.toHaveBeenCalled()
    expect(api.previewAgentConfirmation).not.toHaveBeenCalled()
    await button(wrapper, '调整旅行条件').trigger('click')
    expect(
      wrapper.get<HTMLTextAreaElement>(
        'textarea[aria-label="这次想怎样旅行？"]',
      ).element.value,
    ).toBe('明确历史测试输入')
    expect(
      wrapper
        .findAll<HTMLInputElement>('.permission-card input')
        .every((input) => !input.element.checked),
    ).toBe(true)
    wrapper.unmount()
  })
  it('输入产生脏状态，提交真实任务后清除；未保存的故事编辑重新标记', async () => {
    const run: AgentRun = {
      ...fixture(),
      kind: 'story',
      title: '测试故事',
      result: {
        ...fixture().result,
        days: [],
        story_body: '明确来源的测试正文',
      },
    }
    vi.mocked(api.createAgentRun).mockResolvedValue(run)
    const wrapper = mount(AgentWorkspace, { props: { initialKind: 'story' } })
    await flushPromises()
    await wrapper.get('textarea').setValue('明确的测试输入')
    expect(wrapper.emitted('dirtyChange')?.at(-1)).toEqual([true])
    await wrapper.get('.story-consent input').setValue(true)
    await wrapper.get('.travel-brief').trigger('submit')
    await flushPromises()
    expect(wrapper.emitted('dirtyChange')?.at(-1)).toEqual([false])
    await wrapper.get('.story-paper textarea').setValue('还没有保存的正文修改')
    expect(wrapper.emitted('dirtyChange')?.at(-1)).toEqual([true])
    wrapper.unmount()
  })
  it('默认不授权外部工具，条件草案须先预览再主动勾选才能保存', async () => {
    const wrapper = mount(AgentWorkspace)
    await flushPromises()
    await wrapper.find('.travel-brief textarea').setValue('测试两天的轻松行程')
    await wrapper.find('form.travel-brief').trigger('submit')
    await flushPromises()
    expect(api.createAgentRun).toHaveBeenCalledWith(
      expect.objectContaining({
        allow_external: false,
        allow_model: false,
        allow_memory_access: false,
        candidates: [],
      }),
    )
    expect(wrapper.text()).toContain('条件草案')
    expect(wrapper.text()).toContain('你提供的地点')
    expect(wrapper.text()).toContain('交通时间未核实')
    const proof = {
      confirmation_token: 'test-token',
      content_digest: 'test-digest',
      expires_at: '2099-01-01T00:00:00Z',
      revision: 1,
      summary: '测试预览',
      requires_unverified_acknowledgement: true,
    }
    vi.mocked(api.previewAgentConfirmation).mockResolvedValue(proof)
    await button(wrapper, '核对并保存当前草案').trigger('click')
    await flushPromises()
    expect(api.confirmAgentRun).not.toHaveBeenCalled()
    expect(
      button(wrapper, '确认保存到私人档案').attributes('disabled'),
    ).toBeDefined()
    await wrapper.find('.confirmation-card input[type=checkbox]').setValue(true)
    vi.mocked(api.confirmAgentRun).mockResolvedValue({
      ...fixture(),
      status: 'confirmed',
      saved_artifact_id: 'artifact-test',
    })
    await button(wrapper, '确认保存到私人档案').trigger('click')
    await flushPromises()
    expect(api.confirmAgentRun).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'test-run' }),
      proof,
      true,
    )
    expect(wrapper.text()).toContain('已妥善收藏')
  })
  it('网络失败保留同一请求号供重试，不重复创建新的操作', async () => {
    vi.mocked(api.createAgentRun)
      .mockRejectedValueOnce(new Error('测试网络中断'))
      .mockResolvedValueOnce(fixture())
    const wrapper = mount(AgentWorkspace)
    await flushPromises()
    await wrapper.find('.travel-brief textarea').setValue('测试请求重试')
    await wrapper.find('form.travel-brief').trigger('submit')
    await flushPromises()
    const first = vi.mocked(api.createAgentRun).mock.calls[0]![0]
    await button(wrapper, '重试同一任务').trigger('click')
    await flushPromises()
    expect(vi.mocked(api.createAgentRun).mock.calls[1]![0]).toEqual(first)
  })
  it('故事未授权不发请求，编辑后须保存新版本才允许预览确认', async () => {
    const story: AgentRun = {
      ...fixture(),
      kind: 'story',
      title: '测试故事',
      result: {
        ...fixture().result,
        verification_status: 'validated',
        days: [],
        story_body: '原始夹具记录。',
        source_memories: [],
      },
    }
    vi.mocked(api.createAgentRun).mockResolvedValue(story)
    const wrapper = mount(AgentWorkspace, { props: { initialKind: 'story' } })
    await flushPromises()
    await wrapper.find('.travel-brief textarea').setValue('整理测试回忆')
    await wrapper.find('form.travel-brief').trigger('submit')
    await flushPromises()
    expect(api.createAgentRun).not.toHaveBeenCalled()
    await wrapper.find('.travel-brief input[type=checkbox]').setValue(true)
    await wrapper.find('form.travel-brief').trigger('submit')
    await flushPromises()
    expect(api.createAgentRun).toHaveBeenCalledWith(
      expect.objectContaining({
        allow_memory_access: true,
        allow_external: false,
        allow_model: false,
      }),
    )
    await wrapper.find('.story-paper textarea').setValue('我编辑的测试故事。')
    expect(
      button(wrapper, '核对并保存当前草案').attributes('disabled'),
    ).toBeDefined()
    vi.mocked(api.editAgentDraft).mockResolvedValue({
      ...story,
      revision: 2,
      result: { ...story.result, story_body: '我编辑的测试故事。' },
    })
    await button(wrapper, '保存草稿修改').trigger('click')
    await flushPromises()
    expect(api.editAgentDraft).toHaveBeenCalledWith('test-run', {
      expected_revision: 1,
      title: '测试故事',
      story_body: '我编辑的测试故事。',
    })
    expect(
      button(wrapper, '核对并保存当前草案').attributes('disabled'),
    ).toBeUndefined()
  })
  it('空候选和服务未配置时显示信息不足，不提供确认保存', async () => {
    const missing = fixture()
    missing.status = 'needs_input'
    missing.result.verification_status = 'information_missing'
    // The real API can return empty day shells along with needs_input.
    missing.result.days = [{ ...missing.result.days![0]!, stops: [] }]
    vi.mocked(api.createAgentRun).mockResolvedValue(missing)
    const wrapper = mount(AgentWorkspace)
    await flushPromises()
    await wrapper.find('.travel-brief textarea').setValue('测试没有候选')
    await wrapper.find('form.travel-brief').trigger('submit')
    await flushPromises()
    expect(wrapper.text()).toContain('信息不足')
    expect(wrapper.find('.save-preview').exists()).toBe(false)
    expect(wrapper.find('form.travel-brief').isVisible()).toBe(true)
    expect(api.previewAgentConfirmation).not.toHaveBeenCalled()
  })
  it('中断任务缺少结果时展示刷新，不崩溃也不提供保存', async () => {
    vi.mocked(api.createAgentRun).mockResolvedValue({
      ...fixture(),
      status: 'running',
      result: {},
    } as AgentRun)
    const wrapper = mount(AgentWorkspace)
    await flushPromises()
    await wrapper.find('.travel-brief textarea').setValue('检查中断恢复')
    await wrapper.find('form.travel-brief').trigger('submit')
    await flushPromises()
    expect(wrapper.text()).toContain('任务正在执行')
    expect(wrapper.text()).toContain('刷新任务状态')
    expect(wrapper.find('.save-preview').exists()).toBe(false)
  })
  it('连续排除候选保留先前排除项，不把旧地点重新放回行程', async () => {
    const first = fixture()
    first.request.excluded_candidate_ids = ['previously-excluded']
    vi.mocked(api.createAgentRun).mockResolvedValue(first)
    vi.mocked(api.editAgentDraft).mockResolvedValue({ ...first, revision: 2 })
    const wrapper = mount(AgentWorkspace)
    await flushPromises()
    await wrapper.find('.travel-brief textarea').setValue('测试连续排除')
    await wrapper.find('form.travel-brief').trigger('submit')
    await flushPromises()
    await wrapper.find('[aria-label="从草案移除夹具地点"]').trigger('click')
    await flushPromises()
    expect(api.editAgentDraft).toHaveBeenCalledWith(
      'test-run',
      expect.objectContaining({
        excluded_candidate_ids: ['previously-excluded', 'c1'],
      }),
    )
  })
  it('点选兴趣遵守最多三项，取消后可换选并提交真实表单值', async () => {
    const wrapper = mount(AgentWorkspace)
    await flushPromises()
    await wrapper.find('.travel-brief textarea').setValue('测试兴趣与表单条件')
    const interests = wrapper.find('[aria-label="旅行兴趣"]')
    const option = (name: string) =>
      interests.findAll('button').find((b) => b.text() === name)!
    for (const name of ['博物馆', '美食', '海边'])
      await option(name).trigger('click')
    expect(option('自然风光').attributes('disabled')).toBeDefined()
    await option('博物馆').trigger('click')
    expect(option('自然风光').attributes('disabled')).toBeUndefined()
    await option('自然风光').trigger('click')
    await wrapper.find('form.travel-brief').trigger('submit')
    await flushPromises()
    expect(api.createAgentRun).toHaveBeenCalledWith(
      expect.objectContaining({
        interests: ['美食', '海边', '自然风光'],
        allow_external: false,
        allow_model: false,
      }),
    )
  })
  it('每日安排、地图日期与执行记录切换展示各自真实内容', async () => {
    const value = fixture()
    value.result.days!.push({
      ...value.result.days![0]!,
      day: 2,
      date: '2026-12-02',
      stops: [
        {
          ...value.result.days![0]!.stops[0]!,
          candidate_id: 'c2',
          name: '次日夹具地点',
        },
      ],
    })
    vi.mocked(api.createAgentRun).mockResolvedValue(value)
    const wrapper = mount(AgentWorkspace)
    await flushPromises()
    await wrapper.find('.travel-brief textarea').setValue('测试按天查看与地图切换')
    await wrapper.find('form.travel-brief').trigger('submit')
    await flushPromises()
    await wrapper.find('#map-tab').trigger('click')
    expect(wrapper.find('#map-panel').isVisible()).toBe(true)
    expect(wrapper.find('#schedule-panel').isVisible()).toBe(false)
    expect(wrapper.find('.agent-map').text()).toContain('非导航底图')
    await wrapper.findAll('.map-day-selector button')[1]!.trigger('click')
    expect(wrapper.find('.map-stop-list').text()).toContain('次日夹具地点')
    await wrapper.find('#schedule-tab').trigger('click')
    expect(wrapper.find('.day-timeline').text()).toContain('次日夹具地点')
    expect(wrapper.findAll('.day-timeline h3').map((h) => h.text())).toEqual([
      '次日夹具地点',
    ])
    await wrapper.find('#execution-tab').trigger('click')
    expect(wrapper.find('.execution-card').isVisible()).toBe(true)
    expect(wrapper.find('.execution-card').text()).toContain('暂未返回执行记录')
  })
  it('恢复历史任务后调整条件采用该任务输入，外部工具仍需重新授权', async () => {
    const value = fixture()
    value.status = 'confirmed'
    let finish: (result: AgentRun) => void = () => {}
    vi.mocked(api.createAgentRun).mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finish = resolve
        }),
    )
    value.request = {
      goal: '历史任务中的杭州计划',
      city_adcode: '330100',
      start_date: '2026-12-03',
      days: 2,
      daily_start: '10:00',
      daily_end: '17:00',
      budget_yuan: 200,
      pace: 'balanced',
      transport: 'walking',
      interests: ['博物馆'],
      must_visit: [],
      allow_external: true,
      allow_model: true,
      candidates: [
        {
          name: '[测试夹具] 杭州地点',
          longitude: 120.15,
          latitude: 30.25,
          stay_minutes: 45,
          cost_yuan: null,
        },
      ],
    }
    vi.mocked(api.listAgentRuns).mockResolvedValue({ items: [value] })
    vi.mocked(api.getAgentRun).mockResolvedValue(value)
    const wrapper = mount(AgentWorkspace)
    await flushPromises()
    await button(wrapper, '最近任务').trigger('click')
    await wrapper.find('.history-strip > button').trigger('click')
    await flushPromises()
    await button(wrapper, '调整旅行条件').trigger('click')
    await flushPromises()
    expect(
      wrapper.find<HTMLTextAreaElement>('[aria-label="这次想怎样旅行？"]')
        .element.value,
    ).toBe('历史任务中的杭州计划')
    expect(
      wrapper.find<HTMLSelectElement>('[aria-label="目的地"]').element.value,
    ).toBe('330100')
    expect(
      wrapper.find<HTMLInputElement>('[aria-label="出发日期"]').element.value,
    ).toBe('2026-12-03')
    expect(
      wrapper.find<HTMLInputElement>('.permission-card input[type=checkbox]')
        .element.checked,
    ).toBe(false)
    await wrapper.find('form.travel-brief').trigger('submit')
    await flushPromises()
    expect(
      wrapper.find('.workflow-steps [aria-current=step]').text(),
    ).toContain('整理草案')
    finish(fixture())
    await flushPromises()
    expect(api.createAgentRun).toHaveBeenCalledWith(
      expect.objectContaining({
        city_adcode: '330100',
        start_date: '2026-12-03',
        daily_start: '10:00',
        budget_yuan: 200,
        transport: 'walking',
        allow_external: false,
        allow_model: false,
        candidates: [
          expect.objectContaining({
            name: '[测试夹具] 杭州地点',
            longitude: 120.15,
          }),
        ],
      }),
    )
  })
  it('等待真实请求时只显示等待状态，不把尚未返回的工具标记完成', async () => {
    let finish: (value: AgentRun) => void = () => {}
    vi.mocked(api.createAgentRun).mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finish = resolve
        }),
    )
    const wrapper = mount(AgentWorkspace)
    await flushPromises()
    await wrapper.find('.travel-brief textarea').setValue('测试等待中的真实边界')
    await wrapper.find('form.travel-brief').trigger('submit')
    await flushPromises()
    expect(wrapper.text()).toContain('正在等待本次任务结果')
    expect(
      wrapper.find('.workflow-steps [aria-current=step]').text(),
    ).toContain('整理草案')
    expect(wrapper.find('.execution-card').exists()).toBe(false)
    expect(wrapper.find('.save-preview').exists()).toBe(false)
    finish(fixture())
    await flushPromises()
    expect(wrapper.text()).toContain('条件草案')
    expect(
      wrapper.find('.workflow-steps [aria-current=step]').text(),
    ).toContain('核对细节')
  })
  it('宽屏同屏只挂载一个地图，站点与日期联动且缩放后保留选中地点', async () => {
    const screen = wideScreen()
    const value = fixture()
    value.result.days!.push({
      ...value.result.days![0]!,
      day: 2,
      date: '2026-12-02',
      stops: [
        {
          ...value.result.days![0]!.stops[0]!,
          candidate_id: 'c2',
          name: '次日夹具地点',
        },
      ],
    })
    vi.mocked(api.createAgentRun).mockResolvedValue(value)
    const wrapper = mount(AgentWorkspace, { attachTo: document.body })
    await flushPromises()
    await wrapper.find('.travel-brief textarea').setValue('测试同屏与站点联动')
    await wrapper.find('form.travel-brief').trigger('submit')
    await flushPromises()
    expect(wrapper.find('.plan-panels.is-split').exists()).toBe(true)
    expect(wrapper.find('#schedule-panel').isVisible()).toBe(true)
    expect(wrapper.find('#map-panel').isVisible()).toBe(true)
    expect(wrapper.findAllComponents(AgentRouteMap)).toHaveLength(1)
    await wrapper.find('.stop-dot').trigger('click')
    expect(wrapper.find('.day-timeline li.is-selected h3').text()).toBe(
      '夹具地点',
    )
    expect(wrapper.findComponent(AgentRouteMap).props('selectedStopId')).toBe(
      'c1',
    )
    wrapper
      .findComponent(AgentRouteMap)
      .vm.$emit('select', { day: 2, candidateId: 'c2' })
    await flushPromises()
    expect(wrapper.find('.day-heading').text()).toContain('第 2 天')
    expect(wrapper.find('.map-selection h4').text()).toBe('次日夹具地点')
    await screen.resize(false)
    expect(wrapper.find('.plan-panels.is-split').exists()).toBe(false)
    expect(wrapper.findAllComponents(AgentRouteMap)).toHaveLength(0)
    await wrapper.find('.stop-dot').trigger('click')
    await flushPromises()
    expect(wrapper.find('#map-panel').isVisible()).toBe(true)
    expect(wrapper.find('#schedule-panel').isVisible()).toBe(false)
    const instance = wrapper.findComponent(AgentRouteMap).element
    await screen.resize(true)
    await wrapper.find('#schedule-tab').trigger('click')
    expect(wrapper.findComponent(AgentRouteMap).element).toBe(instance)
    expect(wrapper.findAllComponents(AgentRouteMap)).toHaveLength(1)
    expect(wrapper.findComponent(AgentRouteMap).props('selectedStopId')).toBe(
      'c2',
    )
    wrapper.unmount()
    expect(screen.remove).toHaveBeenCalled()
  })
  it('重新规划移除选中地点后清除地图高亮，不显示已经删除的站点', async () => {
    wideScreen()
    const updated = fixture()
    updated.revision = 2
    updated.result.days![0]!.stops = [
      {
        ...updated.result.days![0]!.stops[0]!,
        candidate_id: 'c2',
        name: '保留的夹具地点',
      },
    ]
    vi.mocked(api.editAgentDraft).mockResolvedValue(updated)
    const wrapper = mount(AgentWorkspace)
    await flushPromises()
    await wrapper.find('.travel-brief textarea').setValue('测试移除选中站点')
    await wrapper.find('form.travel-brief').trigger('submit')
    await flushPromises()
    await wrapper.find('.stop-dot').trigger('click')
    expect(wrapper.find('.map-selection').exists()).toBe(true)
    await wrapper.find('[aria-label="从草案移除夹具地点"]').trigger('click')
    await flushPromises()
    expect(wrapper.find('.map-selection').exists()).toBe(false)
    expect(
      wrapper.findComponent(AgentRouteMap).props('selectedStopId'),
    ).toBeNull()
    expect(wrapper.find('.day-timeline').text()).toContain('保留的夹具地点')
  })
  it('演练入口只填写虚拟条件、不自动创建任务，并能恢复原输入', async () => {
    const wrapper = mount(AgentWorkspace)
    await flushPromises()
    await wrapper.find('.travel-brief textarea').setValue('我自己原来填写的计划')
    await wrapper.find('[aria-label="目的地"]').setValue('330100')
    await wrapper.find('[aria-label="景点预算 / 元"]').setValue(180)
    await wrapper.find('.permission-card input[type=checkbox]').setValue(true)
    await button(wrapper, '填入离线演练条件').trigger('click')
    await flushPromises()
    expect(api.createAgentRun).not.toHaveBeenCalled()
    expect(api.editAgentDraft).not.toHaveBeenCalled()
    expect(wrapper.find('.practice-notice').text()).toContain('虚拟地点')
    expect(wrapper.findAll('.candidate-content fieldset')).toHaveLength(4)
    expect(
      wrapper.find<HTMLInputElement>('.permission-card input[type=checkbox]')
        .element.checked,
    ).toBe(false)
    expect(
      wrapper
        .find('.permission-card input[type=checkbox]')
        .attributes('disabled'),
    ).toBeDefined()
    await button(wrapper, '恢复我之前的输入').trigger('click')
    await flushPromises()
    expect(wrapper.find<HTMLTextAreaElement>('.travel-brief textarea').element.value).toBe(
      '我自己原来填写的计划',
    )
    expect(
      wrapper.find<HTMLSelectElement>('[aria-label="目的地"]').element.value,
    ).toBe('330100')
    expect(
      wrapper.find<HTMLInputElement>('[aria-label="景点预算 / 元"]').element
        .value,
    ).toBe('180')
    expect(wrapper.findAll('.candidate-content fieldset')).toHaveLength(0)
    expect(api.createAgentRun).not.toHaveBeenCalled()
  })
  it('主动生成演练时走创建和草案标记接口，明确关闭全部外部调用', async () => {
    const value = fixture()
    vi.mocked(api.createAgentRun).mockImplementation(async (payload) => ({
      ...value,
      request: { ...payload },
    }))
    vi.mocked(api.editAgentDraft).mockImplementation(async (_id, edit) => ({
      ...value,
      title: edit.title!,
      revision: 2,
      request: { ...vi.mocked(api.createAgentRun).mock.calls[0]![0] },
    }))
    const wrapper = mount(AgentWorkspace)
    await flushPromises()
    await button(wrapper, '填入离线演练条件').trigger('click')
    await wrapper.find('form.travel-brief').trigger('submit')
    await flushPromises()
    const payload = vi.mocked(api.createAgentRun).mock.calls[0]![0]
    expect(payload.goal.startsWith(PRACTICE_MARKER)).toBe(true)
    expect(payload.candidates).toHaveLength(4)
    expect(
      payload.candidates.every((c) => c.name.startsWith(PRACTICE_MARKER)),
    ).toBe(true)
    expect(payload.allow_external).toBe(false)
    expect(payload.allow_model).toBe(false)
    expect(payload.allow_memory_access).toBe(false)
    expect(api.editAgentDraft).toHaveBeenCalledWith('test-run', {
      expected_revision: 1,
      title: expect.stringContaining(PRACTICE_MARKER),
    })
    expect(wrapper.find('.result-heading').text()).toContain(PRACTICE_MARKER)
    expect(wrapper.find('.practice-notice').exists()).toBe(true)
    expect(api.confirmAgentRun).not.toHaveBeenCalled()
  })
  it('演练标记写入失败可用同一请求号重试，不伪装成已完成', async () => {
    const value = fixture()
    vi.mocked(api.createAgentRun).mockImplementation(async (payload) => ({
      ...value,
      request: { ...payload },
    }))
    vi.mocked(api.editAgentDraft)
      .mockRejectedValueOnce(new Error('明确测试的标记写入中断'))
      .mockResolvedValueOnce({
        ...value,
        title: `${PRACTICE_MARKER} 虚拟地点规划`,
        revision: 2,
        request: { goal: `${PRACTICE_MARKER} 练习` },
      })
    const wrapper = mount(AgentWorkspace)
    await flushPromises()
    await button(wrapper, '填入离线演练条件').trigger('click')
    await wrapper.find('form.travel-brief').trigger('submit')
    await flushPromises()
    expect(wrapper.find('.workspace-error').text()).toContain('标记写入中断')
    expect(wrapper.find('.save-preview').exists()).toBe(false)
    const first = vi.mocked(api.createAgentRun).mock.calls[0]![0]
    await button(wrapper, '重试同一任务').trigger('click')
    await flushPromises()
    expect(vi.mocked(api.createAgentRun).mock.calls[1]![0]).toEqual(first)
    expect(wrapper.find('.result-heading').text()).toContain(PRACTICE_MARKER)
    expect(api.confirmAgentRun).not.toHaveBeenCalled()
  })
})
