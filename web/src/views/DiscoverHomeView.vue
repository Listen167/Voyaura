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
            :src="'/discover/xiamen-hero.webp'"
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
  inset: var(--product-header-height) 0 0;
  overflow: auto;
  background: var(--page-bg);
  scroll-behavior: smooth;
  scroll-padding-top: 24px;
}
.discover-container {
  width: min(1320px, calc(100% - 80px));
  margin: auto;
  padding: 30px 0 0;
}
.discover-hero {
  position: relative;
  min-height: 405px;
  border-radius: 20px;
  background: #eaf1f2;
  isolation: isolate;
}
.hero-image-wrap {
  position: absolute;
  inset: 0;
  border-radius: 20px;
  overflow: hidden;
  z-index: -1;
}
.hero-image {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: 75% 48%;
}
.hero-light {
  position: absolute;
  inset: 0;
}
.hero-content {
  position: relative;
  width: 620px;
  max-width: 75%;
  padding: 42px 0 39px 46px;
}
.hero-content h1 {
  letter-spacing: -1.8px;
  font-weight: 650;
  color: var(--text-primary);
  margin: 0 0 15px;
}
.hero-content h1 > span {
  color: var(--brand-orange);
}
.hero-description {
  color: var(--text-secondary);
  line-height: 1.8;
  margin: 0 0 24px;
}
.hero-search-area {
  position: relative;
  z-index: 25;
}
.discovery-search {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 6px 7px 6px 18px;
  border: 1px solid #ffffffc9;
  border-radius: var(--radius-surface);
  background: #fffffff5;
  box-shadow: 0 8px 30px #344d4712;
}
.discovery-search > svg {
  color: var(--text-secondary);
  flex: none;
}
.discovery-search input {
  width: 100%;
  min-width: 0;
  border: 0;
  outline: 0;
  background: transparent;
  line-height: 1.6;
  color: var(--text-secondary);
}
.discovery-search input::-webkit-search-cancel-button {
  display: none;
}
.discovery-search:focus-within {
  outline: 3px solid var(--focus);
  outline-offset: 2px;
}
.search-go {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  flex: none;
  height: 44px;
  padding: 0 17px;
  border: 0;
  border-radius: var(--radius-surface);
  color: white;
  font-size: var(--font-secondary);
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s;
}
.search-go:hover {
  background: #bc4020;
}
.clear-search {
  display: grid;
  place-items: center;
  padding: 4px;
  border: 0;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
}
.hero-suggestions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 9px;
  margin-top: 14px;
  color: var(--text-secondary);
  font-size: var(--font-label);
}
.hero-suggestions > span {
  font-size: var(--font-label);
  color: var(--text-secondary);
}
.hero-suggestions button {
  border: 0;
  background: transparent;
  padding: 3px 0;
  font-size: var(--font-label);
  cursor: pointer;
}
.hero-suggestions button:hover {
  color: var(--brand-ink-orange);
}
.hero-suggestions i {
  width: 2px;
  height: 2px;
  border-radius: 50%;
  background: #a4afa6;
}
.hero-location {
  display: flex;
  align-items: center;
  gap: 7px;
  position: absolute;
  right: 24px;
  bottom: 22px;
  padding: 9px 12px;
  border: 1px solid #ffffff6b;
  border-radius: 20px;
  backdrop-filter: blur(10px);
  font-size: var(--font-label);
}
.hero-location i {
  width: 1px;
  height: 10px;
  background: #c4cec5;
}
.search-city-panel {
  position: absolute;
  top: calc(100% + 10px);
  left: 0;
  right: 0;
  padding: 18px;
  border: 1px solid #ece7df;
  border-radius: var(--radius-surface);
  background: #fffefa;
  box-shadow: 0 15px 40px #213d3524;
}
.search-city-panel > div:first-child {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.search-city-panel strong {
  font-size: var(--font-secondary);
  font-weight: 600;
}
.search-city-panel > div:first-child > button {
  border: 0;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  padding: 5px;
}
.search-city-panel > p {
  font-size: var(--font-secondary);
  color: var(--text-secondary);
  line-height: 1.7;
  margin: 7px 0 15px;
}
.search-city-options {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  margin-top: 12px;
}
.search-city-options > button {
  display: flex;
  align-items: center;
  gap: 7px;
  border: 1px solid #eee9e0;
  border-radius: var(--radius-control);
  padding: 11px 9px;
  background: #fbfaf5;
  color: var(--text-secondary);
  font-size: var(--font-secondary);
  cursor: pointer;
}
.search-city-options > button > svg:first-child {
  color: var(--action);
}
.search-city-options > button > svg:last-child {
  margin-left: auto;
  color: var(--text-secondary);
}
.search-city-options > button:hover {
  background: #fff0e8;
  border-color: #f1cbb8;
}
.discover-shortcuts {
  display: grid;
  gap: 0;
  padding: 18px 2px;
  border-radius: var(--radius-surface);
}
.discover-shortcuts > button {
  display: flex;
  align-items: center;
  gap: 13px;
  border: 0;
  background: transparent;
  text-align: left;
  cursor: pointer;
  min-width: 0;
}
.discover-shortcuts > button:last-child {
  border-right: 0;
}
.shortcut-icon {
  display: grid;
  place-items: center;
  width: 44px;
  height: 44px;
  flex: none;
  border-radius: var(--radius-surface);
  transition: transform 0.2s;
}
.peach {
  color: var(--action);
  background: #fff0e7;
}
.rose {
  color: var(--action);
  background: #fcecee;
}
.mint {
  color: var(--text-secondary);
  background: #e9f3ee;
}
.sand {
  color: var(--text-secondary);
  background: #fcf2df;
}
.lilac {
  color: var(--text-secondary);
  background: #f1ecf8;
}
.discover-shortcuts > button:hover .shortcut-icon {
  transform: translateY(-3px);
}
.discover-shortcuts > button > span:nth-child(2) {
  display: flex;
  flex-direction: column;
  gap: 5px;
  min-width: 0;
}
.discover-shortcuts strong {
  font-size: var(--font-secondary);
  font-weight: 600;
  color: var(--text-secondary);
  white-space: nowrap;
}
.discover-shortcuts small {
  white-space: nowrap;
}
.shortcut-arrow {
  display: none;
  flex: none;
  margin-left: auto;
  color: var(--text-secondary);
}
.discover-lower-grid {
  display: grid;
  gap: 28px;
  align-items: stretch;
}
.destination-section {
  min-width: 0;
}
.discover-section-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  margin: 0 0 19px;
}
.discover-section-heading h2 {
  line-height: 1.45;
  letter-spacing: -0.5px;
  font-weight: 650;
  margin: 0 0 7px;
}
.discover-section-heading > div > p:last-child {
  color: var(--text-secondary);
  line-height: 1.7;
  margin: 0;
}
.quiet-link {
  min-height: 44px;
  display: flex;
  align-items: center;
  gap: 5px;
  white-space: nowrap;
  padding: 7px 0;
  border: 0;
  background: transparent;
  color: var(--text-secondary);
  font-size: var(--font-label);
  cursor: pointer;
}
.quiet-link:hover {
  color: var(--brand-ink-orange);
}
.mood-filters {
  display: flex;
  gap: 7px;
  align-items: center;
  margin: 0 0 19px;
  flex-wrap: wrap;
}
.mood-filters > button {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  min-height: 44px;
  border: 1px solid transparent;
  border-radius: 18px;
  background: transparent;
  cursor: pointer;
}
.mood-filters > button.active {
  color: var(--brand-ink-orange);
  background: #fff0e7;
  border-color: #f3d3c1;
  font-weight: 600;
}
.filter-dot {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: #e97c54;
}
.destination-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 17px;
}
.destination-card {
  display: block;
  overflow: hidden;
  padding: 0;
  text-align: left;
  cursor: pointer;
  transition: transform 0.25s,
    box-shadow 0.25s;
}
.destination-photo {
  position: relative;
  display: block;
  overflow: hidden;
}
.destination-photo > img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.55s;
}
.destination-card:hover .destination-photo > img {
  transform: scale(1.04);
}
.destination-photo-shade {
  position: absolute;
  inset: 0;
  background: linear-gradient(0deg, #18362b36, transparent 50%);
}
.destination-photo-arrow {
  position: absolute;
  right: 10px;
  top: 10px;
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  border-radius: 50%;
  background: #ffffffe8;
  color: var(--text-secondary);
}
.destination-content {
  display: block;
}
.destination-title {
  display: flex;
  flex-direction: column;
  margin-bottom: 8px;
}
.destination-title > strong {
  font-weight: 650;
  line-height: 1.25;
}
.discovery-companion {
  position: relative;
  overflow: hidden;
}
.ray-one {
  left: 9%;
  top: 44px;
}
.ray-two {
  right: 18%;
  top: 11px;
  width: 3px;
  height: 3px;
}
.ray-three {
  left: 25%;
  bottom: 4px;
  width: 3px;
  height: 3px;
}
.discovery-companion h2 {
  font-weight: 600;
  letter-spacing: -0.6px;
  color: var(--text-secondary);
}
.companion-description {
  line-height: 1.9;
  margin: 0 0 19px;
}
.travel-map-invite {
  display: flex;
  align-items: center;
  gap: 18px;
  margin-top: 24px;
  padding: 23px 21px;
  border: 1px solid #e4e9de;
  border-radius: var(--radius-surface);
  background: linear-gradient(100deg, #edf2e9, #f4f5ec 65%);
}
.map-invite-symbol {
  position: relative;
  display: grid;
  place-items: center;
  width: 52px;
  height: 52px;
  flex: none;
  color: var(--text-secondary);
}
.map-invite-symbol > svg:last-child {
  position: absolute;
  right: -1px;
  top: -1px;
  color: var(--action);
  fill: #faf6ed;
}
.map-invite-copy {
  min-width: 0;
}
.map-invite-copy h3 {
  font-size: var(--font-body);
  font-weight: 600;
  color: var(--text-secondary);
  margin: 0 0 7px;
}
.map-invite-copy p {
  font-size: var(--font-label);
  margin: 0;
  line-height: 1.7;
}
.travel-map-invite > button {
  min-height: 44px;
  display: flex;
  align-items: center;
  gap: 8px;
  white-space: nowrap;
  margin-left: auto;
  padding: 11px 12px;
  border: 1px solid #cddac3;
  border-radius: var(--radius-control);
  background: #fffffa80;
  color: var(--text-secondary);
  font-size: var(--font-label);
  cursor: pointer;
}
.travel-map-invite > button:hover {
  background: #fffef8;
}
.discover-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 29px 0 24px;
  color: var(--text-secondary);
  font-size: var(--font-label);
}
.discover-footer p {
  margin: 0;
}
.discover-footer p > span {
  margin: 0 7px;
}
.discover-footer a {
  display: flex;
  align-items: center;
  gap: 5px;
  color: var(--text-secondary);
  text-decoration: none;
  font-size: var(--font-label);
}
.discover-footer a:hover {
  color: var(--text-secondary);
}
@media (min-width: 1600px) {
  .discover-container {
    padding-top: 36px;
  }
  .discover-hero {
    min-height: 440px;
  }
  .hero-content {
    padding: 50px 0 46px 55px;
  }
  .hero-content h1 {
    font-size: var(--font-display);
  }
  .discover-lower-grid {
    grid-template-columns: minmax(0, 1fr) 290px;
  }
}
@media (min-width: 900px) and (max-width: 1150px) {
  .discover-container {
    width: calc(100% - 48px);
  }
  .discover-shortcuts > button {
    padding: 4px 13px;
    gap: 9px;
  }
  .shortcut-icon {
    width: 38px;
    height: 38px;
    border-radius: var(--radius-surface);
  }
  .discover-shortcuts strong {
    font-size: var(--font-secondary);
  }
  .discover-shortcuts small {
    font-size: var(--font-label);
  }
  .discover-lower-grid {
    grid-template-columns: minmax(0, 1fr) 250px;
    gap: 20px;
  }
  .destination-grid {
    gap: 12px;
  }
  .destination-content {
    padding: 14px 11px;
  }
  .destination-title > strong {
    font-size: var(--font-section);
  }
  .discovery-companion {
    padding: 23px 18px;
    flex-direction: row;
    min-width: 0;
    flex-wrap: wrap;
  }
  .discovery-companion h2 {
    font-size: var(--font-section);
  }
  .travel-map-invite {
    padding: 20px 15px;
    gap: 10px;
  }
  .travel-map-invite > button {
    min-height: 44px;
    padding: 9px;
    font-size: var(--font-label);
  }
}
@media (max-width: 899px) {
  .discover-page {
    bottom: calc(68px + env(safe-area-inset-bottom));
    scroll-padding-top: 16px;
  }
  .discover-container {
    width: calc(100% - 40px);
    padding-top: 20px;
  }
  .discover-hero {
    min-height: 365px;
  }
  .hero-content {
    width: 570px;
    max-width: 85%;
    padding: 34px 0 32px 30px;
  }
  .hero-content h1 {
    font-size: var(--font-display);
  }
  .hero-light {
    background: linear-gradient(90deg, #f9f8f3f5 0%, #f9f8f3d9 30%, #f9f8f32e 80%);
  }
  .hero-description {
    font-size: var(--font-secondary);
  }
  .hero-location {
    font-size: var(--font-label);
    right: 16px;
    bottom: 16px;
  }
  .discover-shortcuts {
    margin: 17px 0 28px;
    padding: 15px 6px;
  }
  .discover-shortcuts > button {
    flex-direction: column;
    gap: 9px;
    padding: 0 4px;
    border-right: 0;
    text-align: center;
  }
  .discover-shortcuts small {
    display: none;
  }
  .discover-shortcuts > button > span:nth-child(2) {
    gap: 0;
  }
  .discover-shortcuts strong {
    font-size: var(--font-secondary);
    font-weight: 500;
  }
  .shortcut-icon {
    width: 42px;
    height: 42px;
    border-radius: 50%;
  }
  .discover-lower-grid {
    grid-template-columns: 1fr;
    gap: 26px;
  }
  .discovery-companion {
    display: grid;
    grid-template-columns: 120px minmax(0, 1fr);
    column-gap: 22px;
    padding: 25px;
    flex-direction: row;
    min-width: 0;
    flex-wrap: wrap;
  }
  .discovery-companion .companion-eyebrow,
.discovery-companion h2,
.companion-description,
.companion-start {
    grid-column: 2;
  }
  .discovery-companion h2 {
    font-size: var(--font-section);
  }
  .discovery-companion h2 > br {
    display: none;
  }
  .companion-description {
    margin-bottom: 15px;
  }
  .desktop-break {
    display: none;
  }
  .discover-section-heading h2 {
    font-size: var(--font-section);
  }
  .discover-footer {
    padding: 25px 0 20px;
  }
}
@media (max-width: 600px) {
  .discover-container {
    width: calc(100% - 32px);
    padding-top: 15px;
  }
  .discover-hero {
    min-height: 333px;
    border-radius: 15px;
  }
  .hero-image-wrap {
    border-radius: 15px;
  }
  .hero-image {
    object-position: 71% 46%;
  }
  .hero-light {
    background: linear-gradient(90deg, #faf8f2f5 0%, #faf8f2c4 37%, #faf8f23d 82%),
      linear-gradient(0deg, #faf8f2e8 0%, #faf8f200 30%);
  }
  .hero-content {
    width: 100%;
    max-width: 100%;
    padding: 28px 21px 34px;
  }
  .hero-content h1 {
    font-size: var(--font-title);
    line-height: 1.34;
    letter-spacing: -0.8px;
    margin-bottom: 11px;
  }
  .hero-description {
    font-size: var(--font-label);
    line-height: 1.8;
    max-width: 230px;
    margin-bottom: 22px;
  }
  .discovery-search {
    height: auto;
    padding: 5px 5px 5px 12px;
    gap: 8px;
    border-radius: var(--radius-surface);
    min-height: 56px;
  }
  .discovery-search > svg {
    width: 18px;
    height: 18px;
  }
  .discovery-search input {
    font-size: var(--font-body);
    min-height: 44px;
  }
  .search-go {
    height: 39px;
    width: 40px;
    padding: 0;
    border-radius: var(--radius-surface);
    gap: 0;
  }
  .search-go > span {
    display: none;
  }
  .hero-suggestions {
    gap: 7px;
    margin-top: 12px;
  }
  .hero-suggestions button {
    min-height: 44px;
    font-size: var(--font-label);
    line-height: 1.6;
  }
  .hero-suggestions > span {
    font-size: var(--font-label);
  }
  .hero-location {
    bottom: 12px;
    left: 22px;
    right: auto;
    font-size: var(--font-label);
    gap: 5px;
    padding: 0;
    border: 0;
    border-radius: 0;
    background: transparent;
    color: var(--text-secondary);
    backdrop-filter: none;
  }
  .hero-location > svg {
    width: 10px;
    height: 10px;
  }
  .hero-location i {
    height: 8px;
    background: #aebeb0;
  }
  .discover-shortcuts {
    margin: 15px 0 27px;
    padding: 15px 4px 14px;
    border-radius: var(--radius-surface);
  }
  .shortcut-icon {
    width: 36px;
    height: 36px;
  }
  .shortcut-icon > svg {
    width: 19px;
    height: 19px;
  }
  .discover-shortcuts > button {
    gap: 8px;
  }
  .discover-shortcuts strong {
    font-size: var(--font-label);
    letter-spacing: 0;
  }
  .discover-section-heading {
    gap: 8px;
    margin-bottom: 15px;
  }
  .discover-section-heading h2 {
    font-size: var(--font-section);
    letter-spacing: -0.6px;
    margin-bottom: 6px;
  }
  .discover-section-heading > div > p:last-child {
    font-size: var(--font-label);
    line-height: 1.8;
  }
  .more-destinations {
    min-height: 44px;
    font-size: 0;
    min-width: 32px;
    height: 32px;
    justify-content: center;
    border: 1px solid #e6e6db;
    border-radius: 50%;
    padding: 0;
  }
  .more-destinations > svg {
    width: 16px;
    height: 16px;
  }
  .mood-filters {
    flex-wrap: wrap;
    gap: 2px;
    margin-bottom: 16px;
  }
  .mood-filters > button {
    padding: 7px 9px;
    min-height: 44px;
    font-size: var(--font-label);
    gap: 4px;
    white-space: nowrap;
  }
  .destination-grid {
    display: flex;
    gap: 13px;
    margin-right: -16px;
    padding: 3px 16px 12px 0;
    overflow-x: auto;
    scroll-snap-type: x mandatory;
    scrollbar-width: none;
  }
  .destination-grid::-webkit-scrollbar {
    display: none;
  }
  .destination-card {
    flex: 0 0 226px;
    scroll-snap-align: start;
    border-radius: var(--radius-surface);
    box-shadow: none;
  }
  .destination-card:hover {
    transform: none;
  }
  .destination-photo {
    aspect-ratio: 1.38;
  }
  .destination-content {
    padding: 15px 14px;
  }
  .destination-title > strong {
    font-size: var(--font-section);
  }
  .destination-title > span {
    font-size: var(--font-secondary);
  }
  .travel-map-invite {
    position: relative;
    align-items: flex-start;
    gap: 11px;
    margin-top: 14px;
    padding: 17px 15px 18px;
    border-radius: var(--radius-surface);
  }
  .map-invite-symbol {
    width: 37px;
    height: 41px;
  }
  .map-invite-symbol > svg:first-child {
    width: 30px;
    height: 30px;
  }
  .map-invite-symbol > svg:last-child {
    width: 15px;
    height: 15px;
  }
  .map-invite-copy {
    padding-top: 4px;
    padding-bottom: 32px;
  }
  .map-invite-copy h3 {
    font-size: var(--font-secondary);
    margin-bottom: 7px;
  }
  .map-invite-copy p {
    font-size: var(--font-label);
    line-height: 1.8;
  }
  .travel-map-invite > button {
    min-height: 44px;
    position: absolute;
    left: 63px;
    bottom: 15px;
    border: 0;
    background: transparent;
    padding: 0;
    gap: 5px;
    font-size: var(--font-label);
    min-height: 44px;
  }
  .travel-map-invite > button > svg {
    width: 13px;
    height: 13px;
  }
  .discovery-companion {
    padding: 21px 18px;
    column-gap: 14px;
    grid-template-columns: 74px minmax(0, 1fr);
    border-radius: var(--radius-surface);
    flex-direction: row;
    min-width: 0;
    flex-wrap: wrap;
  }
  .ray-one {
    left: -10%;
  }
  .ray-two {
    right: 3%;
    top: 3px;
  }
  .discovery-companion h2 {
    font-size: var(--font-card);
    letter-spacing: -0.4px;
    line-height: 1.5;
    margin-bottom: 8px;
  }
  .discovery-companion h2 > br {
    display: none;
  }
  .companion-description {
    font-size: var(--font-label);
    line-height: 1.9;
    margin-bottom: 13px;
  }
  .discover-footer {
    align-items: flex-start;
    gap: 10px;
    padding: 23px 0 19px;
    font-size: var(--font-label);
  }
  .discover-footer p {
    max-width: 200px;
    line-height: 1.8;
  }
  .discover-footer p > span {
    margin: 0 4px;
  }
  .discover-footer a {
    font-size: var(--font-label);
    gap: 3px;
    white-space: nowrap;
    line-height: 1.8;
  }
  .discover-footer a > svg {
    width: 10px;
    height: 10px;
  }
  .search-city-panel {
    padding: 14px;
    border-radius: var(--radius-surface);
  }
  .search-city-panel strong {
    font-size: var(--font-secondary);
  }
  .search-city-panel > p {
    font-size: var(--font-label);
    line-height: 1.8;
  }
  .search-city-options {
    gap: 7px;
  }
  .search-city-options > button {
    font-size: var(--font-secondary);
    padding: 12px 7px;
    gap: 4px;
  }
  .search-city-options > button > svg:last-child {
    width: 12px;
    height: 12px;
  }
}
@media (prefers-reduced-motion: reduce) {
  .discover-page {
    scroll-behavior: auto;
  }
  .destination-card,
.destination-photo > img,
.shortcut-icon {
    transition: none;
  }
}
.discover-shortcuts small {
  font-size: var(--font-label);
}
.discover-section-heading > div > p:last-child {
  font-size: var(--font-secondary);
}
.mood-filters > button {
  font-size: var(--font-secondary);
}
.companion-description {
  font-size: var(--font-secondary);
}
.map-invite-copy p,
.travel-map-invite > button {
  min-height: 44px;
  font-size: var(--font-secondary);
}
.discover-footer,
.discover-footer a {
  font-size: var(--font-label);
}
@media (max-width: 600px) {
  .hero-content h1 {
    font-size: var(--font-title);
  }
  .hero-description {
    font-size: var(--font-secondary);
    max-width: 260px;
  }
  .discover-hero {
    min-height: 355px;
  }
  .discovery-search input {
    font-size: var(--font-body);
    min-height: 44px;
  }
  .hero-suggestions button,
.hero-suggestions > span {
    font-size: var(--font-label);
    min-height: 44px;
  }
  .hero-suggestions {
    gap: 6px;
  }
  .hero-location {
    font-size: var(--font-label);
    bottom: 12px;
  }
  .discover-shortcuts strong {
    font-size: var(--font-label);
  }
  .discover-section-heading > div > p:last-child {
    font-size: var(--font-secondary);
  }
  .destination-title > span {
    font-size: var(--font-secondary);
  }
  .mood-filters > button {
    font-size: var(--font-label);
    min-height: 44px;
  }
  .more-destinations {
    min-height: 44px;
    min-width: 40px;
    height: 40px;
  }
  .map-invite-copy p,
.travel-map-invite > button {
    min-height: 44px;
    font-size: var(--font-label);
  }
  .companion-description {
    font-size: var(--font-secondary);
  }
  .discover-footer,
.discover-footer a {
    font-size: var(--font-label);
  }
  .discover-footer p {
    max-width: 205px;
  }
  .discovery-companion h2 {
    font-size: var(--font-section);
  }
}
.hero-description,
.discover-section-heading > div > p:last-child {
  color: var(--text-secondary);
}
.discover-shortcuts small {
  color: var(--text-secondary);
}
.mood-filters > button {
  color: var(--text-secondary);
}
.map-invite-copy p {
  color: var(--text-secondary);
}
.companion-description {
  color: var(--text-secondary);
}
.discover-footer,
.discover-footer a {
  color: var(--text-secondary);
}
.hero-suggestions button {
  min-height: 44px;
  color: var(--text-secondary);
}
.discovery-search input::placeholder {
  color: var(--text-secondary);
}
.discover-hero--immersive .hero-light {
  background: linear-gradient(90deg, #102c38b8 0%, #173a4866 42%, #173a4800 80%),
    linear-gradient(0deg, #132b3647, transparent 65%);
}
.discover-hero--immersive .hero-content h1 {
  color: #fffdf6;
  text-shadow: 0 2px 16px #172e3e26;
}
.discover-hero--immersive .hero-content h1 > span {
  color: var(--action);
}
.discover-hero--immersive .hero-description {
  color: #f4f8f2;
}
.discover-hero--immersive .hero-suggestions,
.discover-hero--immersive .hero-suggestions > span,
.discover-hero--immersive .hero-suggestions button {
  min-height: 44px;
  color: #f7fbf2;
}
.discover-hero--immersive .hero-suggestions i {
  background: #e4eee6;
}
@media (max-width: 600px) {
  .discover-hero--immersive .hero-light {
    background: linear-gradient(90deg, #122c39ba, #193c4666 65%, #1b3b453b),
      linear-gradient(0deg, #16323e55, transparent 70%);
  }
  .discover-hero--immersive .hero-location {
    color: #f3faf2;
  }
  .discover-hero--immersive .hero-location i {
    background: #daeadd;
  }
}
.discover-shortcuts {
  grid-template-columns: repeat(4,minmax(0,1fr));
  border: 0;
  background: transparent;
  box-shadow: none;
  margin: 24px 0 40px;
}
.discover-shortcuts > button {
  min-height: 64px;
  padding: 8px 12px;
  border-right: 0;
}
.discover-lower-grid {
  grid-template-columns: minmax(0,1fr);
}
.discovery-companion {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 28px 0;
  border: 0;
  border-top: 1px solid var(--border-subtle);
  border-radius: 0;
  background: transparent;
  box-shadow: none;
  flex-direction: row;
  min-width: 0;
  flex-wrap: wrap;
}
.discovery-companion h2 {
  font-size: var(--font-section);
  line-height: var(--line-heading);
  margin: 0;
}
.discovery-companion h2 br {
  display: none;
}
.discovery-companion p {
  flex: 1;
  margin: 0;
  font-size: var(--font-body);
  color: var(--text-secondary);
}
.destination-card {
  border: 0;
  border-radius: 0;
  background: transparent;
  box-shadow: none;
}
.destination-card:hover {
  transform: none;
  box-shadow: none;
}
.destination-card:focus-visible {
  outline-offset: 5px;
}
.destination-photo {
  border-radius: var(--radius-photo);
  aspect-ratio: 1.55;
}
.destination-content {
  padding: 18px 0 10px;
}
.destination-title {
  gap: 9px;
}
.destination-title > strong {
  font-size: var(--font-section);
  color: var(--text-primary);
}
.destination-title > span {
  font-size: var(--font-body);
  color: var(--text-secondary);
}
.hero-content h1 {
  font-size: var(--font-display);
  line-height: 1.2;
}
.hero-description {
  font-size: var(--font-body);
}
.discovery-search {
  border-color: var(--border-control);
  min-height: 56px;
  height: auto;
}
.discovery-search input {
  font-size: var(--font-body);
  min-height: 44px;
}
.search-go {
  min-width: 44px;
  min-height: 44px;
  background: var(--action);
}
.hero-light {
  background: linear-gradient(90deg,var(--canvas) 0%,#faf9f6df 27%,#faf9f645 52%,transparent 68%);
}
.discover-section-heading h2 {
  font-size: var(--font-title);
  color: var(--text-primary);
}
.hero-location {
  color: var(--text-body);
  background: #fffefbf2;
}
@media(max-width:899px) {
  .discovery-companion {
    flex-wrap: wrap;
    flex-direction: row;
    min-width: 0;
  }
  .discovery-companion p {
    flex-basis: 100%;
  }
  .discover-shortcuts {
    gap: 8px;
  }
  .shortcut-icon {
    width: 42px;
    height: 42px;
  }
  .discover-shortcuts > button {
    padding: 8px 4px;
  }
  .discover-shortcuts strong {
    font-size: var(--font-secondary);
  }
}
@media(max-width:600px) {
  .hero-content h1 {
    font-size: var(--font-display);
  }
  .hero-light {
    background: linear-gradient(90deg,#faf9f6f0,#faf9f685 70%,#faf9f640);
  }
  .hero-content {
    padding: 28px 22px;
  }
  .discover-shortcuts {
    margin: 20px 0 28px;
  }
  .shortcut-arrow {
    display: none;
  }
  .discover-shortcuts>button {
    flex-direction: column;
    gap: 9px;
  }
  .discover-section-heading h2 {
    font-size: var(--font-section);
  }
  .more-destinations {
    min-height: 44px;
    min-width: 44px;
    min-height: 44px;
  }
  .hero-suggestions {
    font-size: var(--font-label);
    gap: 2px 8px;
    flex-wrap: wrap;
  }
  .hero-suggestions>span,
.hero-suggestions>i {
    display: none;
  }
  .hero-suggestions button {
    min-height: 44px;
    min-height: 44px;
  }
  .destination-grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: 24px;
    margin-right: 0;
    padding-right: 0;
    overflow: visible;
    scroll-snap-type: none;
  }
  .destination-photo {
    aspect-ratio: 1.6;
  }
  .destination-content {
    padding-top: 14px;
  }
  .destination-title>strong {
    font-size: var(--font-section);
  }
  .discovery-companion h2 {
    font-size: var(--font-section);
  }
  .discover-container {
    width: calc(100% - 40px);
  }
}
@media(max-width:360px) {
  .discover-container {
    width: calc(100% - 32px);
  }
  .hero-content {
    padding-inline: 18px;
  }
  .discover-shortcuts strong {
    font-size: var(--font-label);
  }
}
</style>
