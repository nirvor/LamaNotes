<template>
  <section class="flatnotes-csv-preview" aria-label="CSV table preview">
    <div class="flatnotes-csv-summary">
      <span>{{ preview.rows.length }} rows</span>
      <span>{{ preview.columnCount }} columns</span>
      <span>{{ preview.delimiterLabel }} separated</span>
      <span v-if="preview.truncated"
        >first {{ preview.rows.length }} shown</span
      >
    </div>
    <div v-if="preview.columnCount" class="flatnotes-csv-scroll">
      <table>
        <thead>
          <tr>
            <th v-for="(cell, index) in preview.header" :key="index">
              {{ cell || `Column ${index + 1}` }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, rowIndex) in preview.rows" :key="rowIndex">
            <td
              v-for="(cell, cellIndex) in row"
              :key="cellIndex"
              :class="{ 'flatnotes-csv-number': isNumericCsvValue(cell) }"
            >
              {{ cell }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <p v-else class="flatnotes-csv-empty">This CSV file is empty.</p>
  </section>
</template>

<script setup>
import { computed } from "vue";

import { buildCsvPreview, isNumericCsvValue } from "../csvPreview.js";

const props = defineProps({
  source: { type: String, default: "" },
});

const preview = computed(() => buildCsvPreview(props.source));
</script>

<style scoped>
.flatnotes-csv-preview {
  min-width: 0;
  border-block: 1px solid rgb(var(--theme-border));
}

.flatnotes-csv-summary {
  display: flex;
  min-height: 1.8rem;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.35rem 0.8rem;
  padding: 0.28rem 0.35rem;
  color: rgb(var(--theme-text-very-muted));
  font-size: 0.66rem;
  font-weight: 600;
  text-transform: uppercase;
}

.flatnotes-csv-scroll {
  max-width: 100%;
  overflow-x: auto;
  scrollbar-width: thin;
  scrollbar-color: rgb(var(--theme-border)) transparent;
}

table {
  width: max-content;
  min-width: 100%;
  border-collapse: collapse;
  color: rgb(var(--theme-text));
  font-size: 0.78rem;
  line-height: 1.35;
}

th,
td {
  max-width: 24rem;
  border-top: 1px solid rgb(var(--theme-border) / 0.76);
  padding: 0.38rem 0.52rem;
  text-align: left;
  vertical-align: top;
  white-space: pre-wrap;
}

th {
  position: sticky;
  top: 0;
  color: rgb(var(--theme-heading));
  background: rgb(var(--theme-background));
  font-weight: 650;
  white-space: nowrap;
}

tbody tr:nth-child(even) {
  background: rgb(var(--theme-background-elevated) / 0.28);
}

.flatnotes-csv-number {
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.flatnotes-csv-empty {
  margin: 0;
  padding: 0.75rem 0.35rem;
  color: rgb(var(--theme-text-muted));
  font-size: 0.78rem;
}
</style>
