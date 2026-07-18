<template>
  <div class="flatnotes-note-drawer-shell print:hidden">
    <button
      v-if="showFloatingHandle"
      class="flatnotes-note-drawer-handle"
      :class="{ 'flatnotes-note-drawer-handle-open': drawerVisible }"
      type="button"
      title="Open note switcher"
      :aria-expanded="String(drawerVisible)"
      aria-controls="flatnotes-note-drawer"
      :aria-label="drawerVisible ? 'Close note switcher' : 'Open note switcher'"
      @click.stop="toggleDrawer"
    >
      <SvgIcon
        type="mdi"
        :path="drawerVisible ? mdilChevronRight : mdiBookMultipleOutline"
        size="1rem"
      />
    </button>

    <Transition name="flatnotes-note-drawer-fade">
      <div
        v-if="drawerVisible"
        class="flatnotes-note-drawer-backdrop"
        @click="closeDrawer"
      ></div>
    </Transition>

    <aside
      id="flatnotes-note-drawer"
      class="flatnotes-note-drawer"
      :class="{ 'flatnotes-note-drawer-open': drawerVisible }"
      :inert="drawerVisible ? undefined : true"
      :aria-hidden="String(!drawerVisible)"
      aria-label="Note switcher"
      @pointerdown="drawerPointerDown"
      @pointerup="drawerPointerUp"
    >
      <div class="flatnotes-note-drawer-header">
        <div class="flatnotes-note-drawer-title">Notes</div>
        <button
          type="button"
          class="flatnotes-note-drawer-close"
          title="Close note switcher"
          aria-label="Close note switcher"
          @click="closeDrawer"
        >
          <SvgIcon type="mdi" :path="mdilChevronRight" size="1.05rem" />
        </button>
      </div>

      <nav class="flatnotes-note-drawer-nav" aria-label="Library navigation">
        <RouterLink
          :to="{ name: 'home' }"
          class="flatnotes-note-drawer-primary"
          @click="closeDrawer"
        >
          <SvgIcon type="mdi" :path="mdilHome" size="0.9rem" />
          <span>Home</span>
        </RouterLink>

        <RouterLink
          :to="allNotesRoute"
          class="flatnotes-note-drawer-primary"
          @click="closeDrawer"
        >
          <SvgIcon type="mdi" :path="mdilNoteMultiple" size="0.9rem" />
          <span>All notes</span>
        </RouterLink>
      </nav>

      <section class="flatnotes-note-drawer-section">
        <div class="flatnotes-note-drawer-section-title">Open</div>
        <div v-if="openTabs.length" class="flatnotes-note-drawer-list">
          <div
            v-for="title in openTabs"
            :key="title"
            class="flatnotes-note-drawer-row"
            :class="{
              'flatnotes-note-drawer-row-active': title === activeTitle,
            }"
          >
            <RouterLink
              :to="{ name: 'note', params: { title } }"
              class="flatnotes-note-drawer-link"
              :title="title"
              @focus="warmNote(title)"
              @pointerenter="warmNote(title)"
              @click="closeDrawer"
            >
              {{ title }}
            </RouterLink>
            <button
              type="button"
              class="flatnotes-note-drawer-row-close"
              title="Close tab"
              aria-label="Close tab"
              @click.stop="closeTab(title)"
            >
              <SvgIcon type="mdi" :path="mdiClose" size="0.72rem" />
            </button>
          </div>
        </div>
        <div v-else class="flatnotes-note-drawer-empty">No open notes</div>
      </section>

      <section class="flatnotes-note-drawer-section">
        <div class="flatnotes-note-drawer-section-title">
          <SvgIcon type="mdi" :path="mdilClock" size="0.95rem" />
          <span>Recent</span>
        </div>
        <div
          v-if="recentOptions.length"
          class="flatnotes-note-drawer-list flatnotes-note-drawer-recent-list"
        >
          <RouterLink
            v-for="title in recentOptions"
            :key="title"
            :to="{ name: 'note', params: { title } }"
            class="flatnotes-note-drawer-recent-link"
            :title="title"
            @focus="warmNote(title)"
            @pointerenter="warmNote(title)"
            @click="closeDrawer"
          >
            {{ title }}
          </RouterLink>
        </div>
        <div v-else class="flatnotes-note-drawer-empty">No recent notes</div>
      </section>
    </aside>
  </div>
</template>

