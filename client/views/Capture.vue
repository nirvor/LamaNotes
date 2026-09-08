<template>
  <section class="private-view">
    <h1>Private capture</h1>
    <p class="private-help">
      Review selected text, a link or files. Nothing is uploaded until you
      choose Import.
    </p>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="message" role="status">{{ message }}</p>
    <form @submit.prevent="importCapture">
      <fieldset :disabled="busy || Boolean(saved)">
        <label class="private-field"
          >Text<textarea v-model="text" rows="5" maxlength="100000" />
        </label>
        <label class="private-field"
          >Source link<input
            v-model="url"
            type="url"
            placeholder="https://"
            maxlength="4000"
        /></label>
        <label class="private-field"
          >Files<input
            type="file"
            multiple
            accept="image/png,image/jpeg,image/webp,image/gif,application/pdf,text/plain,audio/wav,audio/ogg,audio/mpeg,audio/flac"
            @change="selectFiles"
        /></label>
        <ul class="private-rows">
          <li v-for="(file, index) in files" :key="index">
            <span
              >{{ file.name }}
              <small>{{ Math.ceil(file.size / 1024) }} KB</small></span
            >
          </li>
        </ul>
        <img
          v-if="preview"
          :src="preview"
          alt="Local selected image preview"
          class="private-preview"
        />
        <label class="private-check"
          ><input v-model="personal" type="checkbox" required />This selection
          is personal, not professional work.</label
        >
        <button type="submit" :disabled="!canImport">
          {{ busy ? "Importing..." : "Import private capture" }}
        </button>
      </fieldset>
    </form>
    <button v-if="!saved" type="button" :disabled="busy" @click="discard">
      Discard selection
    </button>
    <fieldset v-if="saved" :disabled="busy || Boolean(noteUrl)">
      <legend>Keep as a note</legend>
      <p class="private-help">
        The capture is saved privately. Keeping it as a note adds it to the flat
        Library.
      </p>
      <label class="private-field"
        >Title<input v-model="title" maxlength="180"
      /></label>
      <button type="button" :disabled="!title.trim()" @click="keepAsNote">
        Keep as note
      </button>
    </fieldset>
    <RouterLink v-if="noteRoute" :to="noteRoute">Open saved note</RouterLink>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import {
  onBeforeRouteLeave,
  useRoute,
  useRouter,
  RouterLink,
} from "vue-router";
import { privateRequest } from "../privateApi.js";
import {
  captureKind,
  captureNoteHtml,
  discardIncoming,
  readIncoming,
} from "../captureIntake.js";
import { clearApiCaches } from "../api.js";

const route = useRoute(),
  router = useRouter();
const text = ref(""),
  url = ref(""),
  files = ref([]),
  preview = ref("");
const personal = ref(false),
  busy = ref(false),
  error = ref(""),
  message = ref("");
const saved = ref(null),
  assets = ref([]),
  title = ref(""),
  noteUrl = ref(""),
  noteRoute = ref("");
let importKey = crypto.randomUUID(),
  noteKey = crypto.randomUUID();
const incomingId = String(route.query.incoming || "");
const canImport = computed(
  () =>
    personal.value &&
    (text.value.trim() || url.value.trim() || files.value.length),
);
function selectFiles(event) {
  files.value = [...event.target.files];
}
watch(files, () => {
  if (preview.value) URL.revokeObjectURL(preview.value);
  const image = files.value.find((file) => file.type.startsWith("image/"));
  preview.value = image ? URL.createObjectURL(image) : "";
  assets.value = [];
  importKey = crypto.randomUUID();
});
watch([text, url], () => {
  importKey = crypto.randomUUID();
});
watch(title, () => {
  noteKey = crypto.randomUUID();
});
onMounted(async () => {
  try {
    const incoming = await readIncoming(incomingId);
    if (incoming) {
      text.value = incoming.text || "";
      url.value = incoming.url || "";
      title.value = incoming.title || "";
      files.value = incoming.files || [];
    }
  } catch {
    error.value =
      "The shared selection could not be opened. Please select it again.";
  }
});
async function importCapture() {
  if (!canImport.value || busy.value) return;
  busy.value = true;
  error.value = "";
  try {
    if (
      files.value.length > 10 ||
      files.value.some((file) => file.size > 20 * 1024 * 1024)
    )
      throw new Error("Select up to 10 files, each no larger than 20 MB.");
    for (
      let index = assets.value.length;
      index < files.value.length;
      index += 1
    ) {
      const form = new FormData();
      form.append("file", files.value[index]);
      form.append("role", "source");
      assets.value.push(
        await privateRequest("/assets", {
          method: "POST",
          body: form,
          key: `${importKey}-${index}`,
        }),
      );
    }
    saved.value = await privateRequest("/captures", {
      method: "POST",
      key: importKey,
      body: {
        kind: captureKind(files.value[0], url.value),
        text: text.value,
        sourceUrl: url.value || null,
        assetIds: assets.value.map((asset) => asset.assetId),
        provenance: { channel: incomingId ? "android-share" : "web" },
      },
    });
    await discardIncoming(incomingId);
    message.value = "Private capture imported.";
  } catch (problem) {
    error.value = problem.message;
  } finally {
    busy.value = false;
  }
}
async function keepAsNote() {
  busy.value = true;
  error.value = "";
  try {
    const note = await privateRequest("/notes", {
      method: "POST",
      key: noteKey,
      body: {
        title: title.value.trim(),
        content: captureNoteHtml(text.value, url.value, assets.value),
        captureIds: [saved.value.captureId],
        assetIds: assets.value.map((asset) => asset.assetId),
      },
    });
    noteUrl.value = note.url;
    noteRoute.value = `/n/${note.noteId}`;
    clearApiCaches();
    message.value = "Saved in your private Library.";
  } catch (problem) {
    error.value = problem.message;
  } finally {
    busy.value = false;
  }
}
async function discard() {
  await discardIncoming(incomingId);
  text.value = "";
  url.value = "";
  files.value = [];
  await router.push({ name: "home" });
}
onBeforeRouteLeave(() => {
  if (busy.value) return false;
  if (!saved.value && (text.value || url.value || files.value.length))
    return window.confirm(
      "Leave this capture? It has not been imported. The shared selection remains on this device until discarded.",
    );
});
onBeforeUnmount(() => {
  if (preview.value) URL.revokeObjectURL(preview.value);
});
</script>
