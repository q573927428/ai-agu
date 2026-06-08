// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  compatibilityDate: "2025-04-01",
  devtools: { enabled: true },

  // Modules
  modules: ["@element-plus/nuxt"],

  // App config
  app: {
    head: {
      title: "A股量化选股平台",
      meta: [
        { charset: "utf-8" },
        { name: "viewport", content: "width=device-width, initial-scale=1" },
        { name: "description", content: "基于LightGBM的A股量化选股系统" },
      ],
    },
  },

  // Runtime config
  runtimeConfig: {
    public: {
      apiBase: process.env.NUXT_PUBLIC_API_BASE || "http://localhost:8000",
    },
  },

  // CSS
  css: ["~/assets/css/main.css"],

  // TypeScript
  typescript: {
    strict: true,
    shim: false,
  },

  // Element Plus
  elementPlus: {
    icon: "ElIcon",
    importStyle: "scss",
  },

  // Vite configuration
  vite: {
    optimizeDeps: {
      include: [
        "@element-plus/icons-vue",
        "dayjs",
        "dayjs/plugin/*.js",
        "echarts/core",
        "echarts/charts",
        "echarts/components",
        "echarts/renderers",
        "vue-echarts",
        'lodash-unified'
      ],
    },
  },

  // Nitro server config
  nitro: {
    preset: "node-server",
  },
});
