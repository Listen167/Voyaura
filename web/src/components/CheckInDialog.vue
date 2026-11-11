<script setup lang="ts">
import { AlertTriangle, Check, LoaderCircle, LocateFixed, MapPin, RotateCcw, Search, Wifi, X } from 'lucide-vue-next'
import { ref } from 'vue'
import type { AppErrorInfo, CheckInPreview, CityCandidate } from '../types'

defineProps<{
  phase: 'locating' | 'manual' | 'preview' | 'confirming' | 'success' | 'error'
  preview: CheckInPreview | null
  error: AppErrorInfo | null
  locationMode: 'device-high' | 'device-fallback' | 'ip'
  manualResults: CityCandidate[]
  manualBusy: boolean
  manualError: AppErrorInfo | null
}>()

const emit = defineEmits<{
  cancel: []
  confirm: []
  retry: []
  useIp: []
  openManual: []
  searchManual: [query: string]
  selectManual: [city: CityCandidate]
}>()

const manualQuery = ref('')

const sourceLabels = {
  device: '设备定位',
  ip: '网络城市建议',
  manual: '手动选城',
}
</script>

<template>
  <div class="dialog-backdrop" @click.self="emit('cancel')">
    <section class="check-in-dialog" role="dialog" aria-modal="true" aria-labelledby="check-in-title">
      <header>
        <div>
          <p class="eyebrow">CITY CHECK-IN</p>
          <h2 id="check-in-title">
            {{ phase === 'preview' ? '确认点亮城市' : phase === 'success' ? '城市已点亮' : phase === 'manual' ? '手动选择城市' : '定位城市' }}
          </h2>
        </div>
        <button type="button" title="关闭" aria-label="关闭定位" @click="emit('cancel')"><X :size="20" /></button>
      </header>

      <div v-if="phase === 'locating' || phase === 'confirming'" class="dialog-progress" aria-live="polite">
        <LoaderCircle class="spin" :size="30" />
        <strong>{{ phase === 'confirming' ? '正在保存这次抵达' : locationMode === 'ip' ? '正在根据网络判断城市' : locationMode === 'device-fallback' ? '正在尝试普通精度定位' : '正在尝试高精度定位' }}</strong>
        <p>{{ phase === 'locating' ? '结果只用于识别城市，不会保存精确坐标。' : '请稍候，不要重复提交。' }}</p>
      </div>

      <div v-else-if="phase === 'manual'" class="manual-city-search">
        <form @submit.prevent="emit('searchManual', manualQuery)">
          <Search :size="17" />
          <input v-model="manualQuery" aria-label="输入城市名称" placeholder="输入完整城市名，例如：广州市" />
          <button type="submit" :disabled="manualBusy || manualQuery.trim().length < 2">
            <LoaderCircle v-if="manualBusy" class="spin" :size="16" />
            <span v-else>搜索</span>
          </button>
        </form>
        <div v-if="manualError" class="manual-city-error" role="status">
          <AlertTriangle :size="16" />
          <span>{{ manualError.message }}</span>
          <code>{{ manualError.code }}</code>
        </div>
        <div v-if="manualResults.length" class="manual-city-results" aria-label="城市搜索结果">
          <button v-for="city in manualResults" :key="city.adcode" type="button" @click="emit('selectManual', city)">
            <MapPin :size="17" />
            <span><strong>{{ city.city_name }}</strong><small>{{ city.province_name }} · {{ city.adcode }}</small></span>
          </button>
        </div>
        <div class="manual-search-actions">
          <button type="button" @click="emit('useIp')"><Wifi :size="16" />使用网络城市建议</button>
          <button type="button" @click="emit('cancel')">取消</button>
        </div>
      </div>

      <div v-else-if="phase === 'preview' && preview" class="check-in-preview">
        <div class="city-stamp">
          <span><MapPin :size="22" /></span>
          <div>
            <small>{{ preview.province_name }} · {{ preview.adcode }}</small>
            <strong>{{ preview.city_name }}</strong>
            <p>{{ preview.formatted_address || '高德未返回详细地址' }}</p>
          </div>
        </div>
        <dl>
          <div><dt>确认方式</dt><dd>{{ sourceLabels[preview.location_source] }}</dd></div>
          <div><dt>定位精度</dt><dd>{{ preview.location_source === 'device' && preview.accuracy_meters ? `约 ${Math.round(preview.accuracy_meters)} 米` : '城市级' }}</dd></div>
          <div><dt>当前状态</dt><dd>{{ preview.already_lit ? '已点亮，将更新最近到访' : '首次点亮' }}</dd></div>
        </dl>
        <p class="privacy-note"><LocateFixed :size="15" />{{ preview.privacy_notice }}</p>
        <div class="dialog-actions">
          <button class="secondary" type="button" @click="emit('cancel')">暂不记录</button>
          <button class="primary" type="button" @click="emit('confirm')"><Check :size="17" />确认点亮</button>
        </div>
      </div>

      <div v-else-if="phase === 'success' && preview" class="dialog-result" aria-live="polite">
        <span><Check :size="30" /></span>
        <strong>{{ preview.city_name }} 已加入旅行图鉴</strong>
        <p>地图与足迹统计已经更新。</p>
        <button class="primary" type="button" @click="emit('cancel')">回到地图</button>
      </div>

      <div v-else-if="phase === 'error' && error" class="dialog-error" role="alert">
        <span><AlertTriangle :size="27" /></span>
        <strong>{{ error.message }}</strong>
        <code>{{ error.code }}</code>
        <p v-if="error.code === 'AMAP_INVALID_SIGNATURE'">请在高德控制台关闭 Web 服务数字签名，或在后端配置对应私钥。</p>
        <p v-else-if="error.code === 'LOCATION_PERMISSION_DENIED'">请在浏览器地址栏的站点权限中允许位置访问。</p>
        <p v-else-if="error.code === 'LOCATION_TIMEOUT'">请到开阔位置重试，或检查系统定位服务是否开启。</p>
        <p v-else>{{ error.retryable ? '这是临时错误，可以稍后重试。' : '请根据错误代码检查配置。' }}</p>
        <small v-if="error.requestId">请求编号：{{ error.requestId }}</small>
        <div class="location-fallback-actions">
          <button type="button" @click="emit('useIp')"><Wifi :size="16" />网络城市建议</button>
          <button type="button" @click="emit('openManual')"><Search :size="16" />手动选择城市</button>
        </div>
        <div class="dialog-actions">
          <button class="secondary" type="button" @click="emit('cancel')">关闭</button>
          <button class="primary" type="button" @click="emit('retry')"><RotateCcw :size="16" />重新定位</button>
        </div>
      </div>
    </section>
  </div>
</template>
