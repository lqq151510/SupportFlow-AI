<script setup>
defineProps({
  text: {type: String, required: true},
  time: {type: String, required: true},
  icon: {type: [Object, Function], required: true},
});
</script>

<template>
  <div class="activity">
    <span class="activity-icon"><component :is="icon" :size="15" /></span>
    <div>
      <strong>{{ text }}</strong>
      <small>{{ time }}</small>
    </div>
  </div>
</template>
