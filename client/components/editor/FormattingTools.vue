<template>
  <button
    v-for="tool in tools"
    :key="tool.id"
    type="button"
    class="lamanotes-format-button"
    :title="tool.label"
    :aria-label="tool.label"
    @mousedown.prevent
    @click="$emit('format', tool.id)"
  >
    <SvgIcon type="mdi" :path="tool.icon" size="0.92rem" />
  </button>
</template>
<script setup>
import SvgIcon from "@jamescoyle/vue-icon";
import {
  mdiFormatBold,
  mdiFormatItalic,
  mdiFormatFontSizeDecrease,
  mdiFormatListBulleted,
  mdiFormatListChecks,
  mdiLinkVariant,
  mdiCodeTags,
} from "@mdi/js";
defineEmits(["format"]);
const tools = [
  { id: "bold", label: "Toggle bold (Ctrl+B)", icon: mdiFormatBold },
  { id: "italic", label: "Toggle italic (Ctrl+I)", icon: mdiFormatItalic },
  {
    id: "small",
    label: "Toggle smaller text",
    icon: mdiFormatFontSizeDecrease,
  },
  { id: "list", label: "Toggle list", icon: mdiFormatListBulleted },
  { id: "checklist", label: "Toggle checklist", icon: mdiFormatListChecks },
  { id: "link", label: "Insert link (Ctrl+K)", icon: mdiLinkVariant },
  { id: "code", label: "Toggle inline code", icon: mdiCodeTags },
];
</script>
