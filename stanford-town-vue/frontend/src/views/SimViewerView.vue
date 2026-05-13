<script setup lang="ts">
// SimViewerView - Pixi canvas + controls for live/replay viewing.
defineProps<{
  id: string | number
  mode: 'live' | 'replay'
}>()
</script>

<template>
  <div>
    <a-typography-title :level="2">Sim Viewer</a-typography-title>
    <a-typography-paragraph type="secondary">
      M1 placeholder, implemented in M4/M5.
    </a-typography-paragraph>
  </div>
</template>
