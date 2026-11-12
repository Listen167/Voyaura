import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import ImageCompareSlider from './ImageCompareSlider.vue'

describe('ImageCompareSlider', () => {
  it('moves the comparison divider with an accessible range input', async () => {
    const wrapper = mount(ImageCompareSlider, {
      props: {
        sourceUrl: 'http://storage.test/source.jpg',
        resultUrl: 'http://storage.test/result.webp',
      },
    })

    const slider = wrapper.get('input[aria-label="拖动比较原图和生成图"]')
    expect(wrapper.get('.compare-divider').attributes('style')).toContain('50%')
    await slider.setValue('72')
    expect(wrapper.get('.compare-divider').attributes('style')).toContain('72%')
    expect(wrapper.get('.compare-result').attributes('style')).toContain('28%')
  })
})
