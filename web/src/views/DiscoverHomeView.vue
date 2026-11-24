<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import UiButton from '../components/UiButton.vue'
import {
  ArrowRight,
  ArrowUpRight,
  CalendarDays,
  Camera,
  ExternalLink,
  Map,
  MapPin,
  Search,
  X,
} from 'lucide-vue-next'
import {
  destinations,
  destinationIntent,
  matchCities,
  searchableCities,
  type DiscoveryIntent,
  type TravelMood,
} from '../content/discovery'
import type { MapStats } from '../types'

withDefaults(defineProps<{ connected: boolean; stats: MapStats; cover?: 'city' | 'immersive' }>(), {
  cover: 'city',
})
const emit = defineEmits<{ plan: [intent: DiscoveryIntent]; map: []; stories: []; connect: [] }>()
const query = ref('')
const mood = ref<TravelMood>('all')
const showCities = ref(false)
const searchInput = ref<HTMLInputElement | null>(null)
const hero = ref<HTMLElement | null>(null)
const moods: Array<{ id: TravelMood; label: string }> = [
  { id: 'all', label: '全部灵感' },
  { id: 'sea', label: '海边放空' },
  { id: 'culture', label: '城市漫游' },
  { id: 'slow', label: '慢一点走' },
]
const visibleDestinations = computed(() =>
  destinations.filter(
    (d) => mood.value === 'all' || (d.moods as readonly string[]).includes(mood.value),
  ),
)
const choices = computed(() => {
  const matched = matchCities(query.value)
  return matched.length > 1 ? matched : searchableCities
})
function submitSearch() {
  if (!query.value.trim()) {
    showCities.value = true
    searchInput.value?.focus()
    return
  }
  const matched = matchCities(query.value.trim())
  if (matched.length === 1) chooseCity(matched[0]!.name, matched[0]!.adcode)
  else showCities.value = true
}
function clearSearch() {
  query.value = ''
  showCities.value = false
}
function searchSuggestion(text: string) {
  query.value = text
  submitSearch()
}
function chooseCity(name: string, adcode: string) {
  showCities.value = false
  const goal = query.value.trim()
    ? query.value.includes(name)
      ? query.value.trim()
      : `想去${name}，${query.value.trim()}`
    : `想去${name}旅行，帮我安排一段轻松的旅程。`
  emit('plan', { cityAdcode: adcode, goal, pace: 'relaxed' })
}
async function explore(text = '') {
  if (text) query.value = text
  showCities.value = true
  hero.value?.scrollIntoView?.({
    behavior: window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
      ? 'instant'
      : 'smooth',
    block: 'start',
  })
  await nextTick()
  searchInput.value?.focus({ preventScroll: true })
}
function exploreMood(id: TravelMood) {
  mood.value = id
  showCities.value = false
}
</script>