<script setup>
import SvgIcon from "@jamescoyle/vue-icon";
import { mdiBookMultipleOutline, mdiClose } from "@mdi/js";
import {
  mdilChevronRight,
  mdilClock,
  mdilHome,
  mdilNoteMultiple,
} from "@mdi/light-js";
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";

import {
  getCachedSemanticIndex,
  getSemanticIndex,
  libraryIndexUpdatedEvent,
  libraryNoteDeletedEvent,
  prefetchNote,
} from "../api.js";
import { params, searchSortOptions } from "../constants.js";

const maxOpenTabs = 7;
const maxRecentNotes = 14;
const serverRecentTtlMs = 60000;
const openTabsKey = "nirvNotesOpenTabs";
const recentNotesKey = "nirvNotesRecentNotes";
const legacyOpenTabsKey = "flatnotesOpenTabs";
const legacyRecentNotesKey = "flatnotesRecentNotes";

const route = useRoute();
const router = useRouter();
const openTabs = ref(loadTitles(openTabsKey, legacyOpenTabsKey));
const recentTitles = ref(loadTitles(recentNotesKey, legacyRecentNotesKey));
const serverRecentTitles = ref([]);
let serverRecentFetchedAt = 0;
let serverRecentRequest = null;
const drawerVisible = ref(false);
let edgeGesture = null;
let drawerGesture = null;
const prefetchingTitles = new Set();

const activeTitle = computed(() =>
  route.name === "note" && route.params.title ? String(route.params.title) : "",
);

const showFloatingHandle = computed(
  () => !["note", "new", "openFile"].includes(route.name),
);

const allNotesRoute = {
  name: "search",
  query: {
    [params.searchTerm]: "*",
    [params.sortBy]: searchSortOptions.lastModified,
  },
};

const recentOptions = computed(() => {
  const open = new Set(openTabs.value);
  return uniqueTitles([...recentTitles.value, ...serverRecentTitles.value])
    .filter((title) => !open.has(title))
    .slice(0, maxRecentNotes);
});

function loadTitles(key, legacyKey = null) {
  try {
    const storedValue =
      localStorage.getItem(key) ||
      (legacyKey ? localStorage.getItem(legacyKey) : null);
    const parsed = JSON.parse(storedValue || "[]");
    if (!Array.isArray(parsed)) {
      return [];
    }

    const titles = uniqueTitles(
      parsed.filter((title) => typeof title === "string"),
    );
    if (titles.length && !localStorage.getItem(key)) {
      saveTitles(key, titles);
    }
    return titles;
  } catch {
    return [];
  }
}

function saveTitles(key, titles) {
  localStorage.setItem(key, JSON.stringify(uniqueTitles(titles)));
}

function uniqueTitles(titles) {
  return [...new Set(titles.map((title) => title.trim()).filter(Boolean))];
}

function rememberTitle(title) {
  const open = uniqueTitles([
    title,
    ...openTabs.value.filter((existingTitle) => existingTitle !== title),
  ]).slice(0, maxOpenTabs);

  const recent = uniqueTitles([
    title,
    ...recentTitles.value.filter((existingTitle) => existingTitle !== title),
  ]).slice(0, maxRecentNotes);

  openTabs.value = open;
  recentTitles.value = recent;
  saveTitles(openTabsKey, open);
  saveTitles(recentNotesKey, recent);
}

function closeTab(title) {
  const wasActive = title === activeTitle.value;
  const nextTabs = openTabs.value.filter(
    (existingTitle) => existingTitle !== title,
  );
  openTabs.value = nextTabs;
  saveTitles(openTabsKey, nextTabs);

  if (!wasActive) {
    return;
  }

  const nextTitle = nextTabs[0];
  if (nextTitle) {
    router.push({ name: "note", params: { title: nextTitle } });
  } else {
    router.push({ name: "home" });
  }
}

function toggleDrawer() {
  if (drawerVisible.value) {
    closeDrawer();
  } else {
    openDrawer();
  }
}

function openDrawer() {
  drawerVisible.value = true;
  loadServerRecentTitles();
  scheduleLikelyNotePrefetch();
}

function closeDrawer() {
  drawerVisible.value = false;
}

function warmNote(title) {
  const normalizedTitle = String(title || "").trim();
  if (
    !normalizedTitle ||
    normalizedTitle === activeTitle.value ||
    prefetchingTitles.has(normalizedTitle)
  ) {
    return;
  }

  prefetchingTitles.add(normalizedTitle);
  void prefetchNote(normalizedTitle)
    .catch(() => {})
    .finally(() => {
      prefetchingTitles.delete(normalizedTitle);
    });
}

