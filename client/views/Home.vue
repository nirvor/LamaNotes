<template>
  <div class="lamanotes-home">
    <img
      :src="homeMarkUrl"
      class="lamanotes-home-mark"
      alt=""
      aria-hidden="true"
      decoding="async"
      fetchpriority="low"
    />
    <div class="lamanotes-home-inner">
      <SearchInput
        :auto-focus="homeSearchAutoFocus"
        prominent-tag-cloud
        class="lamanotes-home-search"
      />
      <LoadingIndicator
        ref="loadingIndicator"
        class="lamanotes-home-shortcuts"
        hideLoader
      >
        <section
          class="lamanotes-home-pinned-section"
          aria-label="Quick access"
        >
          <nav class="lamanotes-home-pinned-list" aria-label="Daily notes">
            <RouterLink
              v-for="entry in dailyEntries"
              :key="entry.key"
              :to="entry.to"
              class="lamanotes-home-pinned-link"
              :title="entry.title"
              @focus="warmNote(entry.title, entry.key)"
              @pointerenter="warmNote(entry.title, entry.key)"
            >
              <SvgIcon
                type="mdi"
                :path="dailyIcons[entry.key]"
                size="1.05rem"
                aria-hidden="true"
              />
              <span class="lamanotes-home-pinned-name">{{ entry.title }}</span>
              <span
                v-if="entry.key === 'shared'"
                class="lamanotes-home-pinned-meta"
              >
                {{ entry.count }} {{ entry.count === 1 ? "note" : "notes" }}
              </span>
            </RouterLink>
          </nav>
          <nav
            v-if="home.pinned.length"
            class="lamanotes-home-pinned-list lamanotes-home-other-pins"
            aria-label="Pinned notes"
          >
            <RouterLink
              v-for="note in home.pinned"
              :key="note.title"
              :to="note.to"
              class="lamanotes-home-pinned-link"
              :title="note.title"
              @focus="warmNote(note.title)"
              @pointerenter="warmNote(note.title)"
            >
              <SvgIcon
                type="mdi"
                :path="mdiPinOutline"
                size="1.05rem"
                aria-hidden="true"
              />
              <span class="lamanotes-home-pinned-name">{{ note.title }}</span>
              <span
                v-if="pinnedNoteContext(note)"
                class="lamanotes-home-pinned-meta"
                >{{ pinnedNoteContext(note) }}</span
              >
            </RouterLink>
          </nav>
          <RouterLink
            v-if="home.more"
            :to="home.allPinnedRoute"
            class="lamanotes-home-pinned-more"
          >
            {{ home.moreLabel }}
            <SvgIcon
              type="mdi"
              :path="mdiDotsHorizontal"
              size="0.9rem"
              aria-hidden="true"
            />
          </RouterLink>
        </section>
      </LoadingIndicator>
    </div>
  </div>
</template>

<script setup>
import SvgIcon from "@jamescoyle/vue-icon";
import {
  mdiCartOutline,
  mdiDotsHorizontal,
  mdiNoteEditOutline,
  mdiPinOutline,
  mdiTrayArrowDown,
} from "@mdi/js";
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import {
  apiErrorHandler,
  getSemanticIndex,
  libraryIndexUpdatedEvent,
  prefetchNote,
  refreshFocusQuicknotesIntegration,
} from "../api.js";
import LoadingIndicator from "../components/LoadingIndicator.vue";
import { useGlobalStore } from "../globalStore.js";
import { isCloudNetworkError } from "../desktopShell.js";
import { buildHomeEntries } from "../homeEntries.js";
import { shouldAutoFocusSearch } from "../inputModality.js";
import { isSystemTag } from "../systemTags.js";
import { useToast } from "../toastStore.js";
import SearchInput from "../partials/SearchInput.vue";
import homeMarkUrl from "../assets/brand/lamanotes-home-mark.webp";

const globalStore = useGlobalStore();
const homeSearchAutoFocus = shouldAutoFocusSearch(window);
const loadingIndicator = ref();
const index = ref([]);
const toast = useToast();
const home = computed(() => buildHomeEntries(index.value, globalStore.config));
const dailyEntries = computed(() => [...home.value.daily, home.value.shared]);
const dailyIcons = {
  shopping: mdiCartOutline,
  quicknotes: mdiNoteEditOutline,
  shared: mdiTrayArrowDown,
};

function applySemanticIndex(entries) {
  index.value = Array.isArray(entries) ? entries : [];
}

