<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'
import NavToggle from '../components/NavToggle.vue'

const stats = ref(null)
const loading = ref(true)
const error = ref('')

const cards = computed(() => {
  const data = stats.value
  if (!data) return []
  return [
    {
      label: 'الأجهزة',
      value: data.devices,
      hint: data.devices ? `${latin(data.synced_ok)} تم سحبها بنجاح` : 'لم يُضف جهاز بعد',
      to: '/devices',
    },
    {
      label: 'الموظفون',
      value: data.employees,
      hint: data.unnamed ? `${latin(data.unnamed)} بدون اسم` : 'الأسماء مكتملة',
      to: '/employees',
    },
    {
      label: 'البصمات',
      value: data.punches,
      hint: `هذا الشهر ${latin(data.month_punches)}`,
      to: '/logs',
    },
    {
      label: 'بصمات اليوم',
      value: data.today_punches,
      hint: data.weekday,
      to: '/logs',
    },
    {
      label: 'آخر 7 أيام',
      value: data.week_punches,
      hint: `من ${data.week_from}`,
      to: '/logs',
    },
    {
      label: 'هذا الشهر',
      value: data.month_punches,
      hint: `من ${data.month_from}`,
      to: '/logs',
    },
  ]
})

function latin(value) {
  return Number(value || 0).toLocaleString('en-US')
}

function statusKind(device) {
  if (!device.ever_synced && !device.last_status) return 'idle'
  return device.last_ok ? 'ok' : 'bad'
}

function statusText(device) {
  if (!device.ever_synced && !device.last_status) return 'بانتظار السحب'
  return device.last_ok ? 'تم السحب' : 'فشل السحب'
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    stats.value = await api('/api/stats')
  } catch (err) {
    error.value = err.message
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="page">
    <div class="stack">
      <header class="page-head">
        <div class="title-with-nav">
          <NavToggle />
          <h1 class="page-title">الإحصائيات</h1>
        </div>
        <p v-if="stats" class="page-count">{{ stats.weekday }} {{ stats.today }}</p>
      </header>

      <div v-if="loading" class="stat-grid" aria-hidden="true">
        <div v-for="item in 6" :key="item" class="stat-card stat-skeleton">
          <span class="sk sk-line"></span>
          <span class="sk sk-value"></span>
          <span class="sk sk-line"></span>
        </div>
      </div>

      <div v-else-if="error" class="app-card">
        <div class="state-block">
          <h2>تعذر تحميل الإحصائيات</h2>
          <p>{{ error }}</p>
          <v-btn color="primary" @click="load">إعادة المحاولة</v-btn>
        </div>
      </div>

      <template v-else>
        <section class="stat-grid" aria-label="ملخص الأرقام">
          <router-link v-for="card in cards" :key="card.label" class="stat-card" :to="card.to">
            <span class="stat-label">{{ card.label }}</span>
            <strong class="stat-value num">{{ latin(card.value) }}</strong>
            <span class="stat-hint">{{ card.hint }}</span>
          </router-link>
        </section>

        <section class="dash-split">
          <v-card class="app-card">
            <div class="table-head">
              <h2 class="card-title">آخر 7 أيام</h2>
              <p>{{ latin(stats.week_punches) }} بصمة</p>
            </div>
            <div class="bars" role="img" :aria-label="`بصمات آخر 7 أيام: ${latin(stats.week_punches)}`">
              <div v-for="day in stats.days" :key="day.date" class="bar-col">
                <span class="bar-value num">{{ latin(day.count) }}</span>
                <div class="bar-track">
                  <div class="bar-fill" :class="{ has: day.count > 0 }" :style="{ height: `${day.share}%` }"></div>
                </div>
                <span class="bar-label">{{ day.weekday }}</span>
                <span class="bar-date num">{{ day.date.slice(0, 5) }}</span>
              </div>
            </div>
          </v-card>

          <v-card class="app-card">
            <div class="table-head">
              <h2 class="card-title">حسب الجهاز</h2>
            </div>
            <div v-if="stats.by_device.length === 0" class="state-block compact">
              <h2>لا توجد أجهزة</h2>
              <p>أضف جهازاً حتى تظهر بصماته هنا.</p>
              <v-btn color="primary" to="/devices">إضافة جهاز</v-btn>
            </div>
            <ul v-else class="meter">
              <li v-for="device in stats.by_device" :key="device.id">
                <div class="meter-top">
                  <strong>{{ device.name }}</strong>
                  <span class="num">{{ latin(device.punches) }}</span>
                </div>
                <div class="meter-track">
                  <div class="meter-fill" :style="{ width: `${device.share}%` }"></div>
                </div>
                <p class="meter-meta">
                  <span>{{ latin(device.employees) }} موظف</span>
                  <span class="status-pill" :data-kind="statusKind(device)">{{ statusText(device) }}</span>
                </p>
              </li>
            </ul>
          </v-card>
        </section>

        <v-card class="app-card sheet">
          <div class="table-head">
            <h2 class="card-title">آخر البصمات</h2>
            <router-link class="text-link" to="/logs">كل البصمات</router-link>
          </div>

          <div v-if="stats.recent.length === 0" class="state-block compact">
            <h2>لا توجد بصمات بعد</h2>
            <p>اسحب السجلات من صفحة الأجهزة حتى تظهر هنا.</p>
            <v-btn color="primary" to="/devices">الانتقال إلى الأجهزة</v-btn>
          </div>

          <div v-else class="table-scroll">
            <table class="data-table" aria-label="آخر البصمات">
              <thead>
                <tr>
                  <th scope="col">اسم الموظف</th>
                  <th scope="col">رقم الموظف</th>
                  <th scope="col">التاريخ</th>
                  <th scope="col">اليوم</th>
                  <th scope="col">الوقت</th>
                  <th scope="col">الجهاز</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in stats.recent" :key="item.id">
                  <td>{{ item.employee_name || '—' }}</td>
                  <td><span class="num">{{ item.user_id }}</span></td>
                  <td><span class="num">{{ item.date }}</span></td>
                  <td>{{ item.weekday }}</td>
                  <td><span class="num">{{ item.time }}</span></td>
                  <td>{{ item.device_name }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </v-card>
      </template>
    </div>
  </div>
</template>