function scheduleLikelyNotePrefetch() {
  if (route.name === "openFile") {
    return;
  }
  const titles = uniqueTitles([...openTabs.value, ...recentTitles.value])
    .filter((title) => title !== activeTitle.value)
    .slice(0, 2);
  if (!titles.length) {
    return;
  }
  const load = () => titles.forEach(warmNote);
  if ("requestIdleCallback" in window) {
    window.requestIdleCallback(load, { timeout: 1800 });
  } else {
    window.setTimeout(load, 700);
  }
}

function loadServerRecentTitles() {
  const now = Date.now();
  if (
    serverRecentTitles.value.length &&
    now - serverRecentFetchedAt < serverRecentTtlMs
  ) {
    return serverRecentRequest || Promise.resolve();
  }

  if (serverRecentRequest) {
    return serverRecentRequest;
  }

  serverRecentRequest = getSemanticIndex()
    .then((index) => {
      applySemanticIndex(index);
      serverRecentFetchedAt = Date.now();
    })
    .catch((error) => {
      console.error(error);
    })
    .finally(() => {
      serverRecentRequest = null;
    });

  return serverRecentRequest;
}

function applySemanticIndex(index, { prune = false } = {}) {
  const sorted = [...(Array.isArray(index) ? index : [])].sort(
    (left, right) =>
      Number(right.lastModified || 0) - Number(left.lastModified || 0),
  );
  const validTitles = new Set(sorted.map((note) => note.title));
  serverRecentTitles.value = sorted
    .map((note) => note.title)
    .slice(0, maxRecentNotes);

  if (!prune) {
    return;
  }
  const nextOpen = openTabs.value.filter((title) => validTitles.has(title));
  const nextRecent = recentTitles.value.filter((title) =>
    validTitles.has(title),
  );
  if (nextOpen.length !== openTabs.value.length) {
    openTabs.value = nextOpen;
    saveTitles(openTabsKey, nextOpen);
  }
  if (nextRecent.length !== recentTitles.value.length) {
    recentTitles.value = nextRecent;
    saveTitles(recentNotesKey, nextRecent);
  }
}

function semanticIndexUpdatedHandler(event) {
  applySemanticIndex(event.detail, { prune: true });
  serverRecentFetchedAt = Date.now();
}

function libraryNoteDeletedHandler(event) {
  const title = String(event.detail?.title || "");
  if (!title) {
    return;
  }
  openTabs.value = openTabs.value.filter((item) => item !== title);
  recentTitles.value = recentTitles.value.filter((item) => item !== title);
  serverRecentTitles.value = serverRecentTitles.value.filter(
    (item) => item !== title,
  );
  saveTitles(openTabsKey, openTabs.value);
  saveTitles(recentNotesKey, recentTitles.value);
}

function isTouchLike(event) {
  return event.pointerType === "touch" || event.pointerType === "pen";
}

function edgePointerDown(event) {
  if (
    drawerVisible.value ||
    !isTouchLike(event) ||
    event.clientX < window.innerWidth - 34
  ) {
    return;
  }

  edgeGesture = {
    pointerId: event.pointerId,
    startX: event.clientX,
    startY: event.clientY,
  };
}

function edgePointerUp(event) {
  if (!edgeGesture || event.pointerId !== edgeGesture.pointerId) {
    return;
  }

  const deltaX = event.clientX - edgeGesture.startX;
  const deltaY = Math.abs(event.clientY - edgeGesture.startY);
  edgeGesture = null;

  if (deltaX <= -56 && deltaY <= 90) {
    openDrawer();
  }
}

function drawerPointerDown(event) {
  if (!drawerVisible.value || !isTouchLike(event)) {
    return;
  }

  drawerGesture = {
    pointerId: event.pointerId,
    startX: event.clientX,
    startY: event.clientY,
  };
}

function drawerPointerUp(event) {
  if (!drawerGesture || event.pointerId !== drawerGesture.pointerId) {
    return;
  }

  const deltaX = event.clientX - drawerGesture.startX;
  const deltaY = Math.abs(event.clientY - drawerGesture.startY);
  drawerGesture = null;

  if (deltaX >= 56 && deltaY <= 90) {
    closeDrawer();
  }
}

