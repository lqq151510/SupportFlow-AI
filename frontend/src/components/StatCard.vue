<script setup>
defineProps({
  label: {type: String, required: true},
  value: {type: [String, Number], default: ''},
  delta: {type: String, default: ''},
  tone: {type: String, default: ''},
});
</script>

<template>
  <div class="stat">
    <span>{{ label }}</span>
    <strong :class="tone">{{ value }}</strong>
    <small>{{ delta }}</small>
  </div>
</template>
