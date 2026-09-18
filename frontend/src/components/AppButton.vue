<script setup>
// 与 React 版 `Button` 等价：不带 type 属性，因此在 <form> 内保持浏览器的默认 submit 行为。
defineProps({
  primary: {type: Boolean, default: false},
  icon: {type: [Object, Function], default: null},
  disabled: {type: Boolean, default: false},
});
defineEmits(['click']);
</script>

<template>
  <button :class="primary ? 'btn primary' : 'btn'" :disabled="disabled" @click="$emit('click', $event)">
    <component :is="icon" v-if="icon" :size="16" /> <slot />
  </button>
</template>
