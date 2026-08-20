import { fileURLToPath, URL } from 'node:url'

import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueJsx from '@vitejs/plugin-vue-jsx'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'
import { compression } from 'vite-plugin-compression2'

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const ENV = loadEnv(mode, process.cwd(), '')
  const devProxyTarget = ENV.VITE_DEV_PROXY_TARGET || 'http://127.0.0.1:5001'
  const googleSiteVerification = (
    process.env.VITE_GOOGLE_SITE_VERIFICATION ||
    ENV.VITE_GOOGLE_SITE_VERIFICATION ||
    ''
  ).trim()

  return {
    base: './',
    envPrefix: ['VITE', 'VUE'],
    plugins: [
      {
        name: 'google-site-verification',
        transformIndexHtml() {
          if (!googleSiteVerification) return

          return [
            {
              tag: 'meta',
              attrs: {
                name: 'google-site-verification',
                content: googleSiteVerification
              },
              injectTo: 'head'
            }
          ]
        }
      },
      vue(),
      vueJsx(),
      AutoImport({
        resolvers: [ElementPlusResolver()]
      }),
      Components({
        resolvers: [ElementPlusResolver()]
      }),
      compression({ threshold: 10240 })
    ],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url))
      }
    },
    server: {
      host: '0.0.0.0',
      port: 8080,
      strictPort: true,
      open: false,
      proxy: {
        '/api': {
          target: devProxyTarget,
          changeOrigin: true,
          rewrite: path => path
        }
      }
    },
    build: {
      outDir: '../static/dist',
      emptyOutDir: true
    }
  }
})
