<template>
  <div class="flatnotes-home">
    <div class="flatnotes-home-inner">
      <SearchInput class="mb-4 shadow-[0_0_20px] shadow-theme-shadow" />
      <LoadingIndicator
        ref="loadingIndicator"
        class="flatnotes-home-pinned min-h-56"
        hideLoader
      >
        <div v-if="notes.length > 0" class="flatnotes-home-pinned-title">
          <SvgIcon type="mdi" :path="mdiStar" size="0.72rem" />
          <span>{{ globalStore.config.quickAccessTitle }}</span>
        </div>
        <div v-if="notes.length > 0" class="flatnotes-home-pinned-list">
          <RouterLink
            v-for="note in notes.slice(0, globalStore.config.quickAccessLimit)"
            :key="note.title"
            :to="{ name: 'note', params: { title: note.title } }"
            class="flatnotes-home-pinned-link"
            :title="note.title"
            @focus="warmNote(note.title)"
            @pointerenter="warmNote(note.title)"
          >
            <span>{{ note.title }}</span>
          </RouterLink>
          <RouterLink
            v-if="notes.length > globalStore.config.quickAccessLimit"
            :to="{
              name: 'search',
              query: {
                term: globalStore.config.quickAccessTerm,
                sortBy: searchSortOptions[globalStore.config.quickAccessSort],
              },
            }"
            class="flatnotes-home-pinned-link flatnotes-home-pinned-more"
            title="Show more"
            aria-label="Show more pinned notes"
          >
            <SvgIcon type="mdi" :path="mdiDotsHorizontal" size="1rem" />
          </RouterLink>
        </div>
      </LoadingIndicator>
    </div>
  </div>
</template>

<script setup>
import SvgIcon from "@jamescoyle/vue-icon";
import { mdiDotsHorizontal, mdiStar } from "@mdi/js";
import { useToast } from "primevue/usetoast";
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import { RouterLink } from "vue-router";

import {
  apiErrorHandler,
  getSemanticIndex,
  libraryIndexUpdatedEvent,
  prefetchNote,
} from "../api.js";
import LoadingIndicator from "../components/LoadingIndicator.vue";
import { searchSortOptions } from "../constants.js";
import { useGlobalStore } from "../globalStore.js";
import { isCloudNetworkError } from "../desktopShell.js";
import SearchInput from "../partials/SearchInput.vue";

const globalStore = useGlobalStore();
const loadingIndicator = ref();
const notes = ref([]);
const toast = useToast();

function init() {
  if (globalStore.config.quickAccessHide) {
    return;
  }
  getSemanticIndex()
    .then((index) => {
      applySemanticIndex(index);
      loadingIndicator.value.setLoaded();
    })
    .catch((error) => {
      if (isCloudNetworkError(error)) {
        notes.value = [];
        loadingIndicator.value.setLoaded();
        return;
      }
      loadingIndicator.value.setFailed();
      apiErrorHandler(error, toast);
    });
}

function applySemanticIndex(index) {
  const tag = String(globalStore.config.quickAccessTerm || "#pinned")
    .replace(/^#/, "")
    .toLowerCase();
  const matching = (Array.isArray(index) ? index : []).filter((note) =>
    (note.tags || []).some((noteTag) => String(noteTag).toLowerCase() === tag),
  );
  matching.sort((left, right) => {
    if (globalStore.config.quickAccessSort === "title") {
      return left.title.localeCompare(right.title);
    }
    return Number(right.lastModified || 0) - Number(left.lastModified || 0);
  });
  notes.value = matching.slice(
    0,
    Number(globalStore.config.quickAccessLimit || 7) + 1,
  );
}

function semanticIndexUpdatedHandler(event) {
  applySemanticIndex(event.detail);
  loadingIndicator.value?.setLoaded();
}

function warmNote(title) {
  void prefetchNote(title).catch(() => {});
}

// Watch to allow for delayed config load.
watch(
  () => [
    globalStore.config.quickAccessHide,
    globalStore.config.quickAccessTerm,
    globalStore.config.quickAccessSort,
    globalStore.config.quickAccessLimit,
  ],
  init,
);
onMounted(() => {
  window.addEventListener(
    libraryIndexUpdatedEvent,
    semanticIndexUpdatedHandler,
  );
  init();
});
onBeforeUnmount(() => {
  window.removeEventListener(
    libraryIndexUpdatedEvent,
    semanticIndexUpdatedHandler,
  );
});
</script>

<style scoped>
.flatnotes-home {
  display: flex;
  min-height: 100%;
  justify-content: center;
}

.flatnotes-home-inner {
  display: flex;
  width: min(100%, 34rem);
  flex-direction: column;
  padding-top: clamp(11rem, 25vh, 18rem);
}

.flatnotes-home-pinned {
  display: flex;
  width: 100%;
  min-width: 0;
  flex-direction: column;
  align-items: stretch;
}

.flatnotes-home-pinned-title {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  margin: 0 0 0.32rem;
  color: rgb(var(--theme-text-very-muted));
  font-size: 0.7rem;
  font-weight: 650;
  letter-spacing: 0;
  text-transform: uppercase;
}

.flatnotes-home-pinned-list {
  display: grid;
  width: 100%;
  min-width: 0;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 12rem), 1fr));
  column-gap: 1rem;
  row-gap: 0;
}

.flatnotes-home-pinned-link {
  display: flex;
  min-width: 0;
  min-height: 2rem;
  overflow: hidden;
  align-items: center;
  border: 0;
  border-bottom: 1px solid rgb(var(--theme-border) / 0.42);
  padding: 0.3rem 0.08rem;
  color: rgb(var(--theme-text-muted));
  background: transparent;
  font-size: 0.84rem;
  line-height: 1.15;
  text-align: left;
  text-decoration: none;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.flatnotes-home-pinned-link:hover,
.flatnotes-home-pinned-link:focus-visible {
  color: rgb(var(--theme-text));
  border-bottom-color: rgb(var(--theme-brand) / 0.62);
  outline: none;
}

.flatnotes-home-pinned-more {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: rgb(var(--theme-text-very-muted));
}

@media (max-width: 560px) {
  .flatnotes-home-inner {
    padding-top: clamp(10rem, 30vh, 17rem);
  }

  .flatnotes-home-pinned-list {
    grid-template-columns: 1fr;
  }
}
</style>
