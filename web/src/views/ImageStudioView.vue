<script setup lang="ts">
import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  Camera,
  ShieldCheck,
  Download,
  Heart,
  Image as ImageIcon,
  LoaderCircle,
  Palette,
  RefreshCw,
  Trash2,
} from 'lucide-vue-next'
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import {
  ApiClientError,
  confirmImageJobDelete,
  getImageJobs,
  getImageStyles,
  previewImageJobDelete,
  setImageJobFavorite,
} from '../api'
import ImageCompareSlider from '../components/ImageCompareSlider.vue'
import UiButton from '../components/UiButton.vue'
import UiStatus from '../components/UiStatus.vue'
import ImageJobDeleteDialog from '../components/ImageJobDeleteDialog.vue'
import type {
  AppErrorInfo,
  ImageJob,
  ImageJobDeletePreview,
  ImageStyleCatalog,
} from '../types'

const emit = defineEmits<{ back: []; memories: [] }>()

const jobs = ref<ImageJob[]>([])
const selectedId = ref<string | null>(null)
const catalog = ref<ImageStyleCatalog | null>(null)
const favoriteOnly = ref(false)
const loading = ref(true)
const error = ref<AppErrorInfo | null>(null)
const favoriteBusyId = ref<string | null>(null)
const deleteTarget = ref<ImageJob | null>(null)
const deletePreview = ref<ImageJobDeletePreview | null>(null)
const deletePhase = ref<'loading' | 'ready' | 'deleting' | 'error'>('loading')
const deleteError = ref<AppErrorInfo | null>(null)
const deleteRequestId = ref('')
let pollTimer: number | undefined
let loadVersion = 0
let disposed = false
const catalogError = ref<AppErrorInfo | null>(null)

const selectedJob = computed(
  () =>
    jobs.value.find((job) => job.id === selectedId.value) ??
    jobs.value[0] ??
    null,
)
const styleName = computed(() => {
  const job = selectedJob.value
  return (
    catalog.value?.styles.find((style) => style.id === job?.style_id)?.name ??
    job?.style_id ??
    ''
  )
})

const statusText: Record<ImageJob['status'], string> = {
  queued: '等待处理',
  running: '正在生成',
  succeeded: '生成完成',
  failed: '生成失败',
}
const captionLayoutLabels = {
  archive_band: '档案横带',
  postcard_corner: '明信片角标',
  vertical_stamp: '竖排印章',
} as const
const captionPaletteLabels = {
  coral: '珊瑚红',
  forest: '森林绿',
  ink: '墨黑',
} as const
const captionFontLabels = { sans: '现代黑体', serif: '旅行宋体' } as const

function asError(value: unknown): AppErrorInfo {
  if (value instanceof ApiClientError) return value
  return {
    code: 'IMAGE_STUDIO_UNKNOWN_ERROR',
    message: '视觉工作台遇到了未知错误。',
    details: {},
    retryable: true,
  }
}

function requestId() {
  return (
    globalThis.crypto?.randomUUID?.() ??
    `${Date.now()}-${Math.random().toString(16).slice(2)}`
  )
}

async function loadJobs(silent = false) {
  const version = ++loadVersion
  if (!silent) loading.value = true
  error.value = null
  const [history, styles] = await Promise.allSettled([
    getImageJobs('AuroraRovella', favoriteOnly.value),
    catalog.value ? Promise.resolve(catalog.value) : getImageStyles(),
  ])
  if (disposed || version !== loadVersion) return
  if (history.status === 'fulfilled') {
    jobs.value = history.value.items
    if (!jobs.value.some((job) => job.id === selectedId.value))
      selectedId.value = jobs.value[0]?.id ?? null
  } else error.value = asError(history.reason)
  if (styles.status === 'fulfilled') {
    catalog.value = styles.value
    catalogError.value = null
  } else catalogError.value = asError(styles.reason)
  loading.value = false
  schedulePoll()
}

function schedulePoll() {
  if (pollTimer) window.clearTimeout(pollTimer)
  if (
    !disposed &&
    jobs.value.some(
      (job) => job.status === 'queued' || job.status === 'running',
    )
  ) {
    pollTimer = window.setTimeout(() => void loadJobs(true), 2500)
  }
}

async function showAllJobs() {
  favoriteOnly.value = false
  await loadJobs()
}

async function toggleFavorite(job: ImageJob) {
  favoriteBusyId.value = job.id
  error.value = null
  try {
    const updated = await setImageJobFavorite(job.id, !job.is_favorite)
    if (favoriteOnly.value && !updated.is_favorite) {
      jobs.value = jobs.value.filter((item) => item.id !== updated.id)
      selectedId.value = jobs.value[0]?.id ?? null
    } else {
      jobs.value = jobs.value.map((item) =>
        item.id === updated.id ? updated : item,
      )
    }
  } catch (value) {
    error.value = asError(value)
  } finally {
    favoriteBusyId.value = null
  }
}

