<template>
  <div class="lamanotes-home">
    <img
      :src="homeMarkUrl"
      class="lamanotes-home-mark"
      alt=""
      aria-hidden="true"
    />
    <div class="lamanotes-home-inner">
      <SearchInput
        :auto-focus="homeSearchAutoFocus"
        large
        prominent-tag-cloud
        class="lamanotes-home-search"
      />
      <LoadingIndicator
        ref="loadingIndicator"
        class="lamanotes-home-pinned"
        hideLoader
      >
        <section v-if="notes.length > 0" class="lamanotes-home-pinned-section">
          <header class="lamanotes-home-pinned-title">
            <span>
              <SvgIcon type="mdi" :path="mdiStar" size="0.72rem" />
              {{ globalStore.config.quickAccessTitle }}
            </span>
            <small>{{ visiblePinnedLabel }}</small>
          </header>
          <div class="lamanotes-home-pinned-list">
            <RouterLink
              v-for="note in visiblePinnedNotes"
              :key="note.title"
              :to="{ name: 'note', params: { title: note.title } }"
              class="lamanotes-home-pinned-link"
              :title="note.title"
              @focus="warmNote(note.title)"
              @pointerenter="warmNote(note.title)"
            >
              <span class="lamanotes-home-pinned-name">{{ note.title }}</span>
              <span
                v-if="pinnedNoteContext(note)"
                class="lamanotes-home-pinned-meta"
              >
                {{ pinnedNoteContext(note) }}
              </span>
            </RouterLink>
          </div>
          <RouterLink
            v-if="notes.length > globalStore.config.quickAccessLimit"
            :to="{
              name: 'search',
              query: {
                term: globalStore.config.quickAccessTerm,
                sortBy: searchSortOptions[globalStore.config.quickAccessSort],
              },
            }"
            class="lamanotes-home-pinned-more"
            title="Show all pinned notes"
            aria-label="Show all pinned notes"
          >
            <span>All pinned notes</span>
            <SvgIcon type="mdi" :path="mdiDotsHorizontal" size="0.9rem" />
          </RouterLink>
        </section>
      </LoadingIndicator>
    </div>
  </div>
</template>

<script setup>
import SvgIcon from "@jamescoyle/vue-icon";
import { mdiDotsHorizontal, mdiStar } from "@mdi/js";
import { useToast } from "primevue/usetoast";
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
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
import { shouldAutoFocusSearch } from "../inputModality.js";
import SearchInput from "../partials/SearchInput.vue";
import homeMarkUrl from "../assets/brand/lamanotes-icon-master.png";

const globalStore = useGlobalStore();
const homeSearchAutoFocus = shouldAutoFocusSearch(window);
const loadingIndicator = ref();
const notes = ref([]);
const toast = useToast();
const visiblePinnedNotes = computed(() =>
  notes.value.slice(0, Number(globalStore.config.quickAccessLimit || 7)),
);
const visiblePinnedCount = computed(() => visiblePinnedNotes.value.length);
const visiblePinnedLabel = computed(
  () =>
    `${visiblePinnedCount.value} ${
      visiblePinnedCount.value === 1 ? "note" : "notes"
    }`,
);

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

