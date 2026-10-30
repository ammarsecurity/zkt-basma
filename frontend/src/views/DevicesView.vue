<script setup>
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { api } from '../api'
import { notify } from '../snack'
import NavToggle from '../components/NavToggle.vue'

const devices = ref([])
const loading = ref(true)
const error = ref('')
const saving = ref(false)
const testing = ref(false)
const syncingId = ref(null)
const syncingAll = ref(false)
const pendingTime = ref(null)
const syncingTime = ref(false)
const deleting = ref(false)
const editingId = ref(null)
const formOpen = ref(false)
const pendingDelete = ref(null)
const nameField = ref(null)

const form = reactive({
  name: '',
  ip: '',
  port: '4370',
  password: '0',
})

const fieldErrors = reactive({
  name: '',
  ip: '',
  port: '',
  password: '',
})

const editing = computed(() => editingId.value != null)
const formTitle = computed(() => (editing.value ? 'تعديل الجهاز' : 'إضافة جهاز'))

function latin(value) {
  return Number(value || 0).toLocaleString('en-US')
}

function resetErrors() {
  fieldErrors.name = ''
  fieldErrors.ip = ''
  fieldErrors.port = ''
  fieldErrors.password = ''
}

function clearForm() {
  editingId.value = null
  form.name = ''
  form.ip = ''
  form.port = '4370'
  form.password = '0'
  resetErrors()
}

function openCreate() {
  clearForm()
  formOpen.value = true
}

function closeForm() {
  if (saving.value || testing.value) return
  formOpen.value = false
}

function validIp(ip) {
  const parts = ip.split('.')
  if (parts.length !== 4) return false
  return parts.every((part) => /^\d+$/.test(part) && String(Number(part)) === part && Number(part) <= 255)
}

function validate() {
  resetErrors()
  if (!form.port) form.port = '4370'
  if (form.password === '') form.password = '0'

  const name = form.name.trim()
  const ip = form.ip.trim()
  const port = Number(form.port)
  const password = Number(form.password)
  if (!name) fieldErrors.name = 'اكتب اسم الجهاز'
  else if (name.length > 80) fieldErrors.name = 'اسم الجهاز طويل'

  if (!validIp(ip)) fieldErrors.ip = 'عنوان IP غير صحيح'
  if (!Number.isInteger(port) || port < 1 || port > 65535) fieldErrors.port = 'المنفذ لازم يكون بين 1 و 65535'
  if (!Number.isInteger(password) || password < 0 || password > 99999999) {
    fieldErrors.password = 'كلمة مرور الاتصال غير صحيحة'
  }

  return !fieldErrors.name && !fieldErrors.ip && !fieldErrors.port && !fieldErrors.password
}

function payload() {
  return {
    name: form.name.trim(),
    ip: form.ip.trim(),
    port: Number(form.port),
    password: Number(form.password),
  }
}

async function load({ silent = false } = {}) {
  if (!silent) loading.value = true
  error.value = ''
  try {
    devices.value = await api('/api/devices')
  } catch (err) {
    error.value = err.message
  } finally {
    loading.value = false
  }
}

async function save() {
  if (!validate()) return
  saving.value = true
  try {
    if (editing.value) {
      await api(`/api/devices/${editingId.value}`, {
        method: 'PUT',
        body: JSON.stringify(payload()),
      })
      notify('تم حفظ التعديل')
    } else {
      await api('/api/devices', {
        method: 'POST',
        body: JSON.stringify(payload()),
      })
      notify('تم حفظ الجهاز')
    }
    clearForm()
    formOpen.value = false
    await load({ silent: true })
  } catch (err) {
    notify(err.message, 'error')
  } finally {
    saving.value = false
  }
}

async function testConnection() {
  if (!validate()) return
  testing.value = true
  try {
    const body = payload()
    const result = await api('/api/devices/test', {
      method: 'POST',
      body: JSON.stringify({ ip: body.ip, port: body.port, password: body.password }),
    })
    notify(result.message)
  } catch (err) {
    notify(err.message, 'error')
  } finally {
    testing.value = false
  }
}

function editDevice(device) {
  editingId.value = device.id
  form.name = device.name
  form.ip = device.ip
  form.port = String(device.port)
  form.password = String(device.password)
  resetErrors()
  formOpen.value = true
}

watch(formOpen, async (open) => {
  if (!open) return
  await nextTick()
  nameField.value?.focus()
})

async function syncDevice(device) {
  syncingId.value = device.id
  try {
    const result = await api(`/api/devices/${device.id}/sync`, { method: 'POST' })
    notify(result.message)
  } catch (err) {
    notify(err.message, 'error')
  } finally {
    syncingId.value = null
    await load({ silent: true })
  }
}

