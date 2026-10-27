<template>
  <section
    class="private-view share-import"
    aria-labelledby="share-import-title"
  >
    <header>
      <h1 id="share-import-title">
        {{ note ? "Saved to LamaNotes" : "Save to LamaNotes" }}
      </h1>
      <RouterLink to="/" aria-label="Close import">Close</RouterLink>
    </header>
    <p v-if="busy" role="status">Saving your LamaShare item...</p>
    <template v-else-if="note">
      <p>{{ note.title }}</p>
      <RouterLink class="share-import-open" :to="`/n/${note.noteId}`"
        >Open note</RouterLink
      >
    </template>
    <template v-else>
      <p role="alert">{{ error }}</p>
      <button v-if="hasTicket" type="button" @click="save">Try again</button>
      <a v-else class="share-import-open" href="https://start.thuber.org/share/">Return to LamaShare</a>
    </template>
  </section>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { RouterLink, useRouter } from "vue-router";
import {
  clearShareTicket,
  importSharedItem,
  pendingShareTicket,
} from "../shareImport.js";
import { getStoredToken } from "../tokenStorage.js";
import { clearApiCaches } from "../api.js";

const router = useRouter();
const busy = ref(false),
  error = ref(""),
  note = ref(null),
  hasTicket = ref(false);

async function save() {
  if (busy.value) return;
  const ticket = pendingShareTicket();
  hasTicket.value = Boolean(ticket);
  if (!ticket) {
    error.value =
      "Open Save to Notes again in LamaShare. Your original item is still there.";
    return;
  }
  busy.value = true;
  error.value = "";
  try {
    note.value = await importSharedItem(ticket, { token: getStoredToken() });
    clearShareTicket();
    clearApiCaches();
  } catch (problem) {
    if (problem.status === 401) {
      await router.replace({
        name: "login",
        query: { redirect: "/share-import" },
      });
      return;
    }
    error.value = problem.message;
    if (problem.status === 410) {
      clearShareTicket();
      hasTicket.value = false;
    }
  } finally {
    busy.value = false;
  }
}

// The pending ticket exists only after the explicit Save to Notes handoff.
onMounted(save);
</script>

<style scoped>
.share-import {
  max-width: 36rem;
}
.share-import header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 1rem;
}
.share-import header a {
  display: inline-flex;
  align-items: center;
  min-height: 44px;
  padding-inline: 0.5rem;
  font-size: var(--ln-font-small);
}
.share-import p {
  margin: 0.65rem 0 1rem;
}
.share-import-open,
.share-import button {
  display: inline-flex;
  align-items: center;
  min-height: 44px;
  padding: 0.45rem 0.75rem;
  border: 1px solid rgb(var(--theme-border));
  border-radius: var(--ln-radius-control);
  color: rgb(var(--theme-brand));
  background: rgb(var(--theme-background-elevated));
}
</style>