async function init() {
  try {
    applySemanticIndex(await getSemanticIndex());
    void refreshFocusQuicknotesIntegration();
    loadingIndicator.value?.setLoaded();
  } catch (error) {
    if (isCloudNetworkError(error)) {
      applySemanticIndex([]);
      loadingIndicator.value?.setLoaded();
      return;
    }
    loadingIndicator.value?.setFailed();
    apiErrorHandler(error, toast);
  }
}

function semanticIndexUpdatedHandler(event) {
  applySemanticIndex(event.detail);
  loadingIndicator.value?.setLoaded();
}

function warmNote(title, key) {
  if (key !== "shared") void prefetchNote(title).catch(() => {});
}

function pinnedNoteContext(note) {
  return (Array.isArray(note?.tags) ? note.tags : [])
    .filter((tag) => tag && !isSystemTag(tag))
    .slice(0, 2)
    .map((tag) => `#${tag}`)
    .join(" ");
}

onMounted(() => {
  window.addEventListener(
    libraryIndexUpdatedEvent,
    semanticIndexUpdatedHandler,
  );
  init();
});
onBeforeUnmount(() =>
  window.removeEventListener(
    libraryIndexUpdatedEvent,
    semanticIndexUpdatedHandler,
  ),
);
</script>

<style scoped>
.lamanotes-home {
  position: relative;
  display: flex;
  min-height: 0;
  flex: 1 0 auto;
  justify-content: center;
  isolation: isolate;
}
.lamanotes-home-inner {
  position: relative;
  z-index: 1;
  display: flex;
  width: min(100%, 42rem);
  min-width: 0;
  flex-direction: column;
  gap: 0.8rem;
  padding-top: clamp(0.75rem, 2.5vh, 1.6rem);
}
.lamanotes-home-mark {
  position: absolute;
  z-index: 0;
  right: max(calc(50% - 21rem), 1rem);
  bottom: 1.5rem;
  width: clamp(7rem, 15vw, 10rem);
  height: auto;
  pointer-events: none;
  user-select: none;
  filter: var(--theme-home-mark-filter);
  opacity: 0.075;
}
.lamanotes-home-shortcuts {
  display: flex;
  width: 100%;
  min-width: 0;
  min-height: 0;
  flex-direction: column;
  align-items: stretch;
}
.lamanotes-home-pinned-section {
  overflow: hidden;
  border: 1px solid rgb(var(--theme-border));
  border-radius: var(--ln-radius-control);
  background: rgb(var(--theme-background-elevated));
  box-shadow: none;
}
.lamanotes-home-pinned-list {
  display: grid;
  width: 100%;
  min-width: 0;
  grid-template-columns: minmax(0, 1fr);
}
.lamanotes-home-pinned-link {
  display: grid;
  grid-template-columns: 1.1rem minmax(0, 1fr) auto;
  min-width: 0;
  min-height: 2.35rem;
  align-items: center;
  gap: 0.6rem;
  border: 0;
  border-bottom: 1px solid rgb(var(--theme-border) / 0.52);
  padding: 0.3rem 0.65rem;
  color: rgb(var(--theme-text-muted));
  background: transparent;
  line-height: 1.25;
  text-decoration: none;
}
.lamanotes-home-pinned-link:last-child {
  border-bottom: 0;
}
.lamanotes-home-other-pins {
  border-top: 1px solid rgb(var(--theme-border));
}
.lamanotes-home-pinned-name {
  overflow: hidden;
  color: rgb(var(--theme-text));
  font-size: 0.87rem;
  font-weight: 400;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.lamanotes-home-pinned-meta {
  max-width: 15rem;
  overflow: hidden;
  color: rgb(var(--theme-text-very-muted));
  font-size: 0.72rem;
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
  outline-offset: -2px;
}
.lamanotes-home-pinned-more {
  display: flex;
  min-height: 2.2rem;
  align-items: center;
  justify-content: flex-end;
  gap: 0.25rem;
  border-top: 1px solid rgb(var(--theme-border) / 0.52);
  padding: 0.35rem 0.65rem;
  color: rgb(var(--theme-text-muted));
  font-size: 0.75rem;
  text-decoration: none;
}
.lamanotes-home-pinned-more:hover,
.lamanotes-home-pinned-more:focus-visible {
  color: rgb(var(--theme-brand));
}
@media (max-width: 560px) {
  .lamanotes-home-inner {
    gap: 0.65rem;
    padding-top: 0.6rem;
  }
  .lamanotes-home-mark {
    display: none;
  }
  .lamanotes-home-pinned-meta {
    max-width: 7rem;
  }
}
@media (pointer: coarse), (hover: none) {
  .lamanotes-home-pinned-link,
  .lamanotes-home-pinned-more {
    min-height: var(--ln-touch-target);
  }
}
</style>
