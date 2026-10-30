<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../api'
import { notify } from '../snack'
import NavToggle from '../components/NavToggle.vue'

const loading = ref(true)
const error = ref('')
const key = ref('')
const baseUrls = ref([])
const renewing = ref(false)
const confirmOpen = ref(false)

const routes = [
  { method: 'GET', path: '/devices', text: 'الأجهزة المحفوظة، بدون كلمة مرور الاتصال' },
  { method: 'GET', path: '/employees', text: 'الموظفون. الفلاتر: device_id و q و finger و page' },
  { method: 'GET', path: '/logs', text: 'البصمات. الفلاتر: device_id و q و date_from و date_to و page' },
  { method: 'GET', path: '/attendance', text: 'ملخص يوم. الفلاتر: date و device_id و q و status و page' },
  { method: 'GET', path: '/attendance/details', text: 'تفاصيل شهر. الفلاتر: month و device_id و user_id و q و page' },
  { method: 'POST', path: '/devices/{id}/employees', text: 'إضافة موظف. الجسم: {"name","user_id"}' },
  { method: 'POST', path: '/devices/{id}/sync', text: 'سحب البصمات من الجهاز إلى هذا النظام' },
]

const baseUrl = () => baseUrls.value[0] || 'http://127.0.0.1:8000/api/v1'

const readExample = () => `curl -H "X-API-Key: ${key.value}" "${baseUrl()}/logs"`

const writeExample = () =>
  `curl -X POST -H "X-API-Key: ${key.value}" -H "Content-Type: application/json" -d '{"name":"Ali","user_id":"15"}' "${baseUrl()}/devices/2/employees"`

async function load() {
  loading.value = true
  error.value = ''
  try {
    const data = await api('/api/integration')
    key.value = data.key
    baseUrls.value = data.base_urls || []
  } catch (err) {
    error.value = err.message
  } finally {
    loading.value = false
  }
}

async function copy(text) {
  try {
    await navigator.clipboard.writeText(text)
    notify('تم النسخ')
  } catch {
    notify('تعذر النسخ. حدّد النص وانسخه يدوياً', 'error')
  }
}

async function regenerate() {
  renewing.value = true
  try {
    const data = await api('/api/integration/regenerate', { method: 'POST' })
    key.value = data.key
    baseUrls.value = data.base_urls || []
    confirmOpen.value = false
    notify('تم تجديد المفتاح')
  } catch (err) {
    notify(err.message, 'error')
  } finally {
    renewing.value = false
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
          <h1 class="page-title">الربط</h1>
        </div>
      </header>

      <div v-if="loading" class="app-card">
        <div class="skeleton" aria-hidden="true">
          <div v-for="row in 4" :key="row" class="skeleton-row"><span class="sk"></span></div>
        </div>
      </div>

      <div v-else-if="error" class="app-card">
        <div class="state-block">
          <h2>تعذر تحميل مفتاح الربط</h2>
          <p>{{ error }}</p>
          <v-btn color="primary" @click="load">إعادة المحاولة</v-btn>
        </div>
      </div>

      <template v-else>
        <v-card class="app-card dev-card">
          <h2 class="card-title">مفتاح الربط</h2>
          <p class="dev-note">أرسِله في الترويسة <span class="code-inline" dir="ltr">X-API-Key</span>. لا تشاركه إلا مع النظام الذي تريد ربطه. تجديد المفتاح يوقف المفتاح القديم فوراً.</p>
          <div class="dev-key-row">
            <input class="dev-key" dir="ltr" readonly :value="key" aria-label="مفتاح الربط" />
            <v-btn variant="outlined" @click="copy(key)">نسخ</v-btn>
            <v-btn variant="text" color="error" @click="confirmOpen = true">تجديد</v-btn>
          </div>
        </v-card>

        <v-card class="app-card dev-card">
          <h2 class="card-title">عنوان الربط</h2>
          <p class="dev-note">الحاسبة لازم تبقى شغالة، والمنفذ 8000 مفتوح للسيرفر الثاني من الجدار الناري أو موجّه الشبكة. افتح هذه الواجهة من <span class="code-inline" dir="ltr">127.0.0.1</span> فقط.</p>
          <ul class="dev-urls">
            <li v-for="url in baseUrls" :key="url">
              <code dir="ltr">{{ url }}</code>
              <v-btn size="small" variant="text" @click="copy(url)">نسخ</v-btn>
            </li>
          </ul>
        </v-card>

        <v-card class="app-card dev-card">
          <h2 class="card-title">المسارات</h2>
          <div class="table-scroll detail-scroll">
            <table class="data-table dev-table">
              <thead>
                <tr>
                  <th scope="col">الطريقة</th>
                  <th scope="col">المسار</th>
                  <th scope="col">العمل</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="route in routes" :key="route.method + route.path">
                  <td><span class="method-pill">{{ route.method }}</span></td>
                  <td><code dir="ltr">{{ route.path }}</code></td>
                  <td>{{ route.text }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p class="dev-note">المفتاح الخاطئ يرجع 401. إذا تعذر الوصول إلى جهاز البصمة يرجع 502.</p>
        </v-card>

        <v-card class="app-card dev-card">
          <h2 class="card-title">أمثلة</h2>
          <p class="field-label">قراءة البصمات</p>
          <pre class="code-block" dir="ltr">{{ readExample() }}</pre>
          <div class="dev-copy">
            <v-btn size="small" variant="text" @click="copy(readExample())">نسخ</v-btn>
          </div>
          <p class="field-label">إضافة موظف</p>
          <pre class="code-block" dir="ltr">{{ writeExample() }}</pre>
          <div class="dev-copy">
            <v-btn size="small" variant="text" @click="copy(writeExample())">نسخ</v-btn>
          </div>
        </v-card>
      </template>
    </div>

    <v-dialog :model-value="confirmOpen" max-width="440" :persistent="renewing" @update:model-value="(open) => { if (!open && !renewing) confirmOpen = false }">
      <v-card class="dialog-card">
        <h2>تجديد المفتاح</h2>
        <p>المفتاح الحالي يتوقف فوراً. النظام الخارجي يحتاج المفتاح الجديد حتى يكمل الربط.</p>
        <div class="dialog-actions">
          <v-btn color="error" :loading="renewing" @click="regenerate">تجديد</v-btn>
          <v-btn variant="text" :disabled="renewing" @click="confirmOpen = false">إلغاء</v-btn>
        </div>
      </v-card>
    </v-dialog>
  </div>
</template>
