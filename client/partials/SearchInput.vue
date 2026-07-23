<template>
  <div class="relative w-full">
    <!-- Input -->
    <div
      class="flex w-full rounded-md border border-theme-border bg-theme-background dark:bg-theme-background-elevated"
      :class="{ 'px-3 py-2': !large, 'px-4 py-2.5': large }"
    >
      <IconLabel :iconPath="mdilMagnify" class="mr-2" />
      <input
        type="text"
        ref="input"
        v-model="searchTerm"
        v-focus
        class="w-full bg-transparent focus:outline-none"
        :placeholder="placeholder"
        @keydown="keydownHandler"
        @input="stateChangeHandler"
        @click="stateChangeHandler"
        @focus="stateChangeHandler"
        @blur="hideMenus"
        @keydown.down.prevent
        @keydown.up.prevent
      />
      <!-- Note: Default behaviour for up and down keys is prevented to stop cursor moving when tag menu is navigated. -->
    </div>

    <!-- Tag Menu -->
    <div
      v-if="tagMenuVisible"
      class="absolute z-10 mt-1.5 max-h-56 w-full overflow-scroll rounded-md border border-theme-border bg-theme-background p-1"
    >
      <p
        v-for="(tag, index) in tagMatches"
        ref="tagMenuItems"
        class="cursor-pointer rounded px-2 py-1 hover:bg-theme-background-elevated"
        :class="{ 'bg-theme-background-elevated': index === tagMenuIndex }"
        @click="tagChosen(tag)"
        @mousedown.prevent
      >
        <!-- Note: Default behaviour for mouse down is prevented to stop focus moving to menu on click. -->
        {{ tag }}
      </p>
    </div>

    <!-- Live Note Suggestions -->
    <div
      v-if="suggestionMenuVisible"
      class="lamanotes-search-suggestions"
      role="listbox"
      aria-label="Matching notes"
    >
      <button
        v-for="(suggestion, index) in suggestions"
        :key="suggestion.title"
        ref="suggestionMenuItems"
        type="button"
        class="lamanotes-search-suggestion"
        :class="{ 'is-selected': index === suggestionMenuIndex }"
        role="option"
        :aria-selected="index === suggestionMenuIndex"
        @pointerenter="selectSuggestion(index)"
        @focus="selectSuggestion(index)"
        @pointerdown.prevent
        @click="openSuggestion(suggestion)"
      >
        <span class="lamanotes-search-suggestion-title">{{
          suggestion.title
        }}</span>
        <span
          v-if="formatSuggestionTags(suggestion)"
          class="lamanotes-search-suggestion-tags"
        >
          {{ formatSuggestionTags(suggestion) }}
        </span>
      </button>
    </div>

    <!-- Empty Search Tag Cloud -->
    <div v-if="tagCloudVisible" class="lamanotes-tag-cloud">
      <div class="lamanotes-tag-cloud-list">
        <button
          v-for="tag in topTags"
          :key="tag.name"
          type="button"
          class="lamanotes-tag-cloud-item"
          :title="`${tag.count} ${tag.count === 1 ? 'note' : 'notes'}`"
          @click="tagCloudChosen(tag.name)"
          @mousedown.prevent
        >
          <IconLabel :iconPath="mdiTag" iconSize="0.76em" />
          <span>{{ tag.name }}</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { mdiTag } from "@mdi/js";
import { mdilMagnify } from "@mdi/light-js";
import { useToast } from "primevue/usetoast";
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";

import {
  apiErrorHandler,
  getCachedSemanticIndex,
  getSemanticIndex,
  libraryIndexUpdatedEvent,
  prefetchNote,
} from "../api.js";
import { isCloudNetworkError } from "../desktopShell.js";
import IconLabel from "../components/IconLabel.vue";
import * as constants from "../constants.js";
import { getSearchSuggestions } from "../searchSuggestions.js";
import { isSystemTag } from "../systemTags.js";
import {
  getTagUsage,
  normalizeTagName,
  onTagUsageChange,
  recordTagUse,
} from "../tagUsage.js";

const props = defineProps({
  initialSearchTerm: { type: String, default: "" },
  large: Boolean,
  placeholder: { type: String, default: "Search..." },
  showAllOnClear: Boolean,
});
const emit = defineEmits(["search"]);

