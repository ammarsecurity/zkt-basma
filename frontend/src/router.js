import { createRouter, createWebHistory } from 'vue-router'
import DashboardView from './views/DashboardView.vue'
import DevicesView from './views/DevicesView.vue'
import EmployeesView from './views/EmployeesView.vue'
import LogsView from './views/LogsView.vue'
import AboutView from './views/AboutView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'dashboard', component: DashboardView, meta: { title: 'الإحصائيات' } },
    { path: '/devices', name: 'devices', component: DevicesView, meta: { title: 'الأجهزة' } },
    { path: '/employees', name: 'employees', component: EmployeesView, meta: { title: 'الموظفون' } },
    { path: '/logs', name: 'logs', component: LogsView, meta: { title: 'البصمات' } },
    { path: '/about', name: 'about', component: AboutView, meta: { title: 'عن المبرمج' } },
  ],
})

router.afterEach((to) => {
  document.title = to.meta.title ? `${to.meta.title} · بصمة ZKTeco` : 'بصمة ZKTeco'
})

export default router
