<script setup lang="ts">
import { AlertTriangle, ArrowLeft, Check, FileText, LoaderCircle, LockKeyhole, X } from 'lucide-vue-next'
import { ref } from 'vue'
import type {
  AppErrorInfo,
  CityMemoryItem,
  CityMemoryPreview,
  CityMemoryUpdatePreview,
  NewMemoryInput,
  VisitedCity,
} from '../types'

const props = defineProps<{
  city: VisitedCity
  mode: 'create' | 'edit'
  initialMemory: CityMemoryItem | null
  phase: 'editing' | 'preview' | 'saving' | 'success' | 'error'
  preview: CityMemoryPreview | CityMemoryUpdatePreview | null
  error: AppErrorInfo | null
}>()

const emit = defineEmits<{
  cancel: []
  preview: [input: NewMemoryInput]
  confirm: []
  edit: []
}>()

const dateInputFormatter = new Intl.DateTimeFormat('en-CA')
const today = dateInputFormatter.format(new Date())
const initialDate = props.initialMemory ? dateInputFormatter.format(new Date(props.initialMemory.occurred_at)) : today
const title = ref(props.initialMemory?.title ?? '')
const body = ref(props.initialMemory?.body ?? '')
const occurredDate = ref(initialDate)
const shared = ref(props.initialMemory?.visibility === 'shared')

const dateFormatter = new Intl.DateTimeFormat('zh-CN', {
  year: 'numeric',
  month: 'long',
  day: 'numeric',
})

function submitPreview() {
  emit('preview', {
    title: title.value.trim(),
    body: body.value.trim() || null,
    occurred_at: new Date(`${occurredDate.value}T12:00:00`).toISOString(),
    visibility: shared.value ? 'shared' : 'private',
  })
}

function formatDate(value: string): string {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '日期未知' : dateFormatter.format(date)
}
</script>

<template>
  <div class="dialog-backdrop memory-composer-backdrop" @click.self="emit('cancel')">
    <section class="memory-composer" role="dialog" aria-modal="true" aria-labelledby="memory-composer-title">
      <header>
        <div>
          <p class="eyebrow">CITY MEMORY · {{ city.adcode }}</p>
          <h2 id="memory-composer-title">{{ mode === 'edit' ? '修改' : '写给' }}{{ city.name_zh }}的记忆</h2>
        </div>
        <button type="button" title="关闭记忆编辑器" aria-label="关闭记忆编辑器" @click="emit('cancel')"><X :size="20" /></button>
      </header>

      <form v-if="phase === 'editing'" class="memory-editor-form" @submit.prevent="submitPreview">
        <label>
          <span>标题</span>
          <input v-model="title" required maxlength="160" placeholder="给这段记忆一个名字" />
        </label>
        <label>
          <span>发生日期</span>
          <input v-model="occurredDate" required type="date" />
        </label>
        <label>
          <span>正文</span>
          <textarea v-model="body" maxlength="5000" rows="7" placeholder="记下当时的天气、声音和心情……"></textarea>
        </label>
        <label class="memory-visibility-toggle">
          <input v-model="shared" type="checkbox" />
          <span><strong>{{ shared ? '允许分享' : '仅自己可见' }}</strong><small>以后发布旅行故事时仍会再次确认</small></span>
        </label>
        <div class="memory-composer-actions">
          <button type="button" class="secondary" @click="emit('cancel')">取消</button>
          <button type="submit" class="primary" :disabled="!title.trim()"><FileText :size="16" />{{ mode === 'edit' ? '预览修改' : '预览记忆' }}</button>
        </div>
      </form>

      <div v-else-if="phase === 'preview' && preview" class="memory-confirmation">
        <div class="memory-confirmation-meta">
          <span>{{ formatDate(preview.occurred_at) }}</span>
          <span><LockKeyhole :size="13" />{{ preview.visibility === 'private' ? '仅自己可见' : '允许分享' }}</span>
        </div>
        <h3>{{ preview.title }}</h3>
        <p v-if="preview.body">{{ preview.body }}</p>
        <p v-else class="memory-body-empty">这段记忆暂时没有正文。</p>
        <small>{{ preview.confirmation_notice }}</small>
        <div class="memory-composer-actions">
          <button type="button" class="secondary" @click="emit('edit')"><ArrowLeft :size="16" />继续修改</button>
          <button type="button" class="primary" @click="emit('confirm')"><Check :size="16" />{{ mode === 'edit' ? '确认更新' : '确认保存' }}</button>
        </div>
      </div>

      <div v-else-if="phase === 'saving'" class="memory-composer-state" aria-live="polite">
        <LoaderCircle class="spin" :size="30" />
        <strong>正在保存城市记忆</strong>
        <p>请稍候，不要重复提交。</p>
      </div>

      <div v-else-if="phase === 'success'" class="memory-composer-state success" aria-live="polite">
        <span><Check :size="28" /></span>
        <strong>{{ mode === 'edit' ? '记忆修改已经保存' : '记忆已经收进城市档案' }}</strong>
        <p>{{ mode === 'edit' ? '城市时间线已经更新。' : '地图统计与城市时间线已经更新。' }}</p>
        <button type="button" class="primary" @click="emit('cancel')">回到城市档案</button>
      </div>

      <div v-else-if="phase === 'error' && error" class="memory-composer-state error" role="alert">
        <span><AlertTriangle :size="26" /></span>
        <strong>{{ error.message }}</strong>
        <code>{{ error.code }}</code>
        <small v-if="error.requestId">请求编号：{{ error.requestId }}</small>
        <button type="button" class="secondary" @click="emit('edit')">返回编辑</button>
      </div>
    </section>
  </div>
</template>
