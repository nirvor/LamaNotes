<template>
  <div class="flex h-full max-w-[700px] flex-col">
    <!-- Search Input -->
    <SearchInput
      :initialSearchTerm="effectiveSearchTerm"
      class="mb-2"
      showAllOnClear
    />

    <LoadingIndicator ref="loadingIndicator" class="flex-1">
      <!-- Sort By -->
      <div class="flex justify-end">
        <CustomButton
          :label="`Sort By: ${sortByName}`"
          :iconPath="mdiSort"
          class="mb-1"
          @click="toggleSortMenu"
        />
        <PrimeMenu ref="sortMenu" :model="menuItems" :popup="true" />
      </div>

      <!-- Search Results -->
      <div
        v-for="result in results"
        :key="result.title"
        class="mb-4 cursor-pointer rounded px-2 py-1 hover:bg-theme-background-elevated"
      >
        <RouterLink
          :to="{ name: 'note', params: { title: result.title } }"
          @focus="warmNote(result.title)"
          @pointerenter="warmNote(result.title)"
        >
          <!-- Title and Tags -->
          <div>
            <span v-html="result.titleHighlightsOrTitle" class="mr-2"></span>
            <Tag v-for="tag in result.tagMatches" :tag="tag" class="mr-1" />
          </div>
          <!-- Last Modified and Content Highlights -->
          <div>
            <span class="text-theme-text-muted">{{
              result.lastModifiedAsString
            }}</span>
            <span v-if="result.contentHighlights"> - </span>
            <span
              v-html="result.contentHighlights"
              class="text-theme-text-muted"
            ></span>
          </div>
        </RouterLink>
      </div>

      <div
        v-if="results.length === 0"
        class="mt-8 flex flex-col items-center gap-3 text-center text-theme-text-muted"
      >
        <div class="text-sm">No results</div>
        <RouterLink
          v-if="canCreateFromSearch"
          :to="{ name: 'new', query: { title: creatableTitle } }"
        >
          <CustomButton :iconPath="mdiPlusCircle" label="Create Note" />
        </RouterLink>
      </div>
    </LoadingIndicator>
  </div>
</template>

<script setup>
import { useToast } from "primevue/usetoast";
import { computed, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";

import { mdiPlusCircle, mdiSort } from "@mdi/js";
import { apiErrorHandler, getNotes, prefetchNote } from "../api.js";
import CustomButton from "../components/CustomButton.vue";
import LoadingIndicator from "../components/LoadingIndicator.vue";
import PrimeMenu from "../components/PrimeMenu.vue";
import Tag from "../components/Tag.vue";
import { params, searchSortOptions } from "../constants.js";
import SearchInput from "../partials/SearchInput.vue";

const props = defineProps({
  searchTerm: String,
  sortBy: {
    type: Number,
    default: searchSortOptions.score,
  },
});

const loadingIndicator = ref();
const results = ref([]);
const router = useRouter();
const sortMenu = ref();
const toast = useToast();

const effectiveSearchTerm = computed(() => props.searchTerm || "*");
const creatableTitle = computed(() =>
  effectiveSearchTerm.value === "*" ? "" : effectiveSearchTerm.value.trim(),
);
const canCreateFromSearch = computed(() => {
  const title = creatableTitle.value;
  return Boolean(title) && !/^#/.test(title) && !/^[@:+]/.test(title);
});

const sortByName = computed(() => {
  const sortOptionNames = {
    [searchSortOptions.title]: "Title",
    [searchSortOptions.lastModified]: "Last Modified",
    [searchSortOptions.score]: "Score",
  };
  return sortOptionNames[props.sortBy];
});

function init() {
  loadingIndicator.value.setLoading();
  getNotes(effectiveSearchTerm.value)
    .then((data) => {
      results.value = sortResults(data);
      loadingIndicator.value.setLoaded();
    })
    .catch((error) => {
      loadingIndicator.value.setFailed();
      apiErrorHandler(error, toast);
    });
}

function sortResults(results) {
  if (props.sortBy === searchSortOptions.title) {
    return results.sort((a, b) => a.title.localeCompare(b.title));
  } else if (props.sortBy === searchSortOptions.lastModified) {
    return results.sort((a, b) => b.lastModified - a.lastModified);
  } else {
    return results.sort((a, b) => b.score - a.score);
  }
}

function reSortResults() {
  results.value = sortResults(results.value);
}

function updateSortByParam(sortBy) {
  router.push({
    name: "search",
    query: {
      [params.searchTerm]: effectiveSearchTerm.value,
      [params.sortBy]: sortBy,
    },
  });
}

const menuItems = [
  {
    label: "Sort By: Score",
    command: () => {
      updateSortByParam(searchSortOptions.score);
    },
  },

  {
    label: "Sort By: Title",
    command: () => {
      updateSortByParam(searchSortOptions.title);
    },
  },
  {
    label: "Sort By: Last Modified",
    command: () => {
      updateSortByParam(searchSortOptions.lastModified);
    },
  },
];

function toggleSortMenu(event) {
  sortMenu.value.toggle(event);
}

function warmNote(title) {
  void prefetchNote(title).catch(() => {});
}

watch(() => props.searchTerm, init);
watch(() => props.sortBy, reSortResults);
onMounted(init);
</script>

<style>
.match {
  @apply text-theme-brand;
}
</style>