async function syncAll() {
  if (!devices.value.length || syncingId.value != null) return
  syncingAll.value = true
  let ok = 0
  let failed = 0
  let lastError = ''
  for (const device of devices.value) {
    syncingId.value = device.id
    try {
      await api(`/api/devices/${device.id}/sync`, { method: 'POST' })
      ok += 1
    } catch (err) {
      failed += 1
      lastError = err.message
    }
  }
  syncingId.value = null
  syncingAll.value = false
  if (failed === 0) notify(`تم سحب ${latin(ok)} جهاز`)
  else if (ok === 0 && devices.value.length === 1) notify(lastError, 'error')
  else notify(`تم سحب ${latin(ok)} جهاز، وفشل ${latin(failed)}`, 'error')
  await load({ silent: true })
}

async function confirmTime() {
  if (!pendingTime.value) return
  syncingTime.value = true
  try {
    const result = await api(`/api/devices/${pendingTime.value.id}/time`, { method: 'POST' })
    pendingTime.value = null
    notify(result.message)
  } catch (err) {
    notify(err.message, 'error')
  } finally {
    syncingTime.value = false
  }
}

async function confirmDelete() {
  if (!pendingDelete.value) return
  deleting.value = true
  try {
    await api(`/api/devices/${pendingDelete.value.id}`, { method: 'DELETE' })
    if (editingId.value === pendingDelete.value.id) clearForm()
    pendingDelete.value = null
    notify('تم حذف الجهاز من النظام')
    await load({ silent: devices.value.length > 1 })
  } catch (err) {
    notify(err.message, 'error')
  } finally {
    deleting.value = false
  }
}

function statusKind(device) {
  if (!device.ever_synced && !device.last_status) return 'idle'
  return device.last_ok ? 'ok' : 'bad'
}

function statusText(device) {
  if (!device.ever_synced && !device.last_status) return 'بانتظار السحب'
  return device.last_ok ? 'تم السحب' : 'فشل السحب'
}

onMounted(load)
</script>