<template>
  <main class="discover-page" aria-label="旅行发现首页">
    <div class="discover-container">
      <section
        ref="hero"
        class="discover-hero"
        :class="{ 'discover-hero--immersive': cover === 'immersive' }"
        aria-labelledby="discover-title"
      >
        <div class="hero-image-wrap" aria-hidden="true">
          <img
            src="/discover/xiamen-hero.webp"
            alt=""
            class="hero-image"
            fetchpriority="high"
            width="1800"
            height="800"
          />
          <div class="hero-light"></div>
        </div>
        <div class="hero-content">

          <h1 id="discover-title">下一段旅程，<br />从心动开始<span>。</span></h1>
          <p class="hero-description">去一座想去的城，把沿途的风景慢慢收藏。</p>
          <div class="hero-search-area">
            <form
              class="discovery-search"
              role="search"
              @submit.prevent="submitSearch"
              @keydown.esc="showCities = false"
            >
              <Search :size="22" aria-hidden="true" />
              <input
                id="discover-search"
                ref="searchInput"
                v-model="query"
                type="search"
                maxlength="300"
                autocomplete="off"
                aria-label="旅行搜索"
                placeholder="目的地、景点，或这次旅行的想法"
              />
              <button
                v-if="query"
                class="clear-search"
                type="button"
                aria-label="清空搜索"
                @click="clearSearch"
              >
                <X :size="15" />
              </button>
              <button class="search-go" type="submit" aria-label="搜索并规划">
                <span>开始探索</span><ArrowRight :size="18" />
              </button>
            </form>
            <section v-if="showCities" class="search-city-panel" aria-label="选择旅行目的地">
              <div>
                <strong>{{ query ? '先选一座城，把想法带上' : '想从哪座城市开始？' }}</strong
                ><button type="button" aria-label="收起目的地选择" @click="showCities = false">
                  <X :size="16" />
                </button>
              </div>
              <p v-if="query">你的旅行想法会一并带入计划，之后还可以调整。</p>
              <div class="search-city-options">
                <button
                  v-for="city in choices"
                  :key="city.adcode"
                  type="button"
                  @click="chooseCity(city.name, city.adcode)"
                >
                  <MapPin :size="15" />{{ city.name }}<ArrowUpRight :size="14" />
                </button>
              </div>
            </section>
          </div>
          <div class="hero-suggestions">
            <span>试试</span
            ><button
              type="button"
              @click="searchSuggestion('厦门两日慢游')"
            >
              厦门两日慢游</button
            ><i></i
            ><button
              type="button"
              @click="searchSuggestion('杭州西湖散步')"
            >
              西湖边走走</button
            ><i></i
            ><button type="button" @click="explore('想看看自然，行程轻松一点')">
              给旅途留点空白
            </button>
          </div>
        </div>
        <div class="hero-location">
          <MapPin :size="14" /><span>中国 · 厦门</span><i></i><span>海风里的鼓浪屿</span>
        </div>
      </section>

      <section class="discover-shortcuts" aria-label="旅行快捷入口">
        <button type="button" @click="explore()">
          <span class="shortcut-icon peach"><MapPin :size="22" /></span
          ><span><strong>目的地</strong></span
          ><ArrowUpRight class="shortcut-arrow" :size="16" />
        </button>
        <button type="button" @click="emit('plan', { goal: '', pace: 'relaxed' })">
          <span class="shortcut-icon rose"><CalendarDays :size="22" /></span
          ><span><strong>规划行程</strong></span
          ><ArrowUpRight class="shortcut-arrow" :size="16" />
        </button>
        <button type="button" @click="emit('map')">
          <span class="shortcut-icon mint"><Map :size="22" /></span
          ><span><strong>旅行地图</strong></span
          ><ArrowUpRight class="shortcut-arrow" :size="16" />
        </button>
        <button type="button" @click="emit('stories')">
          <span class="shortcut-icon sand"><Camera :size="22" /></span
          ><span><strong>旅行记忆</strong></span
          ><ArrowUpRight class="shortcut-arrow" :size="16" />
        </button>

      </section>

      <div class="discover-lower-grid">
        <section class="destination-section" aria-labelledby="destination-heading">
          <header class="discover-section-heading">
            <div>

              <h2 id="destination-heading">总有一座城，让你想出发</h2>
              <p>从一份旅行灵感开始，慢慢走进当地的日常。</p>
            </div>
            <button class="quiet-link more-destinations" type="button" @click="explore()">
              更多目的地<ArrowUpRight :size="16" />
            </button>
          </header>
          <div class="mood-filters" role="group" aria-label="旅行灵感主题">
            <button
              v-for="item in moods"
              :key="item.id"
              type="button"
              :class="{ active: mood === item.id }"
              :aria-pressed="mood === item.id"
              @click="exploreMood(item.id)"
            >
              <span v-if="mood === item.id" class="filter-dot"></span>{{ item.label }}
            </button>
          </div>
          <div class="destination-grid">
            <button v-for="(destination, index) in visibleDestinations" :key="destination.id" type="button" class="destination-card" :aria-label="`规划${destination.name}旅行`" @click="emit('plan', destinationIntent(destination.id))">
              <span class="destination-photo"><img :src="destination.image" :alt="destination.imageAlt" :loading="index === 0 ? 'eager' : 'lazy'" decoding="async" width="960" height="640" /><span class="destination-photo-arrow"><ArrowUpRight :size="19" /></span></span>
              <span class="destination-content"><span class="destination-title"><strong>{{ destination.name }}</strong><span>{{ destination.headline }}</span></span></span>
            </button>
          </div>
          <div class="travel-map-invite">
            <div class="map-invite-symbol" aria-hidden="true">
              <Map :size="33" /><span></span><MapPin :size="18" />
            </div>
            <div class="map-invite-copy">
              <h3>每一次抵达，都有故事。</h3>
              <p v-if="connected">
                已经点亮 {{ stats.lit_cities }} 座城市，留下 {{ stats.memories }} 段旅行记忆。
              </p>
              <p v-else>在你的旅行地图里，收藏城市、照片与回忆。</p>
            </div>
            <button type="button" @click="emit('map')">
              打开我的地图<ArrowRight :size="16" />
            </button>
          </div>
        </section>

        <aside class="discovery-companion" aria-label="和小曦一起规划">
          <h2>想去哪里，<br />就从哪里开始。</h2>
          <p class="companion-description">给小曦一个想法，把时间留给期待。</p>
          <UiButton variant="secondary" @click="emit('plan', { goal: '', pace: 'relaxed' })">规划行程<ArrowRight :size="17" /></UiButton>
        </aside>
      </div>
      <footer class="discover-footer">
        <p>Voyaura</p>
        <a href="/discover/credits.html" target="_blank" rel="noopener noreferrer"
          >影像署名与许可<ExternalLink :size="12"
        /></a>
      </footer>
    </div>
  </main>
