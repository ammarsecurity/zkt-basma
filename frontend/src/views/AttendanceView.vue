<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useDisplay } from 'vuetify'
import { api, downloadFile } from '../api'
import { notify } from '../snack'
import NavToggle from '../components/NavToggle.vue'

const { width } = useDisplay()
const totalVisible = computed(() => (width.value < 600 ? 4 : 7))

const PAGE_SIZE = 25
const devices = ref([])
const items = ref([])
const total = ref(0)
const present = ref(0)
const absent = ref(0)
const punchTotal = ref(0)
const page = ref(1)
const loading = ref(true)
const error = ref('')
const exporting = ref(false)
const exportingId = ref(null)

const filters = reactive({
  mode: 'day',
  date: localDate(),
  month: localMonth(),
  deviceId: '',
  q: '',
  status: 'all',
})

const deviceItems = computed(() => [
  { title: 'كل الأجهزة', value: '' },
  ...devices.value.map((device) => ({ title: device.name, value: device.id })),
])

const statusItems = [
  { title: 'الكل', value: 'all' },
  { title: 'حضر', value: 'present' },
  { title: 'لم يحضر', value: 'absent' },
]

const isMonth = computed(() => filters.mode === 'month')
const isDetail = computed(() => filters.mode === 'detail')

const filtered = computed(() =>
  filters.deviceId !== ''
  || filters.q.trim() !== ''
  || filters.status !== 'all',
)

const pageCount = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))

const rangeText = computed(() => {
  if (total.value === 0) return ''
  const start = (page.value - 1) * PAGE_SIZE + 1
  const end = Math.min(page.value * PAGE_SIZE, total.value)
  return `عرض ${latin(start)}–${latin(end)} من ${latin(total.value)}`
})

const summaryText = computed(() => {
  if (loading.value || error.value) return ''
  if (isDetail.value) return `${latin(punchTotal.value)} بصمة`
  return `حضر ${latin(present.value)} · لم يحضر ${latin(absent.value)}`
})

let requestId = 0
let searchTimer
let ignoreSearch = false

function latin(value) {
  return Number(value || 0).toLocaleString('en-US')
}

