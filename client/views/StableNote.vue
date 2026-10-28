<template>
  <p class="private-view" role="status">{{ error || "Opening note..." }}</p>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { privateRequest } from "../privateApi.js";
import { stableNoteDestination } from "../sharedEntry.js";

const props = defineProps({ noteId: String });
const error = ref("");
const router = useRouter();
onMounted(async () => {
  try {
    const note = await privateRequest(
      `/notes/${encodeURIComponent(props.noteId)}`,
    );
    await router.replace(
      stableNoteDestination(note.title, router.currentRoute.value),
    );
  } catch (problem) {
    error.value = problem.message;
  }
});
</script>
