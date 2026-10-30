<script setup>
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { useDisplay } from 'vuetify'
import { api } from '../api'
import { notify } from '../snack'
import NavToggle from '../components/NavToggle.vue'

const { width } = useDisplay()
const totalVisible = computed(() => (width.value < 600 ? 4 : 7))
const PAGE_SIZE = 25

const devices = ref([])
const employees = ref([])
const total = ref(0)
const page = ref(1)
const loading = ref(true)
const error = ref('')
const saving = ref(false)
const deleting = ref(false)
const refreshing = ref(false)
const formOpen = ref(false)
const pendingDelete = ref(null)
const fingerEmployee = ref(null)
const editingUserId = ref(null)
const nameField = ref(null)

const filters = reactive({
  deviceId: '',
  q: '',
  finger: 'all',
})

const fingerItems = [
  { title: 'كل البصمات', value: 'all' },
  { title: 'بدون بصمة', value: 'none' },
  { title: 'مسجّلة', value: 'enrolled' },
]

const form = reactive({
  deviceId: null,
  name: '',
  userId: '',
})

const fieldErrors = reactive({
  name: '',
  userId: '',
  device: '',
})

const deviceItems = computed(() => [
  { title: 'كل الأجهزة', value: '' },
  ...devices.value.map((device) => ({ title: device.name, value: device.id })),
])

const formDevices = computed(() =>
  devices.value.map((device) => ({ title: device.name, value: device.id })),
)

const editing = computed(() => editingUserId.value != null)
const formTitle = computed(() => (editing.value ? 'تعديل الموظف' : 'إضافة موظف'))
const filtered = computed(() => filters.deviceId !== '' || filters.q.trim() !== '' || filters.finger !== 'all')
const pageCount = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))

const rangeText = computed(() => {
  if (total.value === 0) return ''
  const start = (page.value - 1) * PAGE_SIZE + 1
  const end = Math.min(page.value * PAGE_SIZE, total.value)
  return `عرض ${latin(start)}–${latin(end)} من ${latin(total.value)}`
})

const totalText = computed(() => `${latin(total.value)} موظف`)

let requestId = 0
let searchTimer
let ignoreSearch = false

function latin(value) {
  return Number(value || 0).toLocaleString('en-US')
}

function resetErrors() {
  fieldErrors.name = ''
  fieldErrors.userId = ''
  fieldErrors.device = ''
}

function queryString() {
  const params = new URLSearchParams()
  if (filters.deviceId !== '' && filters.deviceId != null) params.set('device_id', String(filters.deviceId))
  if (filters.q.trim()) params.set('q', filters.q.trim())
  if (filters.finger !== 'all') params.set('finger', filters.finger)
  params.set('page', String(page.value))
  return params.toString()
}

function validate() {
  resetErrors()
  const name = form.name.trim()
  const userId = form.userId.trim()
  if (!form.deviceId) fieldErrors.device = 'اختر الجهاز'
  if (!name) fieldErrors.name = 'اكتب اسم الموظف'
  else if (new TextEncoder().encode(name).length > 24) {
    fieldErrors.name = 'اسم الموظف طويل على الجهاز. اختصره، حوالي 12 حرفاً عربياً'
  }
  if (!editing.value && !/^[1-9]\d{0,8}$/.test(userId)) {
    fieldErrors.userId = 'رقم الموظف لازم يكون من 1 إلى 9 أرقام، بدون صفر في البداية'
  }
  return !fieldErrors.device && !fieldErrors.name && !fieldErrors.userId
}

function openCreate() {
  editingUserId.value = null
  form.deviceId = filters.deviceId || devices.value[0]?.id || null
  form.name = ''
  form.userId = ''
  resetErrors()
  formOpen.value = true
}

function openEdit(employee) {
  editingUserId.value = employee.user_id
  form.deviceId = employee.device_id
  form.name = employee.name || ''
  form.userId = employee.user_id
  resetErrors()
  formOpen.value = true
}

function closeForm() {
  if (saving.value) return
  formOpen.value = false
}

async function loadDevices() {
  devices.value = await api('/api/devices')
}

