<script setup lang="ts">
import { AlertTriangle, LoaderCircle, Trash2, X } from 'lucide-vue-next'
import type { AppErrorInfo, ImageJobDeletePreview } from '../types'

defineProps<{
  phase: 'loading' | 'ready' | 'deleting' | 'error'
  preview: ImageJobDeletePreview | null
  error: AppErrorInfo | null
}>()

const emit = defineEmits<{
  cancel: []
  confirm: []
}>()
</script>

<template>
  <div class="dialog-backdrop image-job-delete-backdrop" role="presentation" @click.self="emit('cancel')">
    <section class="image-job-delete-dialog" role="dialog" aria-modal="true" aria-labelledby="image-job-delete-title">
      <header>
        <div><p class="eyebrow">REMOVE CREATION</p><h2 id="image-job-delete-title">删除生成记录</h2></div>
        <button type="button" title="关闭删除确认" aria-label="关闭删除确认" @click="emit('cancel')"><X :size="20" /></button>
      </header>

      <div v-if="phase === 'loading' || phase === 'deleting'" class="image-job-delete-state" aria-live="polite">
        <LoaderCircle class="spin" :size="30" />
        <strong>{{ phase === 'loading' ? '正在检查生成记录' : '正在删除生成记录' }}</strong>
      </div>

      <div v-else-if="phase === 'ready' && preview" class="image-job-delete-state">
        <span class="delete-symbol"><Trash2 :size="23" /></span>
        <small>{{ preview.city_name }} · {{ preview.memory_title }}</small>
        <strong>{{ preview.style.name }}</strong>
        <p>{{ preview.confirmation_notice }}</p>
        <p class="delete-source-name">{{ preview.source_filename }}</p>
        <footer>
          <button type="button" class="secondary" @click="emit('cancel')">保留</button>
          <button type="button" class="danger-primary" @click="emit('confirm')"><Trash2 :size="15" />确认删除</button>
        </footer>
      </div>

      <div v-else-if="phase === 'error' && error" class="image-job-delete-state error" role="alert">
        <AlertTriangle :size="30" />
        <strong>{{ error.message }}</strong>
        <code>{{ error.code }}</code>
        <small v-if="error.requestId">请求编号：{{ error.requestId }}</small>
        <button type="button" class="secondary" @click="emit('cancel')">关闭</button>
      </div>
    </section>
  </div>
</template>
