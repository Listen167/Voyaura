import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import CheckInDialog from './CheckInDialog.vue'

const baseProps = {
  preview: null,
  error: null,
  locationMode: 'device-high' as const,
  manualResults: [],
  manualBusy: false,
  manualError: null,
}

describe('CheckInDialog', () => {
  it('searches for a manually entered city', async () => {
    const wrapper = mount(CheckInDialog, {
      props: { ...baseProps, phase: 'manual' },
    })

    await wrapper.get('input[aria-label="输入城市名称"]').setValue('广州市')
    await wrapper.get('form').trigger('submit')

    expect(wrapper.emitted('searchManual')?.[0]).toEqual(['广州市'])
  })

  it('offers IP and manual fallbacks after location failure', async () => {
    const wrapper = mount(CheckInDialog, {
      props: {
        ...baseProps,
        phase: 'error',
        error: {
          code: 'LOCATION_TIMEOUT',
          message: '获取位置超时。',
          details: {},
          retryable: true,
        },
      },
    })

    const buttons = wrapper.findAll('.location-fallback-actions button')
    expect(buttons).toHaveLength(2)
    await buttons[0].trigger('click')
    await buttons[1].trigger('click')
    expect(wrapper.emitted('useIp')).toHaveLength(1)
    expect(wrapper.emitted('openManual')).toHaveLength(1)
  })
})
