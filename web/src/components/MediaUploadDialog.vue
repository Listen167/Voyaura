<script setup lang="ts">
import {
  AlertTriangle,
  Camera,
  Check,
  Film,
  ImagePlus,
  LoaderCircle,
  LockKeyhole,
  RefreshCw,
  Upload,
  X,
} from 'lucide-vue-next'
import { onBeforeUnmount, ref, watch } from 'vue'
import type {
  AppErrorInfo,
  CityMemoryItem,
  MediaUploadPreview,
  VisitedCity,
} from '../types'

const props = defineProps<{
  city: VisitedCity
  memory: CityMemoryItem
  phase: 'selecting' | 'preview' | 'uploading' | 'success' | 'error'
  file: File | null
  preview: MediaUploadPreview | null
  error: AppErrorInfo | null
}>()

const emit = defineEmits<{
  cancel: []
  preview: [file: File]
  confirm: []
  retry: []
  edit: []
}>()

const fileInput = ref<HTMLInputElement | null>(null)
const selectedFile = ref<File | null>(props.file)
const objectUrl = ref<string | null>(null)

function releaseObjectUrl() {
  if (objectUrl.value) URL.revokeObjectURL(objectUrl.value)
  objectUrl.value = null
}

watch(
  () => props.file,
  (file) => {
    selectedFile.value = file
    releaseObjectUrl()
    if (file) objectUrl.value = URL.createObjectURL(file)
  },
  { immediate: true },
)

onBeforeUnmount(releaseObjectUrl)

function chooseFile() {
  fileInput.value?.click()
}

function onFileChange(event: Event) {
  selectedFile.value = (event.target as HTMLInputElement).files?.[0] ?? null
}

function submitPreview() {
  if (selectedFile.value) emit('preview', selectedFile.value)
}

function formatBytes(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  return `${Math.max(1, Math.round(bytes / 1024))} KB`
}
</script>

<template>
  <div class="dialog-backdrop media-upload-backdrop" @click.self="emit('cancel')">
    <section class="media-upload-dialog" role="dialog" aria-modal="true" aria-labelledby="media-upload-title">
      <header>
        <div>
          <p class="eyebrow">PRIVATE MEDIA · {{ city.adcode }}</p>
          <h2 id="media-upload-title">添加照片或 Vlog</h2>
        </div>
        <button type="button" title="关闭媒体上传" aria-label="关闭媒体上传" @click="emit('cancel')"><X :size="20" /></button>
      </header>

      <form v-if="phase === 'selecting'" class="media-file-picker" @submit.prevent="submitPreview">
        <input
          ref="fileInput"
          class="visually-hidden"
          type="file"
          accept="image/jpeg,image/png,image/webp,video/mp4,video/quicktime,video/webm"
          @change="onFileChange"
        />
        <button class="media-pick-button" type="button" @click="chooseFile">
          <ImagePlus :size="28" />
          <strong>{{ selectedFile ? selectedFile.name : '选择照片或视频' }}</strong>
          <small>{{ selectedFile ? formatBytes(selectedFile.size) : 'JPEG / PNG / WebP / MP4 / MOV / WebM' }}</small>
        </button>
        <div class="media-memory-context">
          <span>{{ memory.title }}</span>
          <small>{{ city.name_zh }} · 文件默认仅自己可见</small>
        </div>
        <div class="memory-composer-actions">
          <button type="button" class="secondary" @click="emit('cancel')">取消</button>
          <button type="submit" class="primary" :disabled="!selectedFile"><Camera :size="16" />预览上传</button>
        </div>
      </form>

      <div v-else-if="phase === 'preview' && preview" class="media-upload-preview">
        <div class="media-local-preview">
          <img v-if="preview.kind === 'photo' && objectUrl" :src="objectUrl" alt="待上传照片预览" />
          <video v-else-if="objectUrl" :src="objectUrl" controls preload="metadata"></video>
          <Camera v-else-if="preview.kind === 'photo'" :size="34" />
          <Film v-else :size="34" />
        </div>
        <div class="media-upload-summary">
          <strong>{{ preview.filename }}</strong>
          <span>{{ formatBytes(preview.byte_size) }} · {{ preview.kind === 'photo' ? '照片' : 'Vlog' }}</span>
          <p><LockKeyhole :size="14" />{{ preview.confirmation_notice }}</p>
        </div>
        <div class="memory-composer-actions">
          <button type="button" class="secondary" @click="emit('edit')">重新选择</button>
          <button type="button" class="primary" @click="emit('confirm')"><Upload :size="16" />确认上传</button>
        </div>
      </div>

      <div v-else-if="phase === 'uploading'" class="media-upload-state" aria-live="polite">
        <LoaderCircle class="spin" :size="31" />
        <strong>正在安全上传</strong>
        <p>完成后将校验文件并移除照片 EXIF 信息。</p>
      </div>

      <div v-else-if="phase === 'success'" class="media-upload-state success" aria-live="polite">
        <span><Check :size="28" /></span>
        <strong>媒体已经加入城市记忆</strong>
        <p>原文件保持私有，城市统计已经更新。</p>
        <button type="button" class="primary" @click="emit('cancel')">回到城市档案</button>
      </div>

      <div v-else-if="phase === 'error' && error" class="media-upload-state error" role="alert">
        <span><AlertTriangle :size="27" /></span>
        <strong>{{ error.message }}</strong>
        <code>{{ error.code }}</code>
        <small v-if="error.requestId">请求编号：{{ error.requestId }}</small>
        <div class="media-error-actions">
          <button type="button" class="secondary" @click="emit('edit')">重新选择</button>
          <button v-if="error.retryable" type="button" class="primary" @click="emit('retry')"><RefreshCw :size="15" />重试</button>
        </div>
      </div>
    </section>
  </div>
</template>
