<script setup lang="ts">
import { MoveHorizontal } from 'lucide-vue-next'
import { ref } from 'vue'

withDefaults(defineProps<{
  sourceUrl: string
  resultUrl: string
  sourceAlt?: string
  resultAlt?: string
}>(), {
  sourceAlt: '旅行原图',
  resultAlt: '风格生成图',
})

const position = ref(50)
</script>

<template>
  <figure class="image-compare-slider">
    <div class="compare-stage">
      <img class="compare-source" :src="sourceUrl" :alt="sourceAlt" />
      <div class="compare-result" :style="{ clipPath: `inset(0 ${100 - position}% 0 0)` }">
        <img :src="resultUrl" :alt="resultAlt" />
      </div>
      <span class="compare-label compare-label-result">生成图</span>
      <span class="compare-label compare-label-source">原图</span>
      <span class="compare-divider" :style="{ left: `${position}%` }" aria-hidden="true">
        <i><MoveHorizontal :size="16" /></i>
      </span>
      <input
        v-model.number="position"
        class="compare-range"
        type="range"
        min="0"
        max="100"
        step="1"
        aria-label="拖动比较原图和生成图"
      />
    </div>
    <figcaption>左右拖动查看风格变化</figcaption>
  </figure>
</template>