async function loadEmployees() {
  if (!devices.value.length) {
    employees.value = []
    total.value = 0
    loading.value = false
    return
  }
  const current = ++requestId
  loading.value = true
  error.value = ''
  try {
    const data = await api(`/api/employees?${queryString()}`)
    if (current !== requestId) return
    if (data.items.length === 0 && data.total > 0 && page.value > 1) {
      page.value = Math.max(1, Math.ceil(data.total / PAGE_SIZE))
      loading.value = false
      await loadEmployees()
      return
    }
    employees.value = data.items
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
  loadEmployees()
}

function clearFilters() {
  ignoreSearch = true
  filters.deviceId = ''
  filters.q = ''
  filters.finger = 'all'
  ignoreSearch = false
  apply()
}

function onPage(value) {
  page.value = value
  loadEmployees()
}

async function save() {
  if (!validate()) return
  saving.value = true
  try {
    if (editing.value) {
      await api(`/api/devices/${form.deviceId}/employees/${editingUserId.value}`, {
        method: 'PUT',
        body: JSON.stringify({ name: form.name.trim() }),
      })
      notify('تم تعديل الموظف على الجهاز')
    } else {
      await api(`/api/devices/${form.deviceId}/employees`, {
        method: 'POST',
        body: JSON.stringify({
          name: form.name.trim(),
          user_id: form.userId.trim(),
        }),
      })
      notify('تمت إضافة الموظف على الجهاز. سجّل بصمته من شاشة الجهاز')
      page.value = 1
    }
    formOpen.value = false
    editingUserId.value = null
    form.name = ''
    form.userId = ''
    await loadEmployees()
  } catch (err) {
    notify(err.message, 'error')
  } finally {
    saving.value = false
  }
}

function fingerText(employee) {
  if (!employee.fingers_known) return 'لم تُفحص'
  if (!employee.enrolled) return 'لا توجد بصمة'
  if (employee.finger_count === 1) return 'إصبع واحد'
  if (employee.finger_count === 2) return 'إصبعان'
  return `${latin(employee.finger_count)} أصابع`
}

function fingerKind(employee) {
  if (!employee.fingers_known) return 'idle'
  return employee.enrolled ? 'ok' : 'bad'
}

async function confirmDelete() {
  const employee = pendingDelete.value
  if (!employee) return
  deleting.value = true
  try {
    await api(`/api/devices/${employee.device_id}/employees/${employee.user_id}`, { method: 'DELETE' })
    pendingDelete.value = null
    notify('تم حذف الموظف من الجهاز')
    await loadEmployees()
  } catch (err) {
    notify(err.message, 'error')
  } finally {
    deleting.value = false
  }
}

async function refreshFromDevice() {
  const targets = filters.deviceId
    ? devices.value.filter((device) => device.id === filters.deviceId)
    : devices.value
  if (!targets.length) return
  refreshing.value = true
  try {
    for (const device of targets) {
      await api(`/api/devices/${device.id}/employees/refresh`, { method: 'POST' })
    }
    notify(targets.length === 1 ? 'تم تحديث الموظفين من الجهاز' : 'تم تحديث الموظفين من الأجهزة')
    page.value = 1
    await loadEmployees()
  } catch (err) {
    notify(err.message, 'error')
  } finally {
    refreshing.value = false
  }
}

watch(() => filters.q, () => {
  if (ignoreSearch) return
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    page.value = 1
    loadEmployees()
  }, 300)
})

watch(formOpen, async (open) => {
  if (!open) return
  await nextTick()
  nameField.value?.focus()
})

onMounted(async () => {
  try {
    await loadDevices()
  } catch (err) {
    error.value = err.message
    loading.value = false
    return
  }
  await loadEmployees()
})
</script>

