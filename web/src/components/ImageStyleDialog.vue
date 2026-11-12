<script setup lang="ts">
import {
  AlertTriangle,
  Check,
  Image as ImageIcon,
  LoaderCircle,
  LockKeyhole,
  Sparkles,
  WandSparkles,
  X,
} from 'lucide-vue-next'
import { ref, watch } from 'vue'
import type {
  AppErrorInfo,
  CityMemoryItem,
  ImageJob,
  ImageJobPreview,
  ImageCaptionFontStyle,
  ImageCaptionLayout,
  ImageCaptionPalette,
  ImagePreservationLevel,
  ImageStyleCatalog,
  MemoryMediaAsset,
  VisitedCity,
} from '../types'
import ImageCompareSlider from './ImageCompareSlider.vue'

const props = defineProps<{
  city: VisitedCity
  memory: CityMemoryItem
  asset: MemoryMediaAsset
  catalog: ImageStyleCatalog | null
  phase: 'loading' | 'editing' | 'preview' | 'creating' | 'processing' | 'success' | 'error'
  preview: ImageJobPreview | null
  job: ImageJob | null
  error: AppErrorInfo | null
}>()

const emit = defineEmits<{
  close: []
  preview: [draft: {
    style_id: string
    prompt: string
    negative_prompt: string | null
    preservation_level: ImagePreservationLevel
    caption_mode: 'none' | 'travel_stamp'
    caption_layout: ImageCaptionLayout
    caption_palette: ImageCaptionPalette
    caption_font_style: ImageCaptionFontStyle
    companion_enabled: boolean
    companion_position: 'left' | 'right'
    companion_scale: 'small' | 'medium' | 'large'
  }]
  confirm: []
  edit: []
}>()

const styleId = ref('')
const prompt = ref('')
const negativePrompt = ref('')
const preservationLevel = ref<ImagePreservationLevel>('balanced')
const captionEnabled = ref(false)
const captionLayout = ref<ImageCaptionLayout>('archive_band')
const captionPalette = ref<ImageCaptionPalette>('coral')
const captionFontStyle = ref<ImageCaptionFontStyle>('sans')
const companionEnabled = ref(false)
const companionPosition = ref<'left' | 'right'>('right')
const companionScale = ref<'small' | 'medium' | 'large'>('medium')

const captionLayoutLabels: Record<ImageCaptionLayout, string> = {
  archive_band: '档案横带',
  postcard_corner: '明信片角标',
  vertical_stamp: '竖排印章',
}
const captionPaletteLabels: Record<ImageCaptionPalette, string> = {
  coral: '珊瑚红',
  forest: '森林绿',
  ink: '墨黑',
}
const captionPaletteColors: Record<ImageCaptionPalette, string> = {
  coral: '#e54d34',
  forest: '#3f6951',
  ink: '#272b28',
}

watch(
  () => props.catalog,
  (catalog) => {
    if (catalog?.styles.length && !catalog.styles.some((style) => style.id === styleId.value)) {
      styleId.value = catalog.styles[0].id
    }
  },
  { immediate: true },
)

watch(styleId, (id) => {
  const style = props.catalog?.styles.find((candidate) => candidate.id === id)
  if (style) preservationLevel.value = style.recipe.default_preservation
})

function submitPreview() {
  if (!styleId.value) return
  emit('preview', {
    style_id: styleId.value,
    prompt: prompt.value.trim(),
    negative_prompt: negativePrompt.value.trim() || null,
    preservation_level: preservationLevel.value,
    caption_mode: captionEnabled.value ? 'travel_stamp' : 'none',
    caption_layout: captionLayout.value,
    caption_palette: captionPalette.value,
    caption_font_style: captionFontStyle.value,
    companion_enabled: companionEnabled.value,
    companion_position: companionPosition.value,
    companion_scale: companionScale.value,
  })
}
</script>

