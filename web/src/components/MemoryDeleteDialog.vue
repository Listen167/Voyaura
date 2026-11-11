<script setup lang="ts">
import { AlertTriangle, Check, LoaderCircle, Trash2, X } from 'lucide-vue-next'
import type { AppErrorInfo, CityMemoryDeletePreview, VisitedCity } from '../types'

defineProps<{
  city: VisitedCity
  phase: 'loading' | 'preview' | 'deleting' | 'success' | 'error'
  preview: CityMemoryDeletePreview | null
  error: AppErrorInfo | null
}>()

const emit = defineEmits<{
  cancel: []
  confirm: []
}>()

const dateFormatter = new Intl.DateTimeFormat('zh-CN', {
  year: 'numeric',
  month: 'long',
  day: 'numeric',
})
</script>

<template>
  <div class="dialog-backdrop memory-delete-backdrop" @click.self="emit('cancel')">
    <section class="memory-delete-dialog" role="alertdialog" aria-modal="true" aria-labelledby="memory-delete-title">
      <header>
        <div>
          <p class="eyebrow">DELETE MEMORY · {{ city.adcode }}</p>
          <h2 id="memory-delete-title">删除城市记忆</h2>
        </div>
        <button type="button" title="关闭删除确认" aria-label="关闭删除确认" @click="emit('cancel')"><X :size="20" /></button>
      </header>

      <div v-if="phase === 'loading' || phase === 'deleting'" class="memory-delete-state" aria-live="polite">
        <LoaderCircle class="spin" :size="30" />
        <strong>{{ phase === 'loading' ? '正在核对记忆' : '正在删除记忆' }}</strong>
        <p>{{ phase === 'loading' ? '删除前不会修改任何内容。' : '请稍候，不要重复提交。' }}</p>
      </div>

      <div v-else-if="phase === 'preview' && preview" class="memory-delete-preview">
        <span class="memory-delete-icon"><Trash2 :size="25" /></span>
        <small>{{ dateFormatter.format(new Date(preview.occurred_at)) }} · {{ preview.city_name }}</small>
        <h3>{{ preview.title }}</h3>
        <p>{{ preview.confirmation_notice }}</p>
        <p v-if="preview.media_count" class="memory-delete-media-warning">这段记忆关联 {{ preview.media_count }} 个媒体文件记录。</p>
        <div class="memory-composer-actions">
          <button type="button" class="secondary" @click="emit('cancel')">保留记忆</button>
          <button type="button" class="danger-primary" @click="emit('confirm')"><Trash2 :size="16" />确认删除</button>
        </div>
      </div>

      <div v-else-if="phase === 'success'" class="memory-delete-state success" aria-live="polite">
        <span><Check :size="27" /></span>
        <strong>记忆已经删除</strong>
        <p>城市档案与地图统计已经更新。</p>
        <button type="button" class="secondary" @click="emit('cancel')">回到城市档案</button>
      </div>

      <div v-else-if="phase === 'error' && error" class="memory-delete-state error" role="alert">
        <span><AlertTriangle :size="26" /></span>
        <strong>{{ error.message }}</strong>
        <code>{{ error.code }}</code>
        <small v-if="error.requestId">请求编号：{{ error.requestId }}</small>
        <button type="button" class="secondary" @click="emit('cancel')">关闭</button>
      </div>
    </section>
  </div>
</template>