function keydownHandler(event) {
  if (event.key === "Escape") {
    closeDrawer();
  }
}

function pointerCancelHandler() {
  edgeGesture = null;
  drawerGesture = null;
}

function toggleDrawerEventHandler() {
  toggleDrawer();
}

watch(
  activeTitle,
  (title) => {
    if (title) {
      rememberTitle(title);
    }
  },
  { immediate: true },
);

watch(
  () => route.fullPath,
  () => {
    closeDrawer();
  },
);

onMounted(() => {
  window.addEventListener(
    "flatnotes:toggle-note-drawer",
    toggleDrawerEventHandler,
  );
  document.addEventListener("keydown", keydownHandler);
  document.addEventListener("pointerdown", edgePointerDown);
  document.addEventListener("pointerup", edgePointerUp);
  document.addEventListener("pointercancel", pointerCancelHandler);
  window.addEventListener(
    libraryIndexUpdatedEvent,
    semanticIndexUpdatedHandler,
  );
  window.addEventListener(libraryNoteDeletedEvent, libraryNoteDeletedHandler);
  applySemanticIndex(getCachedSemanticIndex());
  scheduleLikelyNotePrefetch();
});

onBeforeUnmount(() => {
  window.removeEventListener(
    "flatnotes:toggle-note-drawer",
    toggleDrawerEventHandler,
  );
  document.removeEventListener("keydown", keydownHandler);
  document.removeEventListener("pointerdown", edgePointerDown);
  document.removeEventListener("pointerup", edgePointerUp);
  document.removeEventListener("pointercancel", pointerCancelHandler);
  window.removeEventListener(
    libraryIndexUpdatedEvent,
    semanticIndexUpdatedHandler,
  );
  window.removeEventListener(
    libraryNoteDeletedEvent,
    libraryNoteDeletedHandler,
  );
});
</script>

<style lang="scss" scoped>
.flatnotes-note-drawer-shell {
  pointer-events: none;
}

.flatnotes-note-drawer-handle {
  position: fixed;
  top: 44%;
  right: max(0rem, env(safe-area-inset-right));
  z-index: 70;
  display: inline-flex;
  width: 2.15rem;
  height: 2.05rem;
  transform: translateY(-50%);
  align-items: center;
  justify-content: center;
  border: 1px solid rgb(var(--theme-border));
  border-right: 0;
  border-radius: 999px 0 0 999px;
  color: rgb(var(--theme-text-muted));
  background-color: rgb(var(--theme-background) / 0.86);
  box-shadow: 0 0.25rem 0.8rem rgba(0, 0, 0, 0.12);
  backdrop-filter: blur(10px);
  opacity: 1;
  pointer-events: auto;
  touch-action: manipulation;
  transition:
    background-color 120ms ease,
    border-color 120ms ease,
    color 120ms ease,
    opacity 120ms ease,
    transform 160ms ease;
}

.flatnotes-note-drawer-handle:hover,
.flatnotes-note-drawer-handle:focus-visible,
.flatnotes-note-drawer-handle-open {
  color: rgb(var(--theme-text));
  border-color: rgb(var(--theme-text-muted));
  background-color: rgb(var(--theme-background-elevated) / 0.95);
}

.flatnotes-note-drawer-handle:focus-visible {
  outline: 2px solid rgb(var(--theme-brand));
  outline-offset: 2px;
}

.flatnotes-note-drawer-handle-open {
  transform: translateY(-50%) translateX(0.35rem);
  opacity: 0;
  pointer-events: none;
}

.flatnotes-note-drawer-backdrop {
  position: fixed;
  inset: 0;
  z-index: 68;
  background-color: rgba(0, 0, 0, 0.12);
  pointer-events: auto;
}

.flatnotes-note-drawer {
  position: fixed;
  inset: 0 0 0 auto;
  z-index: 69;
  display: flex;
  width: min(18rem, 82vw);
  transform: translateX(100%);
  flex-direction: column;
  gap: 0.68rem;
  overflow-y: auto;
  padding: max(0.72rem, env(safe-area-inset-top)) 0.78rem
    max(0.72rem, env(safe-area-inset-bottom));
  border-left: 1px solid rgb(var(--theme-border));
  color: rgb(var(--theme-text));
  background-color: rgb(var(--theme-background) / 0.97);
  box-shadow: -0.35rem 0 1.25rem rgba(0, 0, 0, 0.18);
  backdrop-filter: blur(14px);
  pointer-events: auto;
  touch-action: pan-y;
  transition: transform 180ms ease;
}