function localDate() {
  const now = new Date()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${now.getFullYear()}-${month}-${day}`
}

function localMonth() {
  return localDate().slice(0, 7)
}

function queryString(includePage) {
  const params = new URLSearchParams()
  if (filters.mode === 'detail') {
    params.set('month', filters.month)
  } else {
    params.set('mode', filters.mode)
    if (filters.mode === 'month') params.set('month', filters.month)
    else params.set('date', filters.date)
    if (filters.status !== 'all') params.set('status', filters.status)
  }
  if (filters.deviceId !== '' && filters.deviceId != null) params.set('device_id', String(filters.deviceId))
  if (filters.q.trim()) params.set('q', filters.q.trim())
  if (includePage) params.set('page', String(page.value))
  return params.toString()
}

function onPage(value) {
  page.value = value
  load()
}

async function loadDevices() {
  devices.value = await api('/api/devices')
}

async function load() {
  const current = ++requestId
  loading.value = true
  error.value = ''
  try {
    const path = filters.mode === 'detail' ? '/api/attendance/details' : '/api/attendance'
    const data = await api(`${path}?${queryString(true)}`)
    if (current !== requestId) return
    if (data.items.length === 0 && data.total > 0 && page.value > 1) {
      page.value = Math.max(1, Math.ceil(data.total / PAGE_SIZE))
      loading.value = false
      await load()
      return
    }
    items.value = data.items
    total.value = data.total
    present.value = data.present || 0
    absent.value = data.absent || 0
    punchTotal.value = data.punches || 0
  } catch (err) {
    if (current !== requestId) return
    error.value = err.message
  } finally {
    if (current === requestId) loading.value = false
  }
}

function apply() {
  page.value = 1
  load()
}

function setMode(mode) {
  if (filters.mode === mode) return
  filters.mode = mode
  apply()
}

function clearFilters() {
  ignoreSearch = true
  filters.deviceId = ''
  filters.q = ''
  filters.status = 'all'
  ignoreSearch = false
  apply()
}

async function exportEmployee(item) {
  exportingId.value = item.id
  try {
    const params = new URLSearchParams()
    params.set('month', filters.month)
    params.set('device_id', String(item.device_id))
    params.set('user_id', item.user_id)
    await downloadFile(`/api/attendance/details/export?${params}`, `تفاصيل_${item.user_id}.xlsx`)
    notify('تم تنزيل ملف الإكسل')
  } catch (err) {
    notify(err.message, 'error')
  } finally {
    exportingId.value = null
  }
}

async function exportExcel() {
  if (total.value === 0) return
  exporting.value = true
  try {
    const fallback = filters.mode === 'detail'
      ? 'تفاصيل_الشهر.xlsx'
      : (filters.mode === 'month' ? 'حضور_شهري.xlsx' : 'حضور.xlsx')
    const path = filters.mode === 'detail' ? '/api/attendance/details/export' : '/api/attendance/export'
    await downloadFile(`${path}?${queryString(false)}`, fallback)
    notify('تم تنزيل ملف الإكسل')
  } catch (err) {
    notify(err.message, 'error')
  } finally {
    exporting.value = false
  }
}

watch(() => filters.q, () => {
  if (ignoreSearch) return
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    page.value = 1
    load()
  }, 300)
})

onMounted(async () => {
  try {
    await loadDevices()
  } catch (err) {
    error.value = err.message
  }
  await load()
})
</script>

<template>
  <div class="page">
    <div class="stack">
      <header class="page-head">
        <div class="title-with-nav">
          <NavToggle />
          <h1 class="page-title">الحضور</h1>
        </div>
        <p v-if="summaryText" class="page-count">{{ summaryText }}</p>
      </header>

      <v-card class="app-card filter-card">
        <div class="filters attendance-filters">
          <div class="field">
            <label class="field-label">الفترة</label>
            <div class="mode-switch" role="group" aria-label="نوع التقرير">
              <button type="button" :class="{ active: !isMonth && !isDetail }" @click="setMode('day')">يوم</button>
              <button type="button" :class="{ active: isMonth }" @click="setMode('month')">شهر</button>
              <button type="button" :class="{ active: isDetail }" @click="setMode('detail')">تفاصيل</button>
            </div>
          </div>
          <div v-if="filters.mode === 'day'" class="field">
            <label class="field-label" for="attendance-date">التاريخ</label>
            <v-text-field
              id="attendance-date"
              v-model="filters.date"
              type="date"
              hide-details
              @change="apply"
            />
          </div>
          <div v-else class="field">
            <label class="field-label" for="attendance-month">الشهر</label>
            <v-text-field
              id="attendance-month"
              v-model="filters.month"
              type="month"
              hide-details
              @change="apply"
            />
          </div>
          <div class="field">
            <label class="field-label" for="attendance-device">الجهاز</label>
            <v-select
              id="attendance-device"
              v-model="filters.deviceId"
              :items="deviceItems"
              item-title="title"
              item-value="value"
              hide-details
              @update:model-value="apply"
            />
          </div>
          <div v-if="!isDetail" class="field">
            <label class="field-label" for="attendance-status">الحالة</label>
            <v-select
              id="attendance-status"
              v-model="filters.status"
              :items="statusItems"
              item-title="title"
              item-value="value"
              hide-details
              @update:model-value="apply"
            />
          </div>
          <div class="field">
            <label class="field-label" for="attendance-query">الموظف</label>
            <v-text-field
              id="attendance-query"
              v-model="filters.q"
              placeholder="الاسم أو الرقم"
              prepend-inner-icon="search"
              hide-details
              autocomplete="off"
              @keydown.enter.prevent="apply"
            />
          </div>
          <div class="filter-actions">
            <v-btn
              color="primary"
              :loading="exporting"
              :disabled="loading || total === 0 || Boolean(error)"
              @click="exportExcel"
            >
              <span class="material-symbols-rounded">download</span>
              تصدير
            </v-btn>
            <v-btn v-if="filtered" variant="text" @click="clearFilters">مسح</v-btn>
          </div>
        </div>
      </v-card>

      <v-card class="app-card sheet">
        <div v-if="loading" class="skeleton" aria-hidden="true">
          <div v-for="row in 8" :key="row" class="skeleton-row">
            <span class="sk"></span>
            <span class="sk"></span>
            <span class="sk"></span>
            <span class="sk"></span>
            <span class="sk"></span>
            <span class="sk"></span>
          </div>
        </div>

        <div v-else-if="error" class="state-block">
          <h2>تعذر تحميل الحضور</h2>
          <p>{{ error }}</p>
          <v-btn color="primary" @click="load">إعادة المحاولة</v-btn>
        </div>

        <div v-else-if="items.length === 0" class="state-block">
          <template v-if="devices.length === 0">
            <h2>لا توجد أجهزة بعد</h2>
            <p>أضف جهازاً من صفحة الأجهزة، ثم اسحب البصمات حتى يظهر الحضور هنا.</p>
            <v-btn color="primary" to="/devices">الانتقال إلى الأجهزة</v-btn>
          </template>
          <template v-else-if="filtered">
            <h2>لا توجد نتائج</h2>
            <p>لا يوجد موظف مطابق للفلتر الحالي.</p>
            <v-btn variant="outlined" @click="clearFilters">مسح الفلاتر</v-btn>
          </template>
          <template v-else>
            <h2>لا يوجد موظفون</h2>
            <p>أضف الموظفين من صفحة الموظفين، أو حدّثهم من الجهاز.</p>
            <v-btn color="primary" to="/employees">الانتقال إلى الموظفين</v-btn>
          </template>
        </div>

        <template v-else>
          <div v-if="isDetail" class="detail-list">
            <article v-for="item in items" :key="item.id" class="detail-block">
              <header class="detail-head">
                <div>
                  <strong>{{ item.employee_name || '—' }}</strong>
                  <span class="num muted">{{ item.user_id }} · {{ item.device_name }}</span>
                </div>
                <div class="detail-actions">
                  <p class="detail-count">{{ latin(item.punches) }} بصمة</p>
                  <v-btn
                    size="small"
                    variant="outlined"
                    :loading="exportingId === item.id"
                    :disabled="exportingId != null && exportingId !== item.id"
                    @click="exportEmployee(item)"
                  >
                    تصدير
                  </v-btn>
                </div>
              </header>
              <p v-if="item.days.length === 0" class="detail-empty">لا توجد بصمات في هذا الشهر.</p>
              <div v-else class="table-scroll detail-scroll">
                <table class="data-table detail-table">
                  <thead>
                    <tr>
                      <th scope="col">اليوم</th>
                      <th scope="col">التاريخ</th>
                      <th scope="col">البصمات</th>
                      <th scope="col">فرق الوقت</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="day in item.days" :key="day.date">
                      <td>{{ day.weekday }}</td>
                      <td><span class="num">{{ day.date }}</span></td>
                      <td>
                        <span v-for="(time, index) in day.times" :key="index" class="punch-time num">{{ time }}</span>
                      </td>
                      <td><span class="num">{{ day.gap || '—' }}</span></td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </article>
          </div>
          <div v-else class="table-scroll">
            <table class="data-table attendance-table" aria-label="ملخص الحضور">
              <thead>
                <tr>
                  <th scope="col">اسم الموظف</th>
                  <th scope="col">رقم الموظف</th>
                  <th scope="col">الجهاز</th>
                  <th v-if="isMonth" scope="col">أيام الحضور</th>
                  <th scope="col">أول بصمة</th>
                  <th scope="col">آخر بصمة</th>
                  <th v-if="!isMonth" scope="col">الحالة</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in items" :key="item.id">
                  <td>{{ item.employee_name || '—' }}</td>
                  <td><span class="num">{{ item.user_id }}</span></td>
                  <td>{{ item.device_name }}</td>
                  <td v-if="isMonth"><span class="num">{{ latin(item.days) }}</span></td>
                  <td><span class="num">{{ item.first_at || '—' }}</span></td>
                  <td><span class="num">{{ item.last_at || '—' }}</span></td>
                  <td v-if="!isMonth">
                    <span class="status-pill" :data-kind="item.present ? 'ok' : 'idle'">
                      {{ item.present ? 'حضر' : 'لم يحضر' }}
                    </span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="pager">
            <p class="range">{{ rangeText }}</p>
            <v-pagination
              v-if="pageCount > 1"
              v-model="page"
              :length="pageCount"
              :total-visible="totalVisible"
              density="comfortable"
              rounded="lg"
              @update:model-value="onPage"
            />
          </div>
        </template>
      </v-card>
    </div>
  </div>
</template>
