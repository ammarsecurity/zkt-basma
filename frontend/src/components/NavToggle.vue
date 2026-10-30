<script setup>
import { inject } from 'vue'

const nav = inject('navControls')
</script>

<template>
  <button
    v-if="nav && !nav.isMobile.value"
    class="rail-btn"
    type="button"
    :aria-label="nav.rail.value ? 'فتح القائمة' : 'طي القائمة'"
    @click="nav.toggleNav"
  >
    <span class="material-symbols-rounded">menu</span>
  </button>
</template>