.flatnotes-note-drawer-open {
  transform: translateX(0);
}

.flatnotes-note-drawer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.45rem;
}

.flatnotes-note-drawer-kicker,
.flatnotes-note-drawer-section-title {
  color: rgb(var(--theme-text-very-muted));
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0;
  text-transform: uppercase;
}

.flatnotes-note-drawer-title {
  color: rgb(var(--theme-text));
  font-size: 1rem;
  font-weight: 650;
}

.flatnotes-note-drawer-close,
.flatnotes-note-drawer-row-close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  color: rgb(var(--theme-text-muted));
}

.flatnotes-note-drawer-close {
  width: 1.75rem;
  height: 1.75rem;
  border: 0;
  background: transparent;
}

.flatnotes-note-drawer-primary,
.flatnotes-note-drawer-row,
.flatnotes-note-drawer-recent-link {
  border: 0;
  border-radius: 0;
  background: transparent;
}

.flatnotes-note-drawer-nav {
  display: flex;
  align-items: center;
  gap: 1rem;
  border-bottom: 1px solid rgb(var(--theme-border) / 0.55);
  padding-bottom: 0.48rem;
}

.flatnotes-note-drawer-primary {
  display: inline-flex;
  min-height: 1.8rem;
  align-items: center;
  gap: 0.42rem;
  padding: 0;
  color: rgb(var(--theme-text-muted));
  font-size: 0.8rem;
  text-decoration: none;
}

.flatnotes-note-drawer-primary.router-link-active {
  color: rgb(var(--theme-brand));
}

.flatnotes-note-drawer-section {
  min-width: 0;
  margin-top: 0.08rem;
}

.flatnotes-note-drawer-section-title {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  margin-bottom: 0.16rem;
}

.flatnotes-note-drawer-list {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 0;
}

.flatnotes-note-drawer-recent-list {
  gap: 0;
}

.flatnotes-note-drawer-row {
  display: flex;
  min-height: 2rem;
  min-width: 0;
  align-items: center;
  gap: 0.3rem;
  border-bottom: 1px solid rgb(var(--theme-border) / 0.38);
  padding: 0.2rem 0.1rem 0.2rem 0.42rem;
}

.flatnotes-note-drawer-row-active {
  box-shadow: inset 2px 0 rgb(var(--theme-brand));
}

.flatnotes-note-drawer-link,
.flatnotes-note-drawer-recent-link {
  min-width: 0;
  overflow: hidden;
  color: rgb(var(--theme-text-muted));
  text-overflow: ellipsis;
  white-space: nowrap;
  text-decoration: none;
}

.flatnotes-note-drawer-link {
  flex: 1 1 auto;
  font-size: 0.84rem;
}

.flatnotes-note-drawer-recent-link {
  display: block;
  min-height: 1.78rem;
  border-bottom: 1px solid rgb(var(--theme-border) / 0.3);
  padding: 0.32rem 0.18rem;
  font-size: 0.8rem;
  line-height: 1.15;
}

.flatnotes-note-drawer-row-close {
  width: 1.35rem;
  height: 1.35rem;
  flex: 0 0 auto;
  font-size: 0.76rem;
}

.flatnotes-note-drawer-primary:hover,
.flatnotes-note-drawer-primary:focus-visible,
.flatnotes-note-drawer-row:hover,
.flatnotes-note-drawer-recent-link:hover,
.flatnotes-note-drawer-recent-link:focus-visible,
.flatnotes-note-drawer-close:hover,
.flatnotes-note-drawer-close:focus-visible,
.flatnotes-note-drawer-row-close:hover,
.flatnotes-note-drawer-row-close:focus-visible {
  color: rgb(var(--theme-text));
  background-color: rgb(var(--theme-background-elevated) / 0.62);
}

.flatnotes-note-drawer-empty {
  color: rgb(var(--theme-text-very-muted));
  font-size: 0.86rem;
}

.flatnotes-note-drawer-fade-enter-active,
.flatnotes-note-drawer-fade-leave-active {
  transition: opacity 140ms ease;
}

.flatnotes-note-drawer-fade-enter-from,
.flatnotes-note-drawer-fade-leave-to {
  opacity: 0;
}

@media (min-width: 768px) {
  .flatnotes-note-drawer-handle {
    top: 50%;
  }
}
</style>
