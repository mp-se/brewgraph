import { fileURLToPath, URL } from 'url';

import vue from '@vitejs/plugin-vue';
import { defineConfig, loadEnv } from 'vite';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const api = env.VITE_API_BASE ?? 'http://localhost:8080';
  return {
    // Root-absolute, not relative: the app is served from the host root and its
    // routes are path segments (/public/bottles, /public/:token). A relative base
    // made a page at /public/<anything> request /public/assets/*.js, which the SPA
    // fallback answers with index.html, so the page stayed blank.
    base: '/',
    plugins: [vue()],
    resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
    server: {
      port: 9002,
      // Anchored like the web nginx rule: a bare '/t' prefix would also swallow
      // '/theme.css' and send it to the API.
      proxy: {
        '^/(d|t|b)(/|$)': { target: api, changeOrigin: true },
      },
    },
    test: {
      environment: 'jsdom',
      globals: true,
      coverage: {
        provider: 'v8',
        include: ['src/**/*.{ts,vue}'],
        exclude: ['src/main.ts', 'src/**/*.d.ts'],
      },
    },
  };
});