const input = ref();
const router = useRouter();
const searchTerm = ref(searchTermForInput(props.initialSearchTerm));
const toast = useToast();
let tags = [];
let tagCloudEntries = [];
let semanticIndexEntries = [];
const tagMatches = ref([]);
const tagMenuItems = ref([]);
const tagMenuIndex = ref(0);
const tagMenuVisible = ref(false);
const tagCloudVisible = ref(false);
const topTags = ref([]);
const suggestions = ref([]);
const suggestionMenuItems = ref([]);
const suggestionMenuIndex = ref(0);
const suggestionMenuVisible = ref(false);
let tagCloudLoaded = false;
const tagCloudLimit = 14;
const suggestionDebounceMs = 120;
let suggestionLoadTimer = null;
let suggestionRun = 0;
const priorityTagBonus = {
  work: 90,
  private: 70,
  infra: 60,
};

function searchTermForInput(value = "") {
  return value === "*" ? "" : value || "";
}

function hideMenus() {
  tagMenuVisible.value = false;
  suggestionMenuVisible.value = false;
  if (searchTerm.value.trim()) {
    tagCloudVisible.value = false;
  } else {
    showTagCloud();
  }
}

function keydownHandler(event) {
  // Tag Menu Open
  if (tagMenuVisible.value) {
    if (event.key === "ArrowDown") {
      tagMenuIndex.value = Math.min(
        tagMenuIndex.value + 1,
        tagMatches.value.length - 1,
      );
      tagMenuItems.value[tagMenuIndex.value].scrollIntoView({
        block: "nearest",
      });
    } else if (event.key === "ArrowUp") {
      tagMenuIndex.value = Math.max(tagMenuIndex.value - 1, 0);
      tagMenuItems.value[tagMenuIndex.value].scrollIntoView({
        block: "nearest",
      });
    } else if (event.key === "Enter") {
      event.preventDefault();
      tagChosen(tagMatches.value[tagMenuIndex.value]);
    } else if (event.key === "Escape") {
      tagMenuVisible.value = false;
      event.stopPropagation(); // Prevent the modal from closing when the tag menu is open.
    }
  }
  // Note Suggestion Menu Open
  else if (suggestionMenuVisible.value) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      selectSuggestion(
        Math.min(suggestionMenuIndex.value + 1, suggestions.value.length - 1),
        true,
      );
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      selectSuggestion(Math.max(suggestionMenuIndex.value - 1, 0), true);
    } else if (event.key === "Enter") {
      event.preventDefault();
      openSuggestion(suggestions.value[suggestionMenuIndex.value]);
    } else if (event.key === "Escape") {
      suggestionMenuVisible.value = false;
    }
  }
  // Tag Menu Closed
  else if (event.key === "Enter") {
    event.preventDefault();
    search();
  }
}

function tagChosen(tag) {
  replaceWordOnCursor(tag);
  tagMenuVisible.value = false;
  queueSuggestionRefresh();
}

function tagCloudChosen(tag) {
  searchTerm.value = `#${tag}`;
  hideMenus();
  search();
}

function search() {
  clearSuggestionLoad();
  suggestionMenuVisible.value = false;
  const term = searchTerm.value.trim();
  const route = getRouteForSearchTerm(term);
  if (route.name === "search") {
    recordTagsFromSearchTerm(term);
  }

  router.push(route);
  emit("search");
}

function getRouteForSearchTerm(term) {
  const normalizedTerm = term.trim();
  const lowerTerm = normalizedTerm.toLowerCase();

  if (!normalizedTerm || ["*", "all", ":all"].includes(lowerTerm)) {
    return {
      name: "search",
      query: {
        [constants.params.searchTerm]: "*",
        [constants.params.sortBy]: constants.searchSortOptions.lastModified,
      },
    };
  }

  if (
    ["file", "file:", "files", "@external", "external", "open"].includes(
      lowerTerm,
    )
  ) {
    return { name: "openFile" };
  }

  const newTitle = getNewNoteTitleFromCommand(normalizedTerm);
  if (newTitle) {
    return { name: "new", query: { title: newTitle } };
  }

  return {
    name: "search",
    query: { [constants.params.searchTerm]: normalizedTerm },
  };
}