async function openDelete(job: ImageJob) {
  deleteTarget.value = job
  deletePreview.value = null
  deleteError.value = null
  deletePhase.value = 'loading'
  deleteRequestId.value = requestId()
  try {
    deletePreview.value = await previewImageJobDelete(job.id, {
      username: 'AuroraRovella',
      client_request_id: deleteRequestId.value,
    })
    deletePhase.value = 'ready'
  } catch (value) {
    deleteError.value = asError(value)
    deletePhase.value = 'error'
  }
}

async function confirmDelete() {
  if (!deleteTarget.value) return
  deletePhase.value = 'deleting'
  try {
    const deletedId = deleteTarget.value.id
    await confirmImageJobDelete(deletedId, {
      username: 'AuroraRovella',
      client_request_id: deleteRequestId.value,
    })
    jobs.value = jobs.value.filter((job) => job.id !== deletedId)
    selectedId.value = jobs.value[0]?.id ?? null
    closeDelete()
  } catch (value) {
    deleteError.value = asError(value)
    deletePhase.value = 'error'
  }
}

function closeDelete() {
  deleteTarget.value = null
  deletePreview.value = null
  deleteError.value = null
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat('zh-CN', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}

onMounted(() => void loadJobs())
onBeforeUnmount(() => {
  disposed = true
  loadVersion += 1
  if (pollTimer) window.clearTimeout(pollTimer)
})
</script>

<template>
  <main class="image-studio-view" aria-label="旅行影像工作台">
    <div class="studio-scroll">
      <div class="studio-page">
        <header class="studio-header">
          <div>
            <div class="studio-breadcrumb">
              <button
                type="button"
                aria-label="返回旅行地图"
                @click="emit('back')"
              >
                <ArrowLeft :size="16" />旅程</button
              ><span>/</span><span>旅行影像工作台</span>
            </div>

            <h1>影像创作<span class="studio-title-dot">。</span></h1>
            <p>从自己的照片出发，原片与每一次创作，都有来处。</p>
          </div>
          <UiButton variant="primary"
            v-if="jobs.length || loading || error || favoriteOnly"
            class="studio-pick-source"
            type="button"
            @click="emit('memories')"
          >
            <Camera :size="17" />从旅行记忆选照片<ArrowRight :size="16" />
          </UiButton>
        </header>
        <div v-if="catalog && !catalog.available" class="studio-availability" role="status"><UiStatus tone="warning">影像生成服务暂未连接</UiStatus><span>已有作品仍可查看。</span></div>
        <p v-else-if="catalogError" class="studio-inline-error" role="status">
          风格服务状态暂时无法读取。已有作品仍可查看。{{ catalogError.message }}
        </p>
        <div class="studio-filter-bar">
          <div>
            <h2>我的作品</h2>
            <span
              >{{ favoriteOnly ? '当前收藏' : '当前记录' }} ·
              {{ jobs.length }} 项</span
            >
          </div>
          <div>
            <label
              ><input
                v-model="favoriteOnly"
                type="checkbox"
                @change="loadJobs()"
              /><Heart
                :size="15"
                :fill="favoriteOnly ? 'currentColor' : 'none'"
              />只看收藏</label
            ><button
              type="button"
              aria-label="刷新生成历史"
              :disabled="loading"
              @click="loadJobs()"
            >
              <RefreshCw :size="17" :class="{ spin: loading }" />
            </button>
          </div>
        </div>
        <section
          v-if="loading && !jobs.length"
          class="studio-page-state"
          aria-live="polite"
        >
          <LoaderCircle class="spin" :size="31" /><strong
            >正在整理旅行影像</strong
          >
        </section>
        <section
          v-else-if="error && !jobs.length"
          class="studio-page-state error"
          role="alert"
        >
          <AlertTriangle :size="31" /><strong>{{ error.message }}</strong
          ><code>{{ error.code }}</code
          ><button type="button" @click="loadJobs()">重新加载</button>
        </section>
        <section
          v-else-if="!jobs.length && favoriteOnly"
          class="studio-page-state empty"
        >
          <Heart :size="30" /><strong>还没有收藏的作品</strong>
          <p>回到全部作品，找到想留下的一张。</p>
          <button
            type="button"
              @click="showAllJobs"
          >
            查看全部作品
          </button>
        </section>
        <section v-else-if="!jobs.length" class="studio-start" aria-label="开始照片创作">
          <span class="studio-film-edge" aria-hidden="true"></span>
          <figure class="studio-inspiration">
            <img src="/discover/xiamen-coast.webp" alt="厦门海岸创作灵感摄影，非个人作品或生成结果" />
            <figcaption><span class="studio-photo-label">创作灵感参考 · 非个人作品</span><a href="/discover/credits.html" target="_blank" rel="noopener">摄影来源 ↗</a></figcaption>
          </figure>
          <div class="studio-start-copy">
            <h2>选一张照片，<br />留住旅途的光。</h2>
            <p>从城市记忆中选择自己的照片，原片与创作分别保留。</p>
            <UiButton variant="primary" class="studio-pick-source" type="button" @click="emit('memories')">
              <Camera :size="17" />从旅行记忆选照片<ArrowRight :size="16" />
            </UiButton>
            <details class="ui-disclosure"><summary>如何创作</summary><ol><li>打开一段记忆，添加自己的照片。</li><li>选择风格，核对处理范围后确认生成。</li><li>成功后可对比原片、收藏或下载作品。</li></ol><p>当前生成服务尚未连接时，不会创建成功作品。</p></details>
          </div>
        </section>
        <div v-else class="studio-workspace">
          <aside class="studio-history" aria-label="生成历史">
            <button
              v-for="job in jobs"
              :key="job.id"
              type="button"
              :class="{ active: selectedJob?.id === job.id }"
              :aria-pressed="selectedJob?.id === job.id"
              @click="selectedId = job.id"
            >
              <span class="studio-history-thumb"
                ><img
                  v-if="
                    job.output_url || job.source_thumbnail_url || job.source_url
                  "
                  :src="
                    job.output_url ||
                    job.source_thumbnail_url ||
                    job.source_url ||
                    ''
                  "
                  :alt="job.source_filename" /><ImageIcon v-else :size="20" /><i
                  :class="`status-${job.status}`"
                ></i></span
              ><span class="studio-history-copy"
                ><strong>{{ job.city_name }}</strong
                ><small>{{ job.memory_title }}</small
                ><time>{{ formatDate(job.created_at) }}</time
                ><small>{{ statusText[job.status] }}</small></span
              ><Heart v-if="job.is_favorite" :size="13" fill="currentColor" />
            </button>
          </aside>
          <section v-if="selectedJob" class="studio-canvas">
            <ImageCompareSlider
              v-if="
                selectedJob.status === 'succeeded' &&
                selectedJob.source_url &&
                selectedJob.output_url
              "
              :source-url="selectedJob.source_url"
              :result-url="selectedJob.output_url"
              :source-alt="`原图 ${selectedJob.source_filename}`"
              :result-alt="`${styleName} 生成图`"
            />
            <div v-else class="studio-canvas-state" :class="selectedJob.status">
              <LoaderCircle
                v-if="
                  selectedJob.status === 'queued' ||
                  selectedJob.status === 'running'
                "
                class="spin"
                :size="32"
              /><AlertTriangle
                v-else-if="selectedJob.status === 'failed'"
                :size="32"
              /><ImageIcon v-else :size="32" /><strong>{{
                statusText[selectedJob.status]
              }}</strong>
              <p v-if="selectedJob.failure_message">
                {{ selectedJob.failure_message }}
              </p>
              <p v-else>以实际任务状态为准，可以稍后回来查看。</p>
            </div>
          </section>
          <aside v-if="selectedJob" class="studio-inspector">
            <div class="studio-inspector-heading">
              <div>
                <span :class="`studio-status status-${selectedJob.status}`">{{
                  statusText[selectedJob.status]
                }}</span>
                <h2>{{ styleName }}</h2>
              </div>
              <button
                type="button"
                :title="selectedJob.is_favorite ? '取消收藏' : '收藏作品'"
                :aria-label="selectedJob.is_favorite ? '取消收藏' : '收藏作品'"
                :disabled="favoriteBusyId === selectedJob.id"
                @click="toggleFavorite(selectedJob)"
              >
                <Heart
                  :size="19"
                  :fill="selectedJob.is_favorite ? 'currentColor' : 'none'"
                />
              </button>
            </div>
            <section class="studio-source-card">
              <span><Camera :size="15" />原始照片</span
              ><strong>{{ selectedJob.source_filename }}</strong>
              <p>
                {{ selectedJob.city_name }} · {{ selectedJob.memory_title }}
              </p>
              <a
                v-if="selectedJob.source_url"
                :href="selectedJob.source_url"
                target="_blank"
                rel="noopener"
                >查看原片<ArrowRight :size="13"
              /></a>
            </section>
            <dl class="studio-meta">
              <div>
                <dt>城市</dt>
                <dd>{{ selectedJob.city_name }}</dd>
              </div>
              <div>
                <dt>旅行记忆</dt>
                <dd>{{ selectedJob.memory_title }}</dd>
              </div>
              <div>
                <dt>生成时间</dt>
                <dd>{{ formatDate(selectedJob.created_at) }}</dd>
              </div>
              <div v-if="selectedJob.output_width">
                <dt>尺寸</dt>
                <dd>
                  {{ selectedJob.output_width }} ×
                  {{ selectedJob.output_height }}
                </dd>
              </div>
              <div>
                <dt>原图保真</dt>
                <dd>
                  {{
                    selectedJob.preservation_level === 'high'
                      ? '高保真'
                      : '平衡'
                  }}
                </dd>
              </div>
            </dl>
            <details class="studio-provenance">
              <summary>创作详情与来源</summary>
              <dl class="studio-meta">
                <div>
                  <dt>Recipe</dt>
                  <dd>
                    {{ selectedJob.recipe.version }} ·
                    {{ selectedJob.recipe.aspect_ratio }}
                  </dd>
                </div>
                <div v-if="selectedJob.model_names.length">
                  <dt>模型</dt>
                  <dd>{{ selectedJob.model_names.join('、') }}</dd>
                </div>
                <div v-if="selectedJob.caption">
                  <dt>旅行印记</dt>
                  <dd>
                    {{ selectedJob.caption.title }} ·
                    {{ selectedJob.caption.location }} ·
                    {{ selectedJob.caption.date }} ·
                    {{ captionLayoutLabels[selectedJob.caption.layout] }} ·
                    {{ captionPaletteLabels[selectedJob.caption.palette] }} ·
                    {{ captionFontLabels[selectedJob.caption.font_style] }}
                  </dd>
                </div>
                <div v-if="selectedJob.companion">
                  <dt>小曦合照</dt>
                  <dd>
                    {{
                      selectedJob.companion.position === 'left'
                        ? '左侧'
                        : '右侧'
                    }}
                    · {{ selectedJob.companion.scale }}
                  </dd>
                </div>
              </dl>
              <section class="studio-recipe">
                <span>创作配方</span>
                <p>{{ selectedJob.recipe.layout }}</p>
                <small
                  >{{ selectedJob.recipe.focal_element }} ·
                  {{ selectedJob.recipe.texture }}</small
                >
              </section>
              <a
                v-if="selectedJob.style_source"
                class="studio-source-credit"
                :href="selectedJob.style_source.url"
                target="_blank"
                rel="noreferrer"
                >{{ selectedJob.style_source.name }}
                {{ selectedJob.style_source.version }} ·
                {{ selectedJob.style_source.license }}</a
              >
              <p v-if="selectedJob.companion" class="studio-disclosure">
                {{ selectedJob.companion.disclosure }}
              </p>
              <section class="studio-prompt">
                <span>生成提示词</span>
                <p>{{ selectedJob.prompt }}</p>
              </section>
              <section
                v-if="selectedJob.negative_prompt"
                class="studio-prompt negative"
              >
                <span>避免内容</span>
                <p>{{ selectedJob.negative_prompt }}</p>
              </section>
            </details>
            <p v-if="error" class="studio-inline-error" role="alert">
              <AlertTriangle :size="14" />{{ error.message }}（{{
                error.code
              }}）
            </p>
            <footer class="studio-actions">
              <a
                v-if="
                  selectedJob.download_url && selectedJob.status === 'succeeded'
                "
                :href="selectedJob.download_url"
                ><Download :size="16" />下载作品</a
              ><button
                type="button"
                class="delete"
                :disabled="selectedJob.status === 'running'"
                @click="openDelete(selectedJob)"
              >
                <Trash2 :size="16" />删除作品
              </button>
            </footer>
          </aside>
        </div>
        <details
          v-if="catalog?.styles.length && !jobs.length && !favoriteOnly"
          class="studio-style-library"
          aria-label="可用风格目录"
        ><summary>浏览风格目录</summary>
          <div>

            <h2>先找到，喜欢的表达。</h2>
            <p>以下来自当前风格目录；选定原照片后可在创作窗口使用。</p>
          </div>
          <div class="studio-style-grid">
            <article v-for="style in catalog.styles" :key="style.id">
              <span :style="{ '--style-color': style.swatch }"
                ><Palette :size="23"
              /></span>
              <h3>{{ style.name }}</h3>
              <p>{{ style.description }}</p>
            </article>
          </div>
        </details>
        <p class="studio-footer-note">
          <ShieldCheck
            :size="14"
          />原照片与创作结果分别保存；删除作品须再次确认。
        </p>
      </div>
    </div>
    <ImageJobDeleteDialog
      v-if="deleteTarget"
      :phase="deletePhase"
      :preview="deletePreview"
      :error="deleteError"
      @cancel="closeDelete"
      @confirm="confirmDelete"
    />
  </main>
</template>
