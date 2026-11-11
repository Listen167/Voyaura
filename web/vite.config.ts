import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    vue(),
    VitePWA({
      registerType: 'autoUpdate',
      manifest: {
        name: 'Voyaura',
        short_name: 'Voyaura',
        description: 'Plan the journey. Shape the story.',
        theme_color: '#e9583e',
        background_color: '#f3efe7',
        display: 'standalone',
        start_url: '/',
        icons: [
          { src: '/voyaura-mark.svg', sizes: 'any', type: 'image/svg+xml', purpose: 'any maskable' },
        ],
      },
    }),
  ],
})
