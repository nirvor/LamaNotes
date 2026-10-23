<template>
  <section class="private-view">
    <h1>Note media</h1>
    <RouterLink :to="`/n/${noteId}`">Back to note</RouterLink>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="message" role="status">{{ message }}</p>
    <ul class="private-rows">
      <li v-for="asset in assets" :key="asset.assetId">
        <img
          v-if="asset.mediaType.startsWith('image/')"
          :src="`/api/private/v1/assets/${asset.assetId}/content`"
          :alt="
            asset.role === 'source'
              ? 'Imported original'
              : 'Imported derivative'
          "
          class="private-media-thumbnail"
        />
        <span
          >{{ asset.role === "source" ? "Original" : "Derived image" }}
          <small
            >{{ asset.mediaType }} ·
            {{ Math.ceil(asset.size / 1024) }} KB</small
          ></span
        >
        <a :href="`/api/private/v1/assets/${asset.assetId}/content`" download
          >Download</a
        >
        <a
          v-if="cropOrigin && asset.mediaType.startsWith('image/')"
          :href="cropLink(asset.assetId)"
          target="_blank"
          rel="noopener noreferrer"
          >Crop locally</a
        >
      </li>
    </ul>
    <form @submit.prevent="attach">
      <fieldset :disabled="busy">
        <legend>Add source or return a crop</legend>
        <label class="private-field"
          >File<input
            type="file"
            accept="image/png,image/jpeg,image/webp,image/gif,application/pdf,text/plain"
            @change="file = $event.target.files[0] || null"
        /></label>
        <label class="private-field"
          >Original for this crop<select v-model="sourceId">
            <option value="">New source (unchanged original)</option>
            <option
              v-for="(asset, index) in imageAssets"
              :key="asset.assetId"
              :value="asset.assetId"
            >
              {{ asset.role === "source" ? "Original" : "Derived" }}
              {{ index + 1 }} ({{ asset.width }} x {{ asset.height }})
            </option>
          </select></label
        >
        <label v-if="sourceId" class="private-field"
          >Optional crop receipt<input
            type="file"
            accept="application/json,.json"
            @change="receiptFile = $event.target.files[0] || null"
        /></label>
        <label class="private-check"
          ><input v-model="personal" type="checkbox" required />This file is
          personal and may be attached to this note.</label
        >
        <button type="submit" :disabled="!file || !personal">
          {{ busy ? "Attaching..." : "Attach selected file" }}
        </button>
      </fieldset>
    </form>
    <p class="private-help">
      Originals stay unchanged. LamaShop downloads locally. Returning here
      does not upload anything automatically.
    </p>
  </section>
</template>

<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { RouterLink } from "vue-router";
import { privateRequest } from "../privateApi.js";

const props = defineProps({ noteId: String });
const assets = ref([]),
  note = ref(null),
  file = ref(null),
  receiptFile = ref(null);
const sourceId = ref(""),
  personal = ref(false),
  busy = ref(false),
  error = ref(""),
  message = ref("");
const cropOrigin = ref("");
let key = crypto.randomUUID();
const imageAssets = computed(() =>
  assets.value.filter((asset) => asset.mediaType.startsWith("image/")),
);
watch([file, sourceId, receiptFile], () => {
  key = crypto.randomUUID();
});
function cropLink(assetId) {
  return `${cropOrigin.value}#lp=v1&target=lamanotes&return_id=${props.noteId}&source_id=${assetId}`;
}
async function load() {
  cropOrigin.value = (await privateRequest("/settings")).cropOrigin || "";
  note.value = await privateRequest(`/notes/${props.noteId}`);
  assets.value = (await privateRequest(`/notes/${props.noteId}/assets`)).items;
}
async function attach() {
  busy.value = true;
  error.value = "";
  try {
    const form = new FormData();
    form.append("file", file.value);
    form.append("role", sourceId.value ? "derived" : "source");
    if (sourceId.value) form.append("sourceAssetId", sourceId.value);
    if (sourceId.value && receiptFile.value) {
      if (receiptFile.value.size > 16384)
        throw new Error("Choose a small crop receipt JSON file.");
      form.append("cropReceipt", await receiptFile.value.text());
    }
    const asset = await privateRequest("/assets", {
      method: "POST",
      body: form,
      key,
    });
    await privateRequest(`/notes/${props.noteId}/assets`, {
      method: "POST",
      body: { expectedVersion: note.value.version, assetIds: [asset.assetId] },
    });
    await load();
    message.value = "Attached. The original is unchanged.";
    personal.value = false;
  } catch (problem) {
    error.value = problem.message;
    await load().catch(() => {});
  } finally {
    busy.value = false;
  }
}
onMounted(() =>
  load().catch((problem) => {
    error.value = problem.message;
  }),
);
</script>
