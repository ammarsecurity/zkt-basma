<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useDisplay } from 'vuetify'
import { api, downloadLogs } from '../api'
import { notify } from '../snack'
import NavToggle from '../components/NavToggle.vue'

const { width } = useDisplay()
const totalVisible = computed(() => (width.value < 600 ? 4 : 7))

const PAGE_SIZE = 25
const devices = ref([])
const items = ref([])
const total = ref(0)
const page = ref(1)
const loading = ref(true)
const error = ref('')
const exporting = ref(false)

const filters = reactive({
  deviceId: '',
  q: '',
  dateFrom: '',
  dateTo: '',
})
const dateError = ref('')

const deviceItems = computed(() => [
  { title: 'كل الأجهزة', value: '' },
  ...devices.value.map((device) => ({ title: device.name, value: device.id })),
])

const filtered = computed(() =>
  filters.deviceId !== ''
  || filters.q.trim() !== ''
  || filters.dateFrom !== ''
  || filters.dateTo !== '',
)

const pageCount = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))

const rangeText = computed(() => {
  if (total.value === 0) return ''
  const start = (page.value - 1) * PAGE_SIZE + 1
  const end = Math.min(page.value * PAGE_SIZE, total.value)
  return `عرض ${latin(start)}–${latin(end)} من ${latin(total.value)}`
})

const totalText = computed(() => `${latin(total.value)} بصمة`)

let requestId = 0
let searchTimer
let ignoreSearch = false

function latin(value) {
  return Number(value || 0).toLocaleString('en-US')
}

function queryString(includePage) {
  const params = new URLSearchParams()
  if (filters.deviceId !== '' && filters.deviceId != null) params.set('device_id', String(filters.deviceId))
  if (filters.q.trim()) params.set('q', filters.q.trim())
  if (filters.dateFrom) params.set('date_from', filters.dateFrom)
  if (filters.dateTo) params.set('date_to', filters.dateTo)
  if (includePage) params.set('page', String(page.value))
  return params.toString()
}

function datesValid() {
  if (filters.dateFrom && filters.dateTo && filters.dateFrom > filters.dateTo) {
    dateError.value = 'تاريخ البداية بعد تاريخ النهاية'
    return false
  }
  dateError.value = ''
  return true
}

function onPage(value) {
  page.value = value
  load()
}

async function loadDevices() {
  devices.value = await api('/api/devices')
}

async function load() {
  if (!datesValid()) return
  const current = ++requestId
  loading.value = true
  error.value = ''
  try {
    const data = await api(`/api/logs?${queryString(true)}`)
    if (current !== requestId) return
    if (data.items.length === 0 && data.total > 0 && page.value > 1) {
      page.value = Math.max(1, Math.ceil(data.total / PAGE_SIZE))
      loading.value = false
      await load()
      return
    }
    items.value = data.items
    total.value = data.total
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

function clearFilters() {
  ignoreSearch = true
  filters.deviceId = ''
  filters.q = ''
  filters.dateFrom = ''
  filters.dateTo = ''
  ignoreSearch = false
  apply()
}

async function exportExcel() {
  if (!datesValid() || total.value === 0) return
  exporting.value = true
  try {
    await downloadLogs(queryString(false))
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
          <h1 class="page-title">البصمات</h1>
        </div>
        <p v-if="!loading && !error" class="page-count">{{ totalText }}</p>
      </header>

      <v-card class="app-card filter-card">
        <div class="filters">
          <div class="field">
            <label class="field-label" for="filter-device">الجهاز</label>
            <v-select
              id="filter-device"
              v-model="filters.deviceId"
              :items="deviceItems"
              item-title="title"
              item-value="value"
              hide-details
              @update:model-value="apply"
            />
          </div>
          <div class="field">
            <label class="field-label" for="filter-query">الموظف</label>
            <v-text-field
              id="filter-query"
              v-model="filters.q"
              placeholder="الاسم أو الرقم"
              prepend-inner-icon="search"
              hide-details
              autocomplete="off"
              @keydown.enter.prevent="apply"
            />
          </div>
          <div class="field">
            <label class="field-label" for="filter-from">من تاريخ</label>
            <v-text-field
              id="filter-from"
              v-model="filters.dateFrom"
              type="date"
              hide-details
              @change="apply"
            />
          </div>
          <div class="field">
            <label class="field-label" for="filter-to">إلى تاريخ</label>
            <v-text-field
              id="filter-to"
              v-model="filters.dateTo"
              type="date"
              hide-details
              @change="apply"
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
        <p v-if="dateError" class="date-error">{{ dateError }}</p>
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
          <h2>تعذر تحميل البصمات</h2>
          <p>{{ error }}</p>
          <v-btn color="primary" @click="load">إعادة المحاولة</v-btn>
        </div>

        <div v-else-if="items.length === 0" class="state-block">
          <template v-if="devices.length === 0">
            <h2>لا توجد أجهزة بعد</h2>
            <p>أضف جهازاً من صفحة الأجهزة، ثم اسحب البصمات حتى تظهر هنا.</p>
            <v-btn color="primary" to="/devices">الانتقال إلى الأجهزة</v-btn>
          </template>
          <template v-else-if="filtered">
            <h2>لا توجد نتائج</h2>
            <p>لا توجد بصمات مطابقة للفلتر الحالي.</p>
            <v-btn variant="outlined" @click="clearFilters">مسح الفلاتر</v-btn>
          </template>
          <template v-else>
            <h2>لا توجد بصمات بعد</h2>
            <p>اسحب السجلات من صفحة الأجهزة حتى تتعبأ هذه القائمة.</p>
            <v-btn color="primary" to="/devices">الانتقال إلى الأجهزة</v-btn>
          </template>
        </div>

        <template v-else>
          <div class="table-scroll">
            <table class="data-table logs-table" aria-label="سجلات البصمات">
              <thead>
                <tr>
                  <th scope="col">اسم الموظف</th>
                  <th class="col-optional" scope="col">رقم الموظف</th>
                  <th scope="col">التاريخ</th>
                  <th scope="col">اليوم</th>
                  <th scope="col">الوقت</th>
                  <th class="col-optional" scope="col">الجهاز</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in items" :key="item.id">
                  <td>{{ item.employee_name || '—' }}</td>
                  <td class="col-optional"><span class="num">{{ item.user_id }}</span></td>
                  <td><span class="num">{{ item.date }}</span></td>
                  <td>{{ item.weekday }}</td>
                  <td><span class="num">{{ item.time }}</span></td>
                  <td class="col-optional">{{ item.device_name }}</td>
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