function pinnedNoteContext(note) {
  const tags = (Array.isArray(note?.tags) ? note.tags : [])
    .map((tag) => String(tag || "").trim())
    .filter((tag) => tag && tag.toLowerCase() !== "pinned")
    .slice(0, 2)
    .map((tag) => `#${tag}`);
  const modified = Number(note?.lastModified);
  if (Number.isFinite(modified) && modified > 0) {
    tags.push(
      new Intl.DateTimeFormat(undefined, {
        month: "short",
        day: "numeric",
      }).format(new Date(modified * 1000)),
    );
  }
  return tags.join(" / ");
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
.lamanotes-home {
  position: relative;
  display: flex;
  min-height: calc(100vh - 4rem);
  justify-content: center;
  overflow: hidden;
  isolation: isolate;
}

.lamanotes-home-inner {
  position: relative;
  z-index: 1;
  display: flex;
  width: min(100%, 42rem);
  flex-direction: column;
  padding-top: clamp(3.6rem, 10vh, 6.2rem);
}

.lamanotes-home-search {
  margin-bottom: 1rem;
}

.lamanotes-home-mark {
  position: absolute;
  z-index: 0;
  top: clamp(28rem, 56vh, 35rem);
  right: max(calc(50% - 22rem), 0.5rem);
  width: clamp(12rem, 28vw, 17rem);
  height: auto;
  pointer-events: none;
  user-select: none;
  filter: var(--theme-home-mark-filter);
  opacity: var(--theme-home-mark-opacity);
}

.lamanotes-home-pinned {
  display: flex;
  width: 100%;
  min-width: 0;
  min-height: 9rem;
  flex-direction: column;
  align-items: stretch;
}

.lamanotes-home-pinned-section {
  overflow: hidden;
  border: var(--ln-border-subtle);
  border-radius: var(--ln-radius-card);
  background: rgb(var(--theme-background-elevated) / 0.82);
  box-shadow: var(--ln-shadow-card);
}

.lamanotes-home-pinned-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  min-height: 2.35rem;
  margin: 0;
  border-bottom: 1px solid rgb(var(--theme-border) / 0.7);
  padding: 0.45rem 0.72rem;
  color: rgb(var(--theme-text-very-muted));
  font-size: 0.7rem;
  font-weight: 650;
  text-transform: uppercase;
}

.lamanotes-home-pinned-title > span {
  display: inline-flex;
  align-items: center;
  gap: 0.32rem;
}

.lamanotes-home-pinned-title small {
  color: rgb(var(--theme-text-very-muted));
  font-size: 0.64rem;
  font-weight: 500;
  text-transform: none;
}

.lamanotes-home-pinned-list {
  display: grid;
  width: 100%;
  min-width: 0;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  column-gap: 0;
  row-gap: 0;
}

.lamanotes-home-pinned-link {
  display: grid;
  min-width: 0;
  min-height: 3.1rem;
  overflow: hidden;
  align-content: center;
  gap: 0.16rem;
  border: 0;
  border-bottom: 1px solid rgb(var(--theme-border) / 0.52);
  padding: 0.5rem 0.72rem;
  color: rgb(var(--theme-text-muted));
  background: transparent;
  line-height: 1.15;
  text-align: left;
  text-decoration: none;
}

.lamanotes-home-pinned-link:nth-child(odd) {
  border-right: 1px solid rgb(var(--theme-border) / 0.52);
}

.lamanotes-home-pinned-name {
  overflow: hidden;
  color: rgb(var(--theme-text));
  font-size: 0.9rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.lamanotes-home-pinned-meta {
  overflow: hidden;
  color: rgb(var(--theme-text-very-muted));
  font-size: 0.66rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.lamanotes-home-pinned-link:hover,
.lamanotes-home-pinned-link:focus-visible {
  background: rgb(var(--theme-brand) / 0.055);
}

.lamanotes-home-pinned-link:hover .lamanotes-home-pinned-name,
.lamanotes-home-pinned-link:focus-visible .lamanotes-home-pinned-name {
  color: rgb(var(--theme-brand));
}

.lamanotes-home-pinned-link:focus-visible {
  outline: 2px solid rgb(var(--theme-brand));
  outline-offset: 2px;
}

.lamanotes-home-pinned-more {
  display: flex;
  min-height: 2.2rem;
  align-items: center;
  justify-content: flex-end;
  gap: 0.25rem;
  padding: 0.35rem 0.72rem;
  color: rgb(var(--theme-text-very-muted));
  font-size: 0.68rem;
  text-decoration: none;
}

.lamanotes-home-pinned-more:hover,
.lamanotes-home-pinned-more:focus-visible {
  color: rgb(var(--theme-brand));
}

@media (max-width: 560px) {
  .lamanotes-home-inner {
    padding-top: clamp(2.8rem, 8vh, 4.4rem);
  }

  .lamanotes-home-pinned-list {
    grid-template-columns: 1fr;
  }

  .lamanotes-home-pinned-link:nth-child(odd) {
    border-right: 0;
  }

  .lamanotes-home-mark {
    top: 38rem;
    right: -1.6rem;
    width: 12rem;
    opacity: 0.12;
  }
}

@media (pointer: coarse), (hover: none) {
  .lamanotes-home-pinned-link {
    min-height: var(--ln-touch-target);
  }
}
</style>
