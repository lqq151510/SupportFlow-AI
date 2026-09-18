<script setup>
defineProps({
  title: {type: String, required: true},
  sub: {type: String, default: ''},
});
</script>

<template>
  <div class="page-header">
    <div>
      <h1>{{ title }}</h1>
      <p v-if="sub">{{ sub }}</p>
    </div>
    <div class="header-actions">
      <slot />
    </div>
  </div>
</template>
