<script setup lang="ts">
// LlmLogsView - browse LLM call logs for a simulation.
defineProps<{ id: string | number }>()
</script>

<template>
  <div>
    <a-typography-title :level="2">LLM Logs</a-typography-title>
    <a-typography-paragraph type="secondary">
      M1 placeholder, implemented in M6.
    </a-typography-paragraph>
  </div>
</template>