<template>
  <div class="page">
    <div class="stack">
      <header class="page-head">
        <div class="title-with-nav">
          <NavToggle />
          <h1 class="page-title">الموظفون</h1>
        </div>
        <div class="head-actions">
          <p v-if="!loading && !error && devices.length" class="page-count">{{ totalText }}</p>
          <v-btn v-if="devices.length" color="primary" @click="openCreate">إضافة موظف</v-btn>
        </div>
      </header>

      <div v-if="!loading && devices.length === 0" class="app-card">
        <div class="state-block">
          <h2>لا توجد أجهزة</h2>
          <p>أضف جهاز البصمة أولاً، ثم أضف الموظفين عليه.</p>
          <v-btn color="primary" to="/devices">الانتقال إلى الأجهزة</v-btn>
        </div>
      </div>

      <template v-else>
        <v-card class="app-card filter-card">
          <div class="filters employee-filters">
            <div class="field">
              <label class="field-label" for="employee-filter-device">الجهاز</label>
              <v-select
                id="employee-filter-device"
                v-model="filters.deviceId"
                :items="deviceItems"
                item-title="title"
                item-value="value"
                hide-details
                @update:model-value="apply"
              />
            </div>
            <div class="field">
              <label class="field-label" for="employee-filter-finger">البصمة</label>
              <v-select
                id="employee-filter-finger"
                v-model="filters.finger"
                :items="fingerItems"
                item-title="title"
                item-value="value"
                hide-details
                @update:model-value="apply"
              />
            </div>
            <div class="field">
              <label class="field-label" for="employee-filter-query">الموظف</label>
              <v-text-field
                id="employee-filter-query"
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
                variant="outlined"
                :loading="refreshing"
                :disabled="saving || !devices.length"
                @click="refreshFromDevice"
              >
                تحديث من الجهاز
              </v-btn>
              <v-btn v-if="filtered" variant="text" @click="clearFilters">مسح</v-btn>
            </div>
          </div>
        </v-card>

        <v-card class="app-card sheet">
          <div v-if="loading" class="skeleton" aria-hidden="true">
            <div v-for="row in 6" :key="row" class="skeleton-row">
              <span class="sk"></span>
              <span class="sk"></span>
              <span class="sk"></span>
              <span class="sk"></span>
            </div>
          </div>

          <div v-else-if="error" class="state-block">
            <h2>تعذر تحميل الموظفين</h2>
            <p>{{ error }}</p>
            <v-btn color="primary" @click="loadEmployees">إعادة المحاولة</v-btn>
          </div>

          <div v-else-if="employees.length === 0" class="state-block">
            <template v-if="filtered">
              <h2>لا توجد نتائج</h2>
              <p>لا يوجد موظفون مطابقون للفلتر الحالي.</p>
              <v-btn variant="outlined" @click="clearFilters">مسح الفلتر</v-btn>
            </template>
            <template v-else>
              <h2>لا يوجد موظفون</h2>
              <p>أضف موظفاً، أو حدّث القائمة من الجهاز.</p>
            </template>
          </div>

          <template v-else>
            <div class="table-scroll">
              <table class="data-table employees-table" aria-label="الموظفون">
                <thead>
                  <tr>
                    <th scope="col">الاسم</th>
                    <th scope="col">رقم الموظف</th>
                    <th scope="col">الجهاز</th>
                    <th scope="col">البصمة</th>
                    <th scope="col">إجراءات</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="employee in employees" :key="employee.id">
                    <td>{{ employee.name || '—' }}</td>
                    <td><span class="num">{{ employee.user_id }}</span></td>
                    <td>{{ employee.device_name }}</td>
                    <td>
                      <span class="status-pill" :data-kind="fingerKind(employee)">{{ fingerText(employee) }}</span>
                    </td>
                    <td>
                      <div class="row-actions">
                        <v-btn class="icon-btn" icon variant="text" aria-label="عرض البصمات" @click="fingerEmployee = employee">
                          <span class="material-symbols-rounded">fingerprint</span>
                        </v-btn>
                        <v-btn class="icon-btn" icon variant="text" aria-label="تعديل" @click="openEdit(employee)">
                          <span class="material-symbols-rounded">edit</span>
                        </v-btn>
                        <v-btn class="icon-btn" icon variant="text" color="error" aria-label="حذف" @click="pendingDelete = employee">
                          <span class="material-symbols-rounded">delete</span>
                        </v-btn>
                      </div>
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
      </template>
    </div>

    <v-dialog
      v-model="formOpen"
      max-width="480"
      :persistent="saving"
      @update:model-value="(open) => { if (!open) closeForm() }"
    >
      <v-card class="dialog-card form-dialog">
        <h2>{{ formTitle }}</h2>
        <form @submit.prevent="save">
          <div class="dialog-fields">
            <div v-if="!editing" class="field">
              <label class="field-label" for="employee-device">الجهاز</label>
              <v-select
                id="employee-device"
                v-model="form.deviceId"
                :items="formDevices"
                item-title="title"
                item-value="value"
                :error-messages="fieldErrors.device"
              />
            </div>
            <div class="field">
              <label class="field-label" for="employee-name">اسم الموظف</label>
              <v-text-field
                id="employee-name"
                ref="nameField"
                v-model="form.name"
                placeholder="مثال: أحمد علي"
                autocomplete="off"
                :error-messages="fieldErrors.name"
              />
            </div>
            <div class="field">
              <label class="field-label" for="employee-id">رقم الموظف</label>
              <p class="field-hint">{{ editing ? 'الرقم ثابت لأن البصمة مربوطة به' : 'يظهر هذا الرقم على جهاز البصمة' }}</p>
              <v-text-field
                id="employee-id"
                v-model="form.userId"
                placeholder="101"
                inputmode="numeric"
                autocomplete="off"
                :disabled="editing"
                :error-messages="fieldErrors.userId"
              />
            </div>
          </div>
          <p v-if="!editing" class="field-hint form-note">بعد الحفظ، سجّل بصمة الموظف من شاشة الجهاز.</p>
          <div class="form-actions">
            <v-btn color="primary" type="submit" :loading="saving">
              {{ editing ? 'حفظ التعديل' : 'إضافة على الجهاز' }}
            </v-btn>
            <v-btn variant="text" type="button" @click="closeForm">إلغاء</v-btn>
          </div>
        </form>
      </v-card>
    </v-dialog>

    <v-dialog :model-value="fingerEmployee != null" max-width="440" @update:model-value="(open) => { if (!open) fingerEmployee = null }">
      <v-card v-if="fingerEmployee" class="dialog-card">
        <h2>بصمات الموظف</h2>
        <p class="finger-person">
          {{ fingerEmployee.name || 'بدون اسم' }}
          <span class="num">{{ fingerEmployee.user_id }}</span>
        </p>
        <p v-if="!fingerEmployee.fingers_known">
          لم تُقرأ البصمات من الجهاز بعد. اضغط «تحديث من الجهاز» حتى تظهر الأصابع المسجّلة.
        </p>
        <p v-else-if="!fingerEmployee.enrolled">لا توجد بصمة مسجّلة لهذا الموظف على الجهاز.</p>
        <template v-else>
          <p>مسجّل {{ fingerText(fingerEmployee) }}.</p>
          <ul class="finger-list">
            <li v-for="finger in fingerEmployee.fingers" :key="finger.id">{{ finger.name }}</li>
          </ul>
        </template>
        <div class="dialog-actions">
          <v-btn variant="text" @click="fingerEmployee = null">إغلاق</v-btn>
        </div>
      </v-card>
    </v-dialog>

    <v-dialog :model-value="pendingDelete != null" max-width="440" :persistent="deleting" @update:model-value="(open) => { if (!open && !deleting) pendingDelete = null }">
      <v-card v-if="pendingDelete" class="dialog-card">
        <h2>حذف الموظف</h2>
        <p>
          حذف «{{ pendingDelete.name || pendingDelete.user_id }}» يزيله من جهاز البصمة ومن هذه القائمة.
          البصمات المسحوبة سابقاً تبقى محفوظة برقم الموظف.
        </p>
        <div class="dialog-actions">
          <v-btn color="error" :loading="deleting" @click="confirmDelete">حذف</v-btn>
          <v-btn variant="text" :disabled="deleting" @click="pendingDelete = null">إلغاء</v-btn>
        </div>
      </v-card>
    </v-dialog>
  </div>
</template>