<template>
  <div class="page">
    <header class="page-head">
      <div class="title-with-nav">
        <NavToggle />
        <h1 class="page-title">الأجهزة</h1>
      </div>
      <div class="head-actions">
        <v-btn
          v-if="!loading && devices.length"
          variant="outlined"
          :loading="syncingAll"
          :disabled="syncingId != null"
          @click="syncAll"
        >
          سحب الكل
        </v-btn>
        <v-btn color="primary" @click="openCreate">إضافة جهاز</v-btn>
      </div>
    </header>

    <v-card class="app-card sheet">
        <div v-if="loading" class="skeleton" aria-hidden="true">
          <div v-for="row in 5" :key="row" class="skeleton-row">
            <span class="sk"></span>
            <span class="sk"></span>
            <span class="sk"></span>
            <span class="sk"></span>
          </div>
        </div>

        <div v-else-if="error" class="state-block">
          <h2>تعذر تحميل الأجهزة</h2>
          <p>{{ error }}</p>
          <v-btn color="primary" @click="load">إعادة المحاولة</v-btn>
        </div>

        <div v-else-if="devices.length === 0" class="state-block">
          <h2>لا توجد أجهزة</h2>
          <p>أضف الجهاز من النموذج، ثم اسحب البصمات.</p>
          <v-btn color="primary" @click="openCreate">أضف أول جهاز</v-btn>
        </div>

        <div v-else class="table-scroll">
          <table class="data-table devices-table" aria-label="الأجهزة المحفوظة">
            <thead>
              <tr>
                <th scope="col">الجهاز</th>
                <th scope="col">آخر سحب</th>
                <th scope="col">السجلات</th>
                <th scope="col">الحالة</th>
                <th scope="col">إجراءات</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="device in devices" :key="device.id">
                <td>
                  <strong class="device-name">{{ device.name }}</strong>
                  <span class="num muted device-address">{{ device.ip }}:{{ device.port }}</span>
                </td>
                <td><span class="num">{{ device.last_sync_at || '—' }}</span></td>
                <td><span class="num">{{ latin(device.attendance_count) }}</span></td>
                <td>
                  <span class="status-pill" :data-kind="statusKind(device)">{{ statusText(device) }}</span>
                  <span v-if="device.last_status" class="status-note">{{ device.last_status }}</span>
                </td>
                <td>
                  <div class="row-actions">
                    <v-btn
                      variant="tonal"
                      color="primary"
                      :loading="syncingId === device.id"
                      :disabled="syncingId != null && syncingId !== device.id"
                      @click="syncDevice(device)"
                    >
                      سحب
                    </v-btn>
                    <v-btn
                      class="icon-btn"
                      icon
                      variant="text"
                      aria-label="مزامنة الساعة"
                      :disabled="syncingId != null || syncingTime"
                      @click="pendingTime = device"
                    >
                      <span class="material-symbols-rounded">schedule</span>
                    </v-btn>
                    <v-btn class="icon-btn" icon variant="text" aria-label="تعديل" @click="editDevice(device)">
                      <span class="material-symbols-rounded">edit</span>
                    </v-btn>
                    <v-btn class="icon-btn" icon variant="text" color="error" aria-label="حذف" @click="pendingDelete = device">
                      <span class="material-symbols-rounded">delete</span>
                    </v-btn>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </v-card>

    <v-dialog
      v-model="formOpen"
      max-width="520"
      :persistent="saving || testing"
      @update:model-value="(open) => { if (!open) closeForm() }"
    >
      <v-card class="dialog-card form-dialog">
        <h2>{{ formTitle }}</h2>
        <form @submit.prevent="save">
          <div class="form-grid">
            <div class="field full">
              <label class="field-label" for="device-name">اسم الجهاز</label>
              <v-text-field
                id="device-name"
                ref="nameField"
                v-model="form.name"
                placeholder="مثال: بوابة الموظفين"
                autocomplete="off"
                :error-messages="fieldErrors.name"
              />
            </div>
            <div class="field full">
              <label class="field-label" for="device-ip">عنوان IP</label>
              <v-text-field
                id="device-ip"
                v-model="form.ip"
                placeholder="192.168.1.201"
                autocomplete="off"
                :error-messages="fieldErrors.ip"
              />
            </div>
            <div class="field">
              <label class="field-label" for="device-port">المنفذ</label>
              <p class="field-hint">الافتراضي 4370</p>
              <v-text-field
                id="device-port"
                v-model="form.port"
                inputmode="numeric"
                autocomplete="off"
                :error-messages="fieldErrors.port"
              />
            </div>
            <div class="field">
              <label class="field-label" for="device-password">كلمة مرور الاتصال</label>
              <p class="field-hint">غالباً 0 إذا ما تغيّرت من إعدادات الجهاز</p>
              <v-text-field
                id="device-password"
                v-model="form.password"
                inputmode="numeric"
                autocomplete="off"
                :error-messages="fieldErrors.password"
              />
            </div>
          </div>
          <div class="form-actions">
            <v-btn color="primary" type="submit" :loading="saving">
              {{ editing ? 'حفظ التعديل' : 'حفظ الجهاز' }}
            </v-btn>
            <v-btn variant="outlined" type="button" :loading="testing" @click="testConnection">
              اختبار الاتصال
            </v-btn>
            <v-btn variant="text" type="button" @click="closeForm">إلغاء</v-btn>
          </div>
        </form>
      </v-card>
    </v-dialog>

    <v-dialog
      :model-value="pendingTime != null"
      max-width="440"
      :persistent="syncingTime"
      @update:model-value="(open) => { if (!open && !syncingTime) pendingTime = null }"
    >
      <v-card class="dialog-card">
        <h2>مزامنة الساعة</h2>
        <p>تضبط ساعة «{{ pendingTime?.name }}» على وقت هذه الحاسبة الآن. البصمات المحفوظة سابقاً تبقى بتوقيتها، والبصمات الجديدة تُسجَّل بالوقت الصحيح.</p>
        <div class="dialog-actions">
          <v-btn color="primary" :loading="syncingTime" @click="confirmTime">مزامنة</v-btn>
          <v-btn variant="text" :disabled="syncingTime" @click="pendingTime = null">إلغاء</v-btn>
        </div>
      </v-card>
    </v-dialog>

    <v-dialog :model-value="pendingDelete != null" max-width="440" @update:model-value="(open) => { if (!open) pendingDelete = null }">
      <v-card class="dialog-card">
        <h2>حذف الجهاز</h2>
        <p>حذف «{{ pendingDelete?.name }}» يمسح البصمات المحفوظة منه داخل هذا النظام. جهاز البصمة نفسه يبقى كما هو.</p>
        <div class="dialog-actions">
          <v-btn color="error" :loading="deleting" @click="confirmDelete">حذف</v-btn>
          <v-btn variant="text" @click="pendingDelete = null">إلغاء</v-btn>
        </div>
      </v-card>
    </v-dialog>
  </div>
</template>
