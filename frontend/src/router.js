import { createRouter, createWebHistory } from 'vue-router'
import DevicesView from './views/DevicesView.vue'
import LogsView from './views/LogsView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/devices' },
    { path: '/devices', name: 'devices', component: DevicesView, meta: { title: 'الأجهزة' } },
    { path: '/logs', name: 'logs', component: LogsView, meta: { title: 'البصمات' } },
  ],
})

router.afterEach((to) => {
  document.title = to.meta.title ? `${to.meta.title} · بصمة ZKTeco` : 'بصمة ZKTeco'
})

export default router
