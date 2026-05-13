<script setup lang="ts">
// PersonaStateView - shows scratch, memory streams, plans for a persona.
defineProps<{ id: string | number; name: string }>()
</script>

<template>
  <div>
    <a-typography-title :level="2">Persona State</a-typography-title>
    <a-typography-paragraph type="secondary">
      M1 placeholder, implemented in M6.
    </a-typography-paragraph>
  </div>
</template>
