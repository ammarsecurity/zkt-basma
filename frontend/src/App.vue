<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useDisplay } from 'vuetify'
import { snack } from './snack'

const route = useRoute()
const { width } = useDisplay()
const isMobile = computed(() => width.value < 600)
const isTablet = computed(() => width.value >= 600 && width.value < 1024)
const drawerOpen = ref(true)
const desktopCollapsed = ref(false)
const tabletExpanded = ref(false)

const rail = computed(() => {
  if (isMobile.value) return false
  if (isTablet.value) return !tabletExpanded.value
  return desktopCollapsed.value
})

watch(isMobile, (mobile) => {
  drawerOpen.value = !mobile
}, { immediate: true })

watch(() => route.path, () => {
  if (isMobile.value) drawerOpen.value = false
})

function toggleNav() {
  if (isMobile.value) drawerOpen.value = !drawerOpen.value
  else if (isTablet.value) tabletExpanded.value = !tabletExpanded.value
  else desktopCollapsed.value = !desktopCollapsed.value
}

const links = [
  { to: '/devices', title: 'الأجهزة', icon: 'fingerprint' },
  { to: '/logs', title: 'البصمات', icon: 'history' },
]
</script>

<template>
  <v-app>
    <a class="skip-link" href="#main">تخطي إلى المحتوى</a>

    <v-navigation-drawer
      v-model="drawerOpen"
      class="app-drawer"
      :class="{ 'is-rail': rail }"
      :permanent="!isMobile"
      :temporary="isMobile"
      :rail="rail"
      rail-width="72"
      width="260"
    >
      <div class="brand">
        <button v-if="!isMobile" class="rail-btn" type="button" aria-label="طي القائمة" @click="toggleNav">
          <span class="material-symbols-rounded">menu</span>
        </button>
        <strong v-if="!rail">البصمة</strong>
        <span v-if="!rail" class="brand-mark-text">ZKTeco</span>
      </div>

      <a
        v-if="!rail"
        class="credit"
        href="https://smartstick-iq.com/"
        target="_blank"
        rel="noopener noreferrer"
      >
        <span class="credit-kicker">صُمّم هذا النظام بعناية بواسطة</span>
        <span class="credit-name">
          عمار الأصفر
          <span class="material-symbols-rounded" aria-hidden="true">arrow_outward</span>
        </span>
      </a>
      <v-tooltip v-else location="end" text="صُمّم بعناية بواسطة عمار الأصفر">
        <template #activator="{ props }">
          <a
            v-bind="props"
            class="credit-mini"
            href="https://smartstick-iq.com/"
            target="_blank"
            rel="noopener noreferrer"
            aria-label="عمار الأصفر"
          >ع</a>
        </template>
      </v-tooltip>

      <v-list class="nav-list" nav>
        <v-tooltip
          v-for="link in links"
          :key="link.to"
          :disabled="!rail"
          location="end"
          :text="link.title"
        >
          <template #activator="{ props }">
            <v-list-item
              v-bind="props"
              :to="link.to"
              class="nav-link"
              rounded="lg"
            >
              <template #prepend>
                <span class="material-symbols-rounded nav-icon">{{ link.icon }}</span>
              </template>
              <v-list-item-title>{{ link.title }}</v-list-item-title>
            </v-list-item>
          </template>
        </v-tooltip>
      </v-list>
    </v-navigation-drawer>

    <v-app-bar v-if="isMobile" class="app-bar" flat height="56">
      <v-btn class="nav-toggle" icon variant="text" aria-label="القائمة" @click="toggleNav">
        <span class="material-symbols-rounded">menu</span>
      </v-btn>
      <p class="bar-title">{{ route.meta.title }}</p>
    </v-app-bar>

    <v-main id="main">
      <router-view />
    </v-main>

    <v-snackbar
      v-model="snack.show"
      :timeout="3500"
      location="bottom"
      rounded="lg"
      :color="snack.color === 'error' ? '#B91C1C' : '#166534'"
    >
      {{ snack.text }}
    </v-snackbar>
  </v-app>
</template>
