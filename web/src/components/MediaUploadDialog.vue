<script setup lang="ts">
import {
  AlertTriangle,
  Camera,
  Check,
  Film,
  FolderOpen,
  ImagePlus,
  LoaderCircle,
  LockKeyhole,
  RefreshCw,
  Upload,
  Video,
  X,
} from 'lucide-vue-next'
import { onBeforeUnmount, ref, watch } from 'vue'
import type {
  AppErrorInfo,
  CityMemoryItem,
  MediaUploadProgress,
  MediaUploadPreview,
  VisitedCity,
} from '../types'

const props = defineProps<{
  city: VisitedCity
  memory: CityMemoryItem
  phase: 'selecting' | 'preview' | 'uploading' | 'processing' | 'success' | 'error'
  file: File | null
  preview: MediaUploadPreview | null
  uploadProgress: MediaUploadProgress
  error: AppErrorInfo | null
}>()

const emit = defineEmits<{
  cancel: []
  preview: [file: File]
  confirm: []
  cancelUpload: []
  retry: []
  edit: []
}>()

const photoInput = ref<HTMLInputElement | null>(null)
const videoInput = ref<HTMLInputElement | null>(null)
const libraryInput = ref<HTMLInputElement | null>(null)
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

function chooseSource(input: HTMLInputElement | null) {
  if (!input) return
  input.value = ''
  input.click()
}

function onFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  selectedFile.value = input.files?.[0] ?? null
}

function submitPreview() {
  if (selectedFile.value) emit('preview', selectedFile.value)
}

function formatBytes(bytes: number): string {
  if (bytes <= 0) return '0 KB'
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
          ref="photoInput"
          class="visually-hidden"
          type="file"
          accept="image/jpeg,image/png,image/webp"
          capture="environment"
          @change="onFileChange"
        />
        <input
          ref="videoInput"
          class="visually-hidden"
          type="file"
          accept="video/mp4,video/quicktime,video/webm"
          capture="environment"
          @change="onFileChange"
        />
        <input
          ref="libraryInput"
          class="visually-hidden"
          type="file"
          accept="image/jpeg,image/png,image/webp,video/mp4,video/quicktime,video/webm"
          @change="onFileChange"
        />
        <div class="media-source-grid" aria-label="媒体来源">
          <button type="button" @click="chooseSource(photoInput)"><Camera :size="24" /><strong>拍照</strong></button>
          <button type="button" @click="chooseSource(videoInput)"><Video :size="24" /><strong>录像</strong></button>
          <button type="button" @click="chooseSource(libraryInput)"><FolderOpen :size="24" /><strong>相册或文件</strong></button>
        </div>
        <div v-if="selectedFile" class="media-selected-file">
          <ImagePlus :size="22" />
          <span><strong>{{ selectedFile.name }}</strong><small>{{ formatBytes(selectedFile.size) }}</small></span>
        </div>
        <p v-else class="media-format-note">JPEG / PNG / WebP / MP4 / MOV / WebM</p>
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
        <strong>正在上传私有文件</strong>
        <div class="media-upload-progress">
          <div
            role="progressbar"
            aria-label="媒体上传进度"
            :aria-valuenow="uploadProgress.percent"
            aria-valuemin="0"
            aria-valuemax="100"
          ><span :style="{ width: `${uploadProgress.percent}%` }"></span></div>
          <p><strong>{{ uploadProgress.percent }}%</strong><span>{{ formatBytes(uploadProgress.loaded) }} / {{ formatBytes(uploadProgress.total) }}</span></p>
        </div>
        <p>上传完成后会校验格式并移除照片 EXIF 信息。</p>
        <button type="button" class="media-upload-cancel" @click="emit('cancelUpload')"><X :size="15" />取消上传</button>
      </div>

      <div v-else-if="phase === 'processing'" class="media-upload-state" aria-live="polite">
        <LoaderCircle class="spin" :size="31" />
        <strong>正在安全扫描并生成预览</strong>
        <p>图片缩略图或视频封面完成后，文件才会加入城市记忆。</p>
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