function getNewNoteTitleFromCommand(term) {
  if (term.startsWith("+")) {
    return term.slice(1).trim();
  }

  const newMatch = term.match(/^new\s+(.+)$/i);
  return newMatch ? newMatch[1].trim() : "";
}

function recordTagsFromSearchTerm(term) {
  const searchTags = [...term.matchAll(/#[a-zA-Z0-9_-]+/g)].map((match) =>
    normalizeTagName(match[0]),
  );
  recordTagUse(searchTags);
}

function stateChangeHandler() {
  const wordOnCursor = getWordOnCursor();
  const emptySearch = searchTerm.value.trim().length === 0;

  if (emptySearch) {
    clearSuggestionLoad();
    tagMenuVisible.value = false;
    suggestionMenuVisible.value = false;
    suggestions.value = [];
    tagMatches.value = [];
    showTagCloud();
    if (props.showAllOnClear && props.initialSearchTerm !== "*") {
      router.replace({
        name: "search",
        query: {
          [constants.params.searchTerm]: "*",
          [constants.params.sortBy]: constants.searchSortOptions.lastModified,
        },
      });
    }
  } else if (wordOnCursor.charAt(0) !== "#") {
    tagMenuVisible.value = false;
    tagCloudVisible.value = false;
    tagMatches.value = [];
    queueSuggestionRefresh();
  } else {
    tagCloudVisible.value = false;
    suggestionMenuVisible.value = false;
    // All tags are stored in lowercase, so we can do a case-insensitive search.
    filterTagMatches(wordOnCursor.toLowerCase());
  }
}

async function showTagCloud() {
  if (!tagCloudLoaded) {
    try {
      applySemanticIndex(await getSemanticIndex());
    } catch (error) {
      topTags.value = [];
      if (!isCloudNetworkError(error)) {
        apiErrorHandler(error, toast);
      }
    }
  }

  rebuildTopTags();
  tagCloudVisible.value = topTags.value.length > 0;
}

function applySemanticIndex(index) {
  semanticIndexEntries = Array.isArray(index) ? index : [];
  const counts = new Map();
  semanticIndexEntries.forEach((note) => {
    new Set(note.tags || []).forEach((tag) => {
      const normalizedTag = normalizeTagName(tag);
      if (!normalizedTag || isSystemTag(normalizedTag)) {
        return;
      }
      counts.set(normalizedTag, (counts.get(normalizedTag) || 0) + 1);
    });
  });
  tagCloudEntries = [...counts.entries()].map(([name, count]) => ({
    name,
    count,
  }));
  tags = tagCloudEntries.map((tag) => `#${tag.name}`);
  tagCloudLoaded = true;
  rebuildTopTags();
  if (!searchTerm.value.trim()) {
    tagCloudVisible.value = topTags.value.length > 0;
  }
}

function rebuildTopTags() {
  const usage = getTagUsage();
  topTags.value = tagCloudEntries
    .map((tag) => {
      const tagUsage = usage[tag.name] || { count: 0, lastUsed: 0 };
      const ageDays = tagUsage.lastUsed
        ? (Date.now() - tagUsage.lastUsed) / 86400000
        : Infinity;
      const recencyBoost = Number.isFinite(ageDays)
        ? Math.max(0, 18 - ageDays)
        : 0;
      const useBoost = Math.min(Number(tagUsage.count) || 0, 20) * 14;
      const priorityBoost = priorityTagBonus[tag.name] || 0;
      return {
        ...tag,
        score: tag.count * 10 + useBoost + recencyBoost + priorityBoost,
      };
    })
    .sort((left, right) => {
      if (right.score !== left.score) {
        return right.score - left.score;
      }
      if (right.count !== left.count) {
        return right.count - left.count;
      }
      return left.name.localeCompare(right.name);
    })
    .slice(0, tagCloudLimit);
}

async function filterTagMatches(input) {
  if (!tagCloudLoaded) {
    try {
      applySemanticIndex(await getSemanticIndex());
    } catch (error) {
      tags = [];
      if (!isCloudNetworkError(error)) {
        apiErrorHandler(error, toast);
      }
    }
  }
  const currentTagMatchCount = tagMatches.value.length;
  tagMatches.value = tags.filter(
    (tag) => tag.startsWith(input) && tag !== input,
  );
  if (
    currentTagMatchCount !== tagMatches.value.length &&
    tagMatches.value.length > 0
  ) {
    tagMenuIndex.value = 0;
    tagMenuVisible.value = true;
    suggestionMenuVisible.value = false;
  } else if (tagMatches.value.length === 0) {
    tagMenuVisible.value = false;
    queueSuggestionRefresh();
  }
}

function clearSuggestionLoad() {
  window.clearTimeout(suggestionLoadTimer);
  suggestionLoadTimer = null;
  suggestionRun += 1;
}

function setSuggestions(index, term, run) {
  if (run !== suggestionRun || term !== searchTerm.value.trim()) {
    return;
  }
  suggestions.value = getSearchSuggestions(index, term);
  suggestionMenuIndex.value = 0;
  suggestionMenuVisible.value =
    suggestions.value.length > 0 && !tagMenuVisible.value;
  if (suggestions.value[0]) {
    warmSuggestion(suggestions.value[0]);
  }
}

function queueSuggestionRefresh() {
  window.clearTimeout(suggestionLoadTimer);
  const term = searchTerm.value.trim();
  const run = ++suggestionRun;
  if (!term || tagMenuVisible.value) {
    suggestions.value = [];
    suggestionMenuVisible.value = false;
    return;
  }

  const warmIndex = semanticIndexEntries.length
    ? semanticIndexEntries
    : getCachedSemanticIndex();
  if (warmIndex.length) {
    if (!semanticIndexEntries.length) {
      applySemanticIndex(warmIndex);
    }
    setSuggestions(warmIndex, term, run);
    return;
  }

  suggestionMenuVisible.value = false;
  suggestionLoadTimer = window.setTimeout(async () => {
    try {
      const index = await getSemanticIndex();
      if (run !== suggestionRun) {
        return;
      }
      applySemanticIndex(index);
      setSuggestions(index, term, run);
    } catch {
      if (run === suggestionRun) {
        suggestions.value = [];
        suggestionMenuVisible.value = false;
      }
    }
  }, suggestionDebounceMs);
}

function selectSuggestion(index, scrollIntoView = false) {
  suggestionMenuIndex.value = index;
  const suggestion = suggestions.value[index];
  warmSuggestion(suggestion);
  if (scrollIntoView) {
    nextTick(() => {
      suggestionMenuItems.value[index]?.scrollIntoView({ block: "nearest" });
    });
  }
}

function warmSuggestion(suggestion) {
  if (suggestion?.title) {
    void prefetchNote(suggestion.title).catch(() => {});
  }
}

function openSuggestion(suggestion) {
  if (!suggestion?.title) {
    return;
  }
  clearSuggestionLoad();
  suggestionMenuVisible.value = false;
  void router.push({ name: "note", params: { title: suggestion.title } });
  emit("search");
}

function formatSuggestionTags(suggestion) {
  return (Array.isArray(suggestion?.tags) ? suggestion.tags : [])
    .filter((tag) => !isSystemTag(tag))
    .slice(0, 2)
    .join(" · ");
}

// Helpers

/**
 * Returns the word that the cursor is currently on.
 * @returns {Object} An object containing the start and end indices of the word.
 */
function getWordOnCursorPosition() {
  const cursorPosition = input.value.selectionStart;
  const wordStart = Math.max(
    searchTerm.value.lastIndexOf(" ", cursorPosition - 1) + 1,
    0,
  );
  let wordEnd = searchTerm.value.indexOf(" ", cursorPosition);
  if (wordEnd === -1) {
    // If there is no space after the cursor, then the word ends at the end of the input.
    wordEnd = searchTerm.value.length;
  }
  return { start: wordStart, end: wordEnd };
}

/**
 * Retrieves the word at the current cursor position in the search term.
 * @returns {string} The word at the cursor position.
 */
function getWordOnCursor() {
  const { start, end } = getWordOnCursorPosition();
  return searchTerm.value.substring(start, end);
}

/**
 * Replaces the word at the cursor position with the given replacement.
 * @param {string} replacement The word to replace the current word with.
 */
function replaceWordOnCursor(replacement) {
  const { start, end } = getWordOnCursorPosition();
  searchTerm.value =
    searchTerm.value.substring(0, start) +
    replacement +
    searchTerm.value.substring(end);
}

watch(
  () => props.initialSearchTerm,
  () => {
    searchTerm.value = searchTermForInput(props.initialSearchTerm);
  },
  { immediate: true },
);

const stopTagUsageListener = onTagUsageChange(() => {
  if (tagCloudLoaded) {
    rebuildTopTags();
  }
});

function semanticIndexUpdatedHandler(event) {
  applySemanticIndex(event.detail);
  if (searchTerm.value.trim()) {
    queueSuggestionRefresh();
  }
}

onMounted(() => {
  window.addEventListener(
    libraryIndexUpdatedEvent,
    semanticIndexUpdatedHandler,
  );
  const warmIndex = getCachedSemanticIndex();
  if (warmIndex.length) {
    applySemanticIndex(warmIndex);
  }
  if (!searchTerm.value.trim()) {
    showTagCloud();
  } else {
    queueSuggestionRefresh();
  }
});

onBeforeUnmount(() => {
  clearSuggestionLoad();
  stopTagUsageListener();
  window.removeEventListener(
    libraryIndexUpdatedEvent,
    semanticIndexUpdatedHandler,
  );
});
</script>

<style scoped>
.lamanotes-tag-cloud {
  width: 100%;
  padding: 0.42rem 0.15rem 0;
}

.lamanotes-tag-cloud-list {
  display: flex;
  flex-wrap: wrap;
  column-gap: 0.9rem;
  row-gap: 0.18rem;
}

.lamanotes-tag-cloud-item {
  display: inline-flex;
  align-items: center;
  gap: 0.28rem;
  border: 0;
  padding: 0.2rem 0;
  color: rgb(var(--theme-text-muted));
  background: transparent;
  font-size: 0.78rem;
  line-height: 1.15;
  cursor: pointer;
  transition: color 120ms ease;
}

.lamanotes-tag-cloud-item :deep(svg) {
  color: rgb(var(--theme-text-very-muted));
}

.lamanotes-tag-cloud-item:hover,
.lamanotes-tag-cloud-item:focus-visible {
  color: rgb(var(--theme-brand));
}

.lamanotes-tag-cloud-item:focus-visible {
  outline: 2px solid rgb(var(--theme-brand));
  outline-offset: 2px;
  text-decoration: underline;
  text-underline-offset: 0.2rem;
}

.lamanotes-search-suggestions {
  position: absolute;
  z-index: 20;
  width: 100%;
  max-height: 14rem;
  margin-top: 0.35rem;
  overflow-y: auto;
  border: 1px solid rgb(var(--theme-border));
  border-radius: 0.34rem;
  background: rgb(var(--theme-background-elevated));
  box-shadow: 0 0.55rem 1.4rem rgb(0 0 0 / 0.18);
}

.lamanotes-search-suggestion {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 0.8rem;
  width: 100%;
  min-height: 2.15rem;
  padding: 0.38rem 0.62rem;
  border: 0;
  border-bottom: 1px solid rgb(var(--theme-border) / 0.58);
  color: rgb(var(--theme-text));
  background: transparent;
  text-align: left;
  cursor: pointer;
}

.lamanotes-search-suggestion:last-child {
  border-bottom: 0;
}

@media (pointer: coarse), (hover: none) {
  .lamanotes-tag-cloud-item,
  .lamanotes-search-suggestion {
    min-height: var(--ln-touch-target);
  }

  .lamanotes-tag-cloud-item {
    padding-block: 0.45rem;
  }
}

.lamanotes-search-suggestion:hover,
.lamanotes-search-suggestion:focus-visible,
.lamanotes-search-suggestion.is-selected {
  background: rgb(var(--theme-background));
}

.lamanotes-search-suggestion:focus-visible {
  outline: 2px solid rgb(var(--theme-brand));
  outline-offset: -3px;
}

.lamanotes-search-suggestion.is-selected .lamanotes-search-suggestion-title {
  color: rgb(var(--theme-brand));
}

.lamanotes-search-suggestion-title {
  overflow: hidden;
  font-size: 0.88rem;
  line-height: 1.25;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.lamanotes-search-suggestion-tags {
  max-width: 12rem;
  overflow: hidden;
  color: rgb(var(--theme-text-muted));
  font-size: 0.7rem;
  line-height: 1.2;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 520px) {
  .lamanotes-search-suggestion-tags {
    max-width: 7rem;
  }
}
</style>
