<script setup lang="ts">
import { AlertTriangle, Camera, Check, Film, LoaderCircle, Trash2, X } from 'lucide-vue-next'
import type { AppErrorInfo, MediaDeletePreview, VisitedCity } from '../types'

defineProps<{
  city: VisitedCity
  phase: 'loading' | 'preview' | 'deleting' | 'success' | 'error'
  preview: MediaDeletePreview | null
  error: AppErrorInfo | null
}>()

const emit = defineEmits<{
  cancel: []
  confirm: []
}>()

function formatBytes(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  return `${Math.max(1, Math.round(bytes / 1024))} KB`
}
</script>

<template>
  <div class="dialog-backdrop media-delete-backdrop" @click.self="emit('cancel')">
    <section class="media-delete-dialog" role="dialog" aria-modal="true" aria-labelledby="media-delete-title">
      <header>
        <div>
          <p class="eyebrow">PRIVATE MEDIA · {{ city.adcode }}</p>
          <h2 id="media-delete-title">删除媒体</h2>
        </div>
        <button type="button" title="关闭删除确认" aria-label="关闭删除确认" @click="emit('cancel')"><X :size="20" /></button>
      </header>

      <div v-if="phase === 'loading' || phase === 'deleting'" class="media-delete-state" aria-live="polite">
        <LoaderCircle class="spin" :size="30" />
        <strong>{{ phase === 'loading' ? '正在核对媒体' : '正在删除私有文件' }}</strong>
        <p>{{ phase === 'loading' ? '读取文件状态与所属记忆' : '同步清理原文件、预览图和媒体记录' }}</p>
      </div>

      <div v-else-if="phase === 'preview' && preview" class="media-delete-preview">
        <span class="media-delete-icon"><Camera v-if="preview.kind === 'photo'" :size="25" /><Film v-else :size="25" /></span>
        <small>{{ preview.memory_title }} · {{ preview.city_name }}</small>
        <h3>{{ preview.original_filename }}</h3>
        <p>{{ formatBytes(preview.byte_size) }} · {{ preview.kind === 'photo' ? '照片' : 'Vlog' }}</p>
        <p>{{ preview.confirmation_notice }}</p>
        <div class="memory-composer-actions">
          <button type="button" class="secondary" @click="emit('cancel')">保留文件</button>
          <button type="button" class="danger-primary" @click="emit('confirm')"><Trash2 :size="16" />确认删除</button>
        </div>
      </div>

      <div v-else-if="phase === 'success'" class="media-delete-state success" aria-live="polite">
        <span><Check :size="27" /></span>
        <strong>媒体已经删除</strong>
        <p>城市统计和记忆内容已经同步更新。</p>
        <button type="button" @click="emit('cancel')">返回城市档案</button>
      </div>

      <div v-else-if="phase === 'error' && error" class="media-delete-state error" role="alert">
        <span><AlertTriangle :size="27" /></span>
        <strong>{{ error.message }}</strong>
        <code>{{ error.code }}</code>
        <small v-if="error.requestId">请求编号：{{ error.requestId }}</small>
        <button type="button" @click="emit('cancel')">关闭</button>
      </div>
    </section>
  </div>
</template>
