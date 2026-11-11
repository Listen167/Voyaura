<script setup lang="ts">
import { BookImage, Map, Route, Sparkles, UserRound } from 'lucide-vue-next'
import type { Component } from 'vue'
import type { AppView } from '../types'

defineProps<{ activeView: AppView }>()
const emit = defineEmits<{ select: [view: AppView] }>()

const items: Array<{ id: AppView; label: string; icon: Component }> = [
  { id: 'map', label: '地图', icon: Map },
  { id: 'journeys', label: '行程', icon: Route },
  { id: 'memories', label: '记忆', icon: BookImage },
  { id: 'studio', label: '创作', icon: Sparkles },
  { id: 'profile', label: '我的', icon: UserRound },
]
</script>

<template>
  <nav class="app-nav" aria-label="主要导航">
    <button
      v-for="item in items"
      :key="item.id"
      class="nav-item"
      :class="{ active: activeView === item.id }"
      :aria-current="activeView === item.id ? 'page' : undefined"
      :title="item.label"
      type="button"
      @click="emit('select', item.id)"
    >
      <component :is="item.icon" :size="21" :stroke-width="1.8" />
      <span>{{ item.label }}</span>
    </button>
  </nav>
</template>
