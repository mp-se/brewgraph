import { createApp } from 'vue';
import { createRouter, createWebHistory } from 'vue-router';

import App from './App.vue';
import BottleListView from './pages/BottleListView.vue';
import TapListView from './pages/TapListView.vue';
import { themeStylesheetUrl } from './lib/publicDisplay';
import './styles.css';

// Deployment branding hook: theme.css is appended after the built-in styles so
// its rules win. It ships empty; see public/theme.css.
const theme = document.createElement('link');
theme.rel = 'stylesheet';
theme.href = themeStylesheetUrl(import.meta.url);
document.head.appendChild(theme);

const tokenProps = (route: { params: Record<string, unknown> }) => ({
  token: typeof route.params.token === 'string' ? route.params.token : undefined,
});

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/public', component: TapListView },
    { path: '/public/bottles', component: BottleListView },
    { path: '/public/:token/bottles', component: BottleListView, props: tokenProps },
    { path: '/public/:token', component: TapListView, props: tokenProps },
    { path: '/', redirect: '/public' },
    { path: '/:catchAll(.*)', redirect: '/public' },
  ],
});

createApp(App).use(router).mount('#app');