</template>

<style scoped>
.discover-page {
  position: absolute;
  inset: var(--product-header-height) 0 var(--product-bottom-height);
  overflow: auto;
  scroll-behavior: smooth;
  scroll-padding-top: 24px;
  background: var(--canvas);
}
.discover-container {
  margin: auto;
  width: min(1180px,calc(100% - 80px));
  padding: 22px 0 0;
  position: relative;
}
.discover-hero {
  position: relative;
  isolation: isolate;
  min-height: 282px;
  background: var(--canvas);
  border-radius: 20px;
}
.hero-image-wrap {
  position: absolute;
  overflow: hidden;
  z-index: -1;
  inset: 0;
  border-radius: 20px;
}
.hero-image {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: 72% 60%;
}
.hero-light {
  display: block;
  background: linear-gradient(90deg,#faf8f4 0%,#faf8f4f5 29%,#faf8f4b0 47%,#faf8f400 70%);
  position: absolute;
  inset: 0;
}
.hero-content {
  position: relative;
  width: 620px;
  max-width: 65%;
  padding: 22px 32px 14px;
}
.hero-content h1 {
  color: var(--text-primary);
  font-family: var(--font-editorial);
  font-size: 2.625rem;
  font-weight: 650;
  letter-spacing: -1px;
  line-height: 1.18;
  margin: 0 0 10px;
}
.hero-content h1>span {
  color: var(--brand-accent);
}
.hero-description {
  color: var(--text-secondary);
  font-size: var(--font-body);
  max-width: none;
  margin: 0 0 12px;
  line-height: 1.6;
}
.hero-search-area {
  position: relative;
  z-index: 25;
  width: 100%;
}
.discovery-search {
  display: flex;
  align-items: center;
  border: 1px solid var(--border-control);
  border-radius: var(--radius-control);
  background: var(--surface);
  color: var(--text-secondary);
  min-height: 54px;
  padding: 4px 5px 4px 14px;
  gap: 8px;
  border-color: var(--border-subtle);
  box-shadow: 0 3px 12px #263b3310;
}
.discovery-search:focus-within {
  border-color: var(--action);
}
.discovery-search>svg {
  flex: none;
}
.discovery-search input {
  width: 100%;
  min-width: 0;
  border: 0;
  background: transparent;
  color: var(--text-primary);
  font-size: var(--font-body);
  height: 44px;
}
.discovery-search input::placeholder {
  color: var(--text-secondary);
  opacity: 1;
}
.discovery-search input::-webkit-search-cancel-button {
  display: none;
}
.clear-search,.search-city-panel>div>button {
  display: grid;
  place-items: center;
  flex: none;
  min-width: 44px;
  height: 44px;
  border: 0;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
}
.search-go {
  display: flex;
  align-items: center;
  justify-content: center;
  flex: none;
  border: 1px solid var(--action);
  border-radius: var(--radius-control);
  background: var(--action);
  color: white;
  font-size: var(--font-secondary);
  font-weight: 600;
  cursor: pointer;
  min-height: 44px;
  padding: 9px 15px;
  gap: 10px;
}
.search-go:hover {
  background: var(--action-hover);
}
.hero-suggestions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  color: var(--text-secondary);
  margin-top: 0;
  gap: 0 12px;
  font-size: var(--font-label);
}
.hero-suggestions button {
  min-height: 44px;
  padding: 7px 0;
  border: 0;
  background: transparent;
  color: var(--text-secondary);
  font-size: inherit;
  cursor: pointer;
}
.hero-suggestions button:hover {
  color: var(--action);
  text-decoration: underline;
  text-underline-offset: 5px;
}
.hero-suggestions i {
  height: 12px;
  width: 1px;
  background: var(--border-subtle);
}
.hero-location {
  position: absolute;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  color: var(--text-secondary);
  font-size: var(--font-label);
  line-height: 1.6;
  right: 16px;
  bottom: 14px;
  padding: 7px 12px;
  border-radius: 24px;
  background: var(--canvas);
}
.hero-location i {
  width: 18px;
  height: 1px;
  background: var(--border-control);
}
.search-city-panel {
  position: absolute;
  inset: calc(100% + 8px) 0 auto;
  padding: 20px;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-surface);
  background: var(--surface);
  box-shadow: var(--shadow-float);
}
.search-city-panel>div:first-child {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}
.search-city-panel strong {
  font-size: var(--font-body);
  color: var(--text-primary);
}
.search-city-panel p {
  color: var(--text-secondary);
  font-size: var(--font-secondary);
  line-height: var(--line-body);
  margin: 6px 0 12px;
}
.search-city-options {
  display: grid;
  grid-template-columns: repeat(3,minmax(0,1fr));
  gap: 8px;
  margin-top: 12px;
}
.search-city-options button {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-height: 46px;
  padding: 8px;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-control);
  background: var(--canvas);
  color: var(--text-body);
  font-size: var(--font-secondary);
  cursor: pointer;
}
.search-city-options button:hover {
  background: var(--sage);
  border-color: var(--border-control);
}
.discover-shortcuts {
  display: grid;
  grid-template-columns: repeat(4,minmax(0,1fr));
  border-block: 1px solid var(--border-subtle);
  gap: 18px;
  margin: 16px 0 24px;
  padding: 0;
  border: 0;
}
.discover-shortcuts>button {
  display: flex;
  align-items: center;
  border-right: 1px solid var(--border-subtle);
  color: var(--text-primary);
  text-align: left;
  cursor: pointer;
  min-height: 56px;
  padding: 6px 14px;
  gap: 14px;
  border: 0;
  border-radius: 10px;
  background: var(--surface-soft);
}
.discover-shortcuts>button:first-child {
  padding-left: 14px;
}
.discover-shortcuts>button:last-child {
  border-right: 0;
}
.shortcut-icon {
  display: grid;
  place-items: center;
  flex: none;
  color: var(--action);
  width: 44px;
  height: 44px;
  border-radius: 10px;
}
.discover-shortcuts strong {
  font-size: var(--font-body);
  font-weight: 550;
}
.shortcut-arrow {
  margin-left: auto;
  color: var(--text-secondary);
  display: none;
}
.discover-shortcuts>button:hover strong {
  text-decoration: underline;
  text-underline-offset: 5px;
}
.discover-lower-grid {
  display: grid;
  grid-template-columns: minmax(0,1fr);
  gap: 16px;
}
.discover-section-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
}
.discover-section-heading h2 {
  margin: 0;
  color: var(--text-primary);
  font-family: var(--font-editorial);
  letter-spacing: -.7px;
  font-size: 1.75rem;
  font-weight: 650;
  line-height: 1.4;
}
.discover-section-heading p {
  color: var(--text-secondary);
  margin: 4px 0 0;
  font-size: var(--font-secondary);
  line-height: 1.6;
}
.quiet-link {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  flex: none;
  min-height: 44px;
  padding: 10px 0;
  border: 0;
  background: transparent;
  color: var(--text-body);
  font-size: var(--font-secondary);
  cursor: pointer;
}
.quiet-link:hover {
  color: var(--action);
  text-decoration: underline;
  text-underline-offset: 4px;
}
.mood-filters {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  margin: 12px 0 14px;
}
.mood-filters button {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 44px;
  border: 0;
  color: var(--text-secondary);
  font-size: var(--font-secondary);
  cursor: pointer;
  padding: 8px 16px;
  border-bottom: 0;
  border-radius: 24px;
  background: var(--surface-soft);
}
.mood-filters button.active {
  font-weight: 600;
  background: var(--action);
  color: white;
  border-bottom-color: transparent;
}
.filter-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: currentColor;
}
.destination-grid {
  display: grid;
  grid-template-columns: repeat(3,minmax(0,1fr));
  gap: 16px;
}
.destination-card {
  flex-direction: column;
  gap: 0;
  min-width: 0;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--text-primary);
  text-align: left;
  cursor: pointer;
  position: relative;
  display: block;
  border-radius: 14px;
  overflow: hidden;
}
.destination-photo {
  display: block;
  position: relative;
  width: 100%;
  overflow: hidden;
  background: var(--sage);
  aspect-ratio: 2 / 1;
  border-radius: 14px;
}
.destination-photo img {
  width: 100%;
  height: 100%;
  display: block;
  object-fit: cover;
  transition: transform .3s ease;
}
.destination-photo-arrow {
  position: absolute;
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--surface);
  color: var(--text-body);
  top: auto;
  bottom: 12px;
  right: 12px;
  z-index: 2;
}
.destination-card:hover .destination-photo img {
  transform: scale(1.025);
}
.destination-content {
  display: block;
  position: absolute;
  inset: auto 60px 16px 20px;
  width: auto;
  padding: 0;
  color: white;
  z-index: 1;
}
.destination-title {
  display: flex;
  flex-wrap: wrap;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
}
.destination-title strong {
  font-family: var(--font-editorial);
  font-size: 1.625rem;
  font-weight: 600;
  line-height: 1.3;
}
.destination-title>span {
  line-height: var(--line-body);
  color: white;
  font-size: var(--font-secondary);
}
.travel-map-invite {
  display: flex;
  align-items: center;
  margin-top: 38px;
  background: var(--sage) var(--texture-map) right center/420px auto no-repeat;
  margin: 16px 0 0;
  padding: 14px 20px;
  gap: 18px;
  min-height: 80px;
  border-radius: 12px;
}
.map-invite-symbol {
  display: grid;
  place-items: center;
  position: relative;
  flex: none;
  color: var(--forest);
  width: 44px;
  height: 44px;
}
.map-invite-symbol>svg:last-child {
  position: absolute;
  right: 0;
  top: 0;
  background: var(--sage);
}
.map-invite-copy {
  min-width: 0;
  flex: 1;
}
.map-invite-copy h3 {
  font-family: var(--font-editorial);
  color: var(--text-primary);
  font-size: var(--font-section);
  font-weight: 600;
  margin: 0 0 3px;
}
.map-invite-copy p {
  margin: 0;
  color: var(--text-secondary);
  font-size: var(--font-secondary);
  line-height: var(--line-body);
}
.travel-map-invite>button {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 44px;
  flex: none;
  color: var(--text-primary);
  font-size: var(--font-secondary);
  cursor: pointer;
  padding: 8px 14px;
  border: 1px solid var(--border-control);
  border-radius: var(--radius-control);
  background: var(--canvas);
}
.travel-map-invite>button:hover {
  text-decoration: underline;
  text-underline-offset: 5px;
}
.discovery-companion {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  border-bottom: 1px solid var(--border-subtle);
  padding: 0;
  gap: 18px;
  border: 0;
  min-height: 58px;
}
.discovery-companion h2 {
  margin: 0;
  font-family: var(--font-editorial);
  color: var(--text-primary);
  font-size: var(--font-section);
  line-height: 1.55;
  font-weight: 600;
}
.discovery-companion h2 br {
  display: none;
}
.companion-description {
  flex: 1;
  margin: 0;
  color: var(--text-secondary);
  line-height: var(--line-body);
  font-size: var(--font-secondary);
}
.discover-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  color: var(--text-secondary);
  font-size: var(--font-label);
  padding: 16px 0 22px;
}
.discover-footer p {
  font-size: var(--font-secondary);
  font-weight: 600;
  margin: 0;
}
.discover-footer a {
  display: flex;
  align-items: center;
  gap: 5px;
  min-height: 44px;
  color: inherit;
  text-underline-offset: 4px;
}
.discover-hero--immersive .hero-image-wrap {
  inset: 0;
  border-radius: var(--radius-surface);
}
.discover-hero--immersive .hero-content {
  padding-left: 32px;
}
.discover-hero--immersive .hero-light {
  display: block;
  background: linear-gradient(90deg,var(--canvas) 0%,#faf8f4e8 30%,#faf8f400 85%);
}
.discover-hero--immersive .hero-location {
  bottom: 14px;
  right: 16px;
  padding: 8px 12px;
  background: var(--canvas);
}
.shortcut-icon.peach {
  background: var(--action-soft);
  color: var(--action);
}
.shortcut-icon.rose {
  background: #f7e8e4;
  color: var(--action);
}
.shortcut-icon.mint {
  background: var(--sage);
  color: var(--forest);
}
.shortcut-icon.sand {
  background: #f3e7d2;
  color: #79613f;
}
.destination-photo::after {
  content: '';
  position: absolute;
  inset: 28% 0 0;
  background: linear-gradient(0deg,#102b27e6,transparent);
}
.discovery-companion .ui-button {
  background: var(--action);
  color: white;
  border-color: var(--action);
}
@media (min-width:1600px) {
  .discover-hero {
    min-height: 282px;
  }
  .hero-content {
    padding-top: 22px;
  }
}
@media (min-width:900px) and (max-width:1150px) {
  .hero-content {
    width: 590px;
    max-width: 70%;
  }
  .hero-content h1 {
    font-size: 2.375rem;
  }
  .hero-search-area {
    width: 100%;
  }
  .discover-shortcuts>button {
    padding: 6px 10px;
    gap: 8px;
  }
}
@media (max-width:899px) {
  .discover-container {
    width: calc(100% - 40px);
    padding-top: 24px;
  }
  .discover-hero {
    display: flex;
    flex-direction: column;
    min-height: 0;
  }
  .hero-content {
    width: 100%;
    max-width: none;
    padding: 10px 0 20px;
  }
  .hero-content h1 {
    margin-bottom: 18px;
    letter-spacing: -1px;
    font-size: 2.25rem;
    font-weight: 600;
  }
  .hero-description {
    max-width: none;
    margin-bottom: 22px;
  }
  .hero-search-area {
    width: 100%;
  }
  .hero-image-wrap {
    position: relative;
    inset: auto;
    width: 100%;
    order: 2;
    z-index: 0;
    border-radius: 14px;
    height: 200px;
  }
  .hero-location {
    position: static;
    order: 3;
    justify-content: flex-end;
    padding: 12px 0 0;
    background: transparent;
  }
  .hero-suggestions {
    gap: 0 12px;
    margin-top: 8px;
  }
  .discover-shortcuts {
    grid-template-columns: repeat(2,minmax(0,1fr));
    gap: 12px;
    margin: 20px 0 28px;
    padding: 0;
  }
  .discover-shortcuts>button {
    flex-wrap: wrap;
    flex-direction: row;
    justify-content: flex-start;
    padding: 8px 14px;
    gap: 12px;
  }
  .discover-shortcuts>button:first-child {
    padding-left: 14px;
  }
  .shortcut-arrow {
    display: none;
  }
  .shortcut-icon {
    width: 30px;
  }
  .discover-shortcuts strong {
    font-size: var(--font-secondary);
  }
  .discover-section-heading h2 {
    font-size: 1.625rem;
  }
  .destination-grid {
    gap: 18px;
  }
  .destination-title {
    flex-direction: column;
    gap: 2px;
  }
  .destination-title strong {
    font-size: var(--font-section);
  }
  .travel-map-invite {
    flex-wrap: wrap;
    padding: 20px;
    gap: 12px;
  }
  .discovery-companion {
    gap: 16px;
  }
  .discover-hero--immersive .hero-image-wrap {
    inset: auto;
  }
  .discover-hero--immersive .hero-content {
    padding-left: 0;
  }
  .discover-hero--immersive .hero-light {
    display: none;
  }
}
@media (max-width:600px) {
  .discovery-search {
    min-height: 60px;
    padding: 6px;
    gap: 8px;
  }
  .discovery-search>svg {
    display: none;
  }
  .search-go {
    gap: 6px;
    padding: 10px 12px;
  }
  .search-go>svg {
    display: none;
  }
  .discovery-search input {
    height: 46px;
  }
  .hero-image-wrap {
    height: 180px;
  }
  .search-city-panel {
    padding: 14px;
  }
  .search-city-options {
    grid-template-columns: repeat(2,minmax(0,1fr));
  }
  .discover-shortcuts {
    gap: 12px;
  }
  .discover-shortcuts>button {
    flex-direction: row;
    padding: 8px 10px;
    gap: 10px;
  }
  .discover-shortcuts strong {
    font-size: var(--font-secondary);
  }
  .discover-section-heading {
    align-items: flex-start;
    flex-wrap: wrap;
    gap: 8px;
  }
  .discover-section-heading h2 {
    font-size: 1.5rem;
  }
  .discover-section-heading p {
    font-size: var(--font-secondary);
  }
  .quiet-link {
    margin-left: auto;
  }
  .mood-filters {
    gap: 8px;
    margin: 12px 0 16px;
  }
  .destination-grid {
    grid-template-columns: 1fr;
    gap: 14px;
  }
  .destination-photo {
    aspect-ratio: 1.85 / 1;
  }
  .destination-title {
    align-items: baseline;
    flex-direction: column;
    gap: 2px;
  }
  .destination-content {
    padding: 0;
  }
  .destination-title strong {
    font-size: 1.625rem;
  }
  .map-invite-symbol {
    display: none;
  }
  .travel-map-invite {
    margin-top: 20px;
    padding: 20px;
  }
  .map-invite-copy {
    flex: 1 1 100%;
  }
  .travel-map-invite>button {
    min-height: 44px;
  }
  .discovery-companion {
    flex-direction: column;
    align-items: flex-start;
    padding: 8px 0 0;
  }
  .discovery-companion .ui-button {
    width: 100%;
  }
  .discover-footer {
    padding: 20px 0 28px;
  }
}
@media (max-width:360px) {
  .discover-container {
    width: calc(100% - 32px);
  }
  .hero-suggestions {
    font-size: var(--font-label);
    gap: 0 9px;
  }
  .hero-suggestions i {
    display: none;
  }
  .clear-search {
    width: 44px;
  }
}
@media (prefers-reduced-motion:reduce) {
  .discover-page {
    scroll-behavior: auto;
  }
  .destination-photo img {
    transition: none;
  }
}
@media (max-width:899px) {
  .hero-light {
    display: none;
  }
}
@media (max-width:600px) {
  .hero-content h1 {
    font-size: 2rem;
  }
}
@media (max-width:600px) {
  .hero-suggestions {
    font-size: var(--font-label);
    gap: 0 12px;
  }
}
@media (max-width:600px) {
  .shortcut-icon {
    width: 36px;
    height: 44px;
  }
}
@media (max-width:600px) {
  .mood-filters button {
    padding: 8px 12px;
  }
}
@media (max-width:360px) {
  .discovery-search {
    flex-wrap: wrap;
  }
}
@media (max-width:360px) {
  .discovery-search input {
    flex-basis: calc(100% - 52px);
  }
}
@media (max-width:360px) {
  .search-go {
    width: 100%;
  }
}
@media (min-width:1680px) {
  .discover-container::after {
    content: '';
    position: absolute;
    top: 44px;
    right: -200px;
    width: 180px;
    height: 120px;
    background: url('/art/brand-postmark.svg') center/contain no-repeat;
    opacity: .36;
    transform: rotate(-10deg);
    pointer-events: none;
  }
}
</style>
