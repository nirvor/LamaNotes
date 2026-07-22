<template>
  <div class="flex items-center">
    <SvgIcon
      v-if="iconPath"
      type="mdi"
      :path="iconPath"
      :size="iconSize"
      class="lamanotes-icon-label-icon"
      :class="{ 'mr-1': label }"
    ></SvgIcon>
    <span v-if="label" class="lamanotes-icon-label-text">{{ label }}</span>
  </div>
</template>

<script setup>
import SvgIcon from "@jamescoyle/vue-icon";

defineProps({
  iconPath: String,
  iconSize: {
    type: String,
    default: "1.25em",
  },
  label: String,
});
</script>