<template>
  <div class="dialog-backdrop image-style-backdrop" role="presentation" @click.self="emit('close')">
    <section class="image-style-dialog" role="dialog" aria-modal="true" aria-labelledby="image-style-title">
      <header>
        <div><p class="eyebrow">PRIVATE VISUAL LAB</p><h2 id="image-style-title">照片风格创作</h2></div>
        <button type="button" title="关闭风格创作" aria-label="关闭风格创作" @click="emit('close')"><X :size="20" /></button>
      </header>

      <div v-if="phase === 'loading'" class="image-style-state" aria-live="polite">
        <LoaderCircle class="spin" :size="30" /><strong>正在读取风格配置</strong>
      </div>

      <form v-else-if="phase === 'editing' && catalog" class="image-style-editor" @submit.prevent="submitPreview">
        <section class="style-source-strip">
          <img v-if="asset.thumbnail_url" :src="asset.thumbnail_url" :alt="asset.original_filename" />
          <span v-else><ImageIcon :size="24" /></span>
          <div><strong>{{ asset.original_filename }}</strong><small>{{ city.name_zh }} · {{ memory.title }}</small></div>
          <LockKeyhole :size="15" />
        </section>

        <p class="provider-status" :class="{ unavailable: !catalog.available }">
          <Check v-if="catalog.available" :size="15" /><AlertTriangle v-else :size="15" />
          <span>{{ catalog.available ? `${catalog.provider} 已连接` : '图片 Provider 尚未配置' }}</span>
        </p>

        <fieldset class="style-options">
          <legend>选择风格</legend>
          <label v-for="style in catalog.styles" :key="style.id" :class="{ selected: styleId === style.id }">
            <input v-model="styleId" type="radio" name="image-style" :value="style.id" />
            <span class="style-swatch" :style="{ backgroundColor: style.swatch }"></span>
            <span><strong>{{ style.name }}</strong><small>{{ style.description }}</small><em v-if="style.source">{{ style.source.name }} · {{ style.source.license }}</em></span>
          </label>
        </fieldset>

        <fieldset class="style-preservation">
          <legend>原图保真</legend>
          <label :class="{ selected: preservationLevel === 'balanced' }"><input v-model="preservationLevel" type="radio" value="balanced" /><span>平衡</span></label>
          <label :class="{ selected: preservationLevel === 'high' }"><input v-model="preservationLevel" type="radio" value="high" /><span>高保真</span></label>
        </fieldset>

        <label class="style-caption-toggle">
          <input v-model="captionEnabled" type="checkbox" />
          <span><strong>旅行档案印记</strong><small>{{ memory.title }} · {{ city.name_zh }} · {{ memory.occurred_at.slice(0, 10) }}</small></span>
        </label>

        <section v-if="captionEnabled" class="style-caption-editor">
          <fieldset>
            <legend>版式</legend>
            <label v-for="(label, value) in captionLayoutLabels" :key="value" :class="{ selected: captionLayout === value }">
              <input v-model="captionLayout" type="radio" name="caption-layout" :value="value" />{{ label }}
            </label>
          </fieldset>
          <fieldset>
            <legend>颜色</legend>
            <label v-for="(label, value) in captionPaletteLabels" :key="value" :class="{ selected: captionPalette === value }">
              <input v-model="captionPalette" type="radio" name="caption-palette" :value="value" />
              <span class="caption-palette-swatch" :style="{ backgroundColor: captionPaletteColors[value] }"></span>{{ label }}
            </label>
          </fieldset>
          <fieldset>
            <legend>字体</legend>
            <label :class="{ selected: captionFontStyle === 'sans' }"><input v-model="captionFontStyle" type="radio" name="caption-font" value="sans" />现代黑体</label>
            <label :class="{ selected: captionFontStyle === 'serif' }"><input v-model="captionFontStyle" type="radio" name="caption-font" value="serif" />旅行宋体</label>
          </fieldset>
        </section>

        <section class="style-companion-editor" :class="{ unavailable: !catalog.companion.available }">
          <label class="style-caption-toggle">
            <input v-model="companionEnabled" type="checkbox" :disabled="!catalog.companion.available" />
            <span><strong>和小曦一起入镜</strong><small>{{ catalog.companion.available ? `素材版本 ${catalog.companion.asset_version}` : '等待配置经授权的透明 PNG 素材' }}</small></span>
          </label>
          <div v-if="companionEnabled" class="style-companion-options">
            <fieldset><legend>站位</legend><label><input v-model="companionPosition" type="radio" value="left" />左侧</label><label><input v-model="companionPosition" type="radio" value="right" />右侧</label></fieldset>
            <fieldset><legend>尺寸</legend><label><input v-model="companionScale" type="radio" value="small" />小</label><label><input v-model="companionScale" type="radio" value="medium" />中</label><label><input v-model="companionScale" type="radio" value="large" />大</label></fieldset>
          </div>
        </section>

        <label class="style-prompt-field">
          <span>画面补充</span>
          <textarea v-model="prompt" maxlength="1200" rows="3" placeholder="例如：保留珠江塔轮廓，傍晚暖光"></textarea>
        </label>
        <label class="style-prompt-field">
          <span>避免内容</span>
          <textarea v-model="negativePrompt" maxlength="1200" rows="2" placeholder="例如：模糊、变形文字、过度磨皮"></textarea>
        </label>

        <footer class="style-actions">
          <button type="button" class="secondary" @click="emit('close')">取消</button>
          <button type="submit" class="primary" :disabled="!styleId"><WandSparkles :size="16" />预览任务</button>
        </footer>
      </form>

      <div v-else-if="phase === 'preview' && preview" class="image-style-confirmation">
        <div class="style-preview-heading"><span :style="{ backgroundColor: preview.style.swatch }"></span><div><small>{{ preview.provider }}</small><strong>{{ preview.style.name }}</strong></div></div>
        <dl>
          <div><dt>照片</dt><dd>{{ preview.source_filename }}</dd></div>
          <div><dt>城市记忆</dt><dd>{{ preview.city_name }} · {{ preview.memory_title }}</dd></div>
          <div><dt>原图保真</dt><dd>{{ preview.preservation_level === 'high' ? '高保真' : '平衡' }}</dd></div>
          <div><dt>Recipe</dt><dd>{{ preview.recipe.version }} · {{ preview.recipe.aspect_ratio }} · {{ preview.recipe.layout }}</dd></div>
          <div v-if="preview.caption"><dt>旅行印记</dt><dd>{{ preview.caption.title }} · {{ preview.caption.location }} · {{ preview.caption.date }} · {{ captionLayoutLabels[preview.caption.layout] }} · {{ captionPaletteLabels[preview.caption.palette] }} · {{ preview.caption.font_style === 'serif' ? '旅行宋体' : '现代黑体' }}</dd></div>
          <div v-if="preview.companion"><dt>小曦合照</dt><dd>{{ preview.companion.position === 'left' ? '左侧' : '右侧' }} · {{ { small: '小', medium: '中', large: '大' }[preview.companion.scale] }} · {{ preview.companion.asset_version }}</dd></div>
          <div><dt>生成提示词</dt><dd>{{ preview.effective_prompt }}</dd></div>
          <div v-if="preview.negative_prompt"><dt>避免内容</dt><dd>{{ preview.negative_prompt }}</dd></div>
        </dl>
        <a v-if="preview.style.source" class="style-source-credit" :href="preview.style.source.url" target="_blank" rel="noreferrer">{{ preview.style.source.name }} {{ preview.style.source.version }} · {{ preview.style.source.license }}</a>
        <p><LockKeyhole :size="15" />{{ preview.confirmation_notice }}</p>
        <p v-if="!preview.provider_available" class="style-config-warning" role="alert"><AlertTriangle :size="15" />需要先完成 ComfyUI 环境配置。</p>
        <p v-if="preview.companion && !preview.companion_available" class="style-config-warning" role="alert"><AlertTriangle :size="15" />需要先配置经授权的小曦透明素材。</p>
        <footer class="style-actions">
          <button type="button" class="secondary" @click="emit('edit')">返回修改</button>
          <button type="button" class="primary" :disabled="!preview.provider_available || (!!preview.companion && !preview.companion_available)" @click="emit('confirm')"><Sparkles :size="16" />开始生成</button>
        </footer>
      </div>

      <div v-else-if="phase === 'creating' || phase === 'processing'" class="image-style-state" aria-live="polite">
        <LoaderCircle class="spin" :size="32" /><strong>{{ phase === 'creating' ? '正在创建私有任务' : 'ComfyUI 正在生成' }}</strong><p>可以保持此窗口打开查看结果</p>
      </div>

      <div v-else-if="phase === 'success' && job?.output_url" class="image-style-result">
        <ImageCompareSlider
          :source-url="asset.content_url || asset.thumbnail_url || ''"
          :result-url="job.output_url"
          :source-alt="`原图 ${asset.original_filename}`"
          result-alt="生成后的风格图片"
        />
        <p><Check :size="16" />私有 WebP 已生成 · {{ job.output_width }} × {{ job.output_height }}</p>
        <p v-if="job.caption" class="style-result-meta">已写入：{{ job.caption.title }} · {{ job.caption.location }} · {{ job.caption.date }} · {{ captionLayoutLabels[job.caption.layout] }} · {{ captionPaletteLabels[job.caption.palette] }}</p>
        <p v-if="job.companion" class="style-result-meta">{{ job.companion.disclosure }}</p>
        <p v-if="job.model_names.length" class="style-result-meta">模型：{{ job.model_names.join('、') }}</p>
        <footer class="style-actions"><button type="button" class="secondary" @click="emit('close')">完成</button><a class="primary" :href="job.download_url || job.output_url">下载作品</a></footer>
      </div>

      <div v-else-if="phase === 'error' && error" class="image-style-state error" role="alert">
        <AlertTriangle :size="30" /><strong>{{ error.message }}</strong><code>{{ error.code }}</code><small v-if="error.requestId">请求编号：{{ error.requestId }}</small>
        <button type="button" class="secondary" @click="emit('edit')">返回设置</button>
      </div>
    </section>
  </div>
</template>
