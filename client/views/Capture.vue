<template>
  <section class="private-view capture-view">
    <header class="capture-header"><h1>{{ note ? 'Saved to LamaNotes' : 'Save to LamaNotes' }}</h1><RouterLink to="/" aria-label="Close">Close</RouterLink></header>
    <p v-if="error" role="alert">{{ error }}</p>
    <form v-if="!note" @submit.prevent="importCapture">
      <label class="private-field">Title<input v-model="title" maxlength="180" :disabled="busy" required /></label>
      <fieldset :disabled="busy || Boolean(saved)">
        <label class="private-field">Note<textarea v-model="text" rows="5" maxlength="100000" placeholder="Add a thought..." /></label>
        <label class="private-field">Source link<input v-model="url" type="url" placeholder="https://" maxlength="4000" /></label>
        <label class="capture-add">Add files<input type="file" multiple accept="image/png,image/jpeg,image/webp,image/gif,application/pdf,text/plain,audio/wav,audio/ogg,audio/mpeg,audio/flac,audio/mp4" @change="selectFiles" /></label>
        <ul v-if="files.length" class="capture-files">
          <li v-for="(item,index) in previews" :key="index">
            <img v-if="item.image" :src="item.image" alt="Selected image" />
            <div><span>{{ item.file.name }}</span><small>{{ Math.ceil(item.file.size / 1024) }} KB</small><audio v-if="item.audio" :src="item.audio" controls preload="metadata" /></div>
            <button type="button" :aria-label="`Remove ${item.file.name}`" @click="removeFile(index)">Remove</button>
          </li>
        </ul>
        <label class="private-check"><input v-model="personal" type="checkbox" required />Personal content</label>
      </fieldset>
      <div class="capture-actions"><button class="capture-primary" type="submit" :disabled="busy || !canImport">{{ busy ? progress : 'Save note' }}</button><button type="button" :disabled="busy" @click="discard">Discard</button></div>
    </form>
    <template v-else>
      <h2>{{ note.title }}</h2>
      <div class="capture-actions"><RouterLink class="capture-open" :to="`/n/${note.noteId}`">Open note</RouterLink><button type="button" :disabled="busy" @click="polish">{{ busy ? 'Opening Research...' : 'Polish with Research' }}</button></div>
    </template>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { onBeforeRouteLeave, useRoute, useRouter, RouterLink } from 'vue-router';
import { privateRequest } from '../privateApi.js';
import { captureKind, captureNoteHtml, discardIncoming, readIncoming, sharedSelection, validateSelection } from '../captureIntake.js';
import { clearApiCaches } from '../api.js';

const route = useRoute(), router = useRouter();
const text = ref(''), url = ref(''), files = ref([]), title = ref('');
const personal = ref(false), busy = ref(false), error = ref(''), progress = ref('Saving...');
const saved = ref(null), assets = ref([]), note = ref(null), previews = ref([]);
const incomingId = String(route.query.incoming || '');
let importKey = crypto.randomUUID(), noteKey = crypto.randomUUID();
const canImport = computed(() => personal.value && title.value.trim() && (text.value.trim() || url.value.trim() || files.value.length));
function clearPreviews() { for (const item of previews.value) { if (item.image) URL.revokeObjectURL(item.image); if (item.audio) URL.revokeObjectURL(item.audio); } }
function selectFiles(event) { files.value = [...files.value, ...event.target.files]; event.target.value = ''; }
function removeFile(index) { files.value = files.value.filter((_, i) => i !== index); }
watch(files, () => {
  clearPreviews();
  previews.value = files.value.map(file => ({ file, image: file.type.startsWith('image/') ? URL.createObjectURL(file) : '', audio: file.type.startsWith('audio/') ? URL.createObjectURL(file) : '' }));
  assets.value = []; importKey = crypto.randomUUID();
  if (!title.value && files.value.length) title.value = sharedSelection({ files: files.value }).title;
});
watch([text, url], () => { if (!saved.value) importKey = crypto.randomUUID(); });
watch(title, () => { noteKey = crypto.randomUUID(); });
onMounted(async () => {
  try {
    const incoming = await readIncoming(incomingId);
    if (incoming) {
      const selection = sharedSelection(incoming);
      text.value = selection.text; url.value = selection.url; title.value = selection.title;
      files.value = incoming.files || [];
    }
  } catch { error.value = 'The shared selection could not be opened. Please share it again.'; }
});
async function importCapture() {
  if (!canImport.value || busy.value) return;
  busy.value = true; error.value = '';
  try {
    validateSelection(text.value, url.value, files.value);
    if (!saved.value) {
      for (let index = assets.value.length; index < files.value.length; index++) {
        progress.value = `Saving file ${index + 1} of ${files.value.length}...`;
        const form = new FormData(); form.append('file', files.value[index]); form.append('role', 'source');
        const asset = await privateRequest('/assets', { method: 'POST', body: form, key: `${importKey}-${index}` });
        assets.value.push({ ...asset, name: files.value[index].name });
      }
      progress.value = 'Saving note...';
      saved.value = await privateRequest('/captures', { method: 'POST', key: importKey, body: {
        kind: captureKind(files.value[0], url.value), text: text.value, sourceUrl: url.value || null,
        assetIds: assets.value.map(asset => asset.assetId), provenance: { channel: incomingId ? 'android-share' : 'web' },
      } });
    }
    note.value = await privateRequest('/notes', { method: 'POST', key: noteKey, body: {
      title: title.value.trim(), content: captureNoteHtml(text.value, url.value, assets.value),
      captureIds: [saved.value.captureId], assetIds: assets.value.map(asset => asset.assetId),
    } });
    await discardIncoming(incomingId); clearApiCaches();
  } catch (problem) { error.value = problem.message; }
  finally { busy.value = false; progress.value = 'Saving...'; }
}
async function polish() {
  busy.value = true; error.value = '';
  try {
    const result = await privateRequest('/research-intakes', { method: 'POST', body: { noteId: note.value.noteId, expectedVersion: note.value.version } });
    window.location.assign('https://start.thuber.org/research/#intake=' + encodeURIComponent(result.ticket));
  } catch (problem) { error.value = problem.message; }
  finally { busy.value = false; }
}
async function discard() { await discardIncoming(incomingId); text.value = ''; url.value = ''; files.value = []; await router.push({ name: 'home' }); }
onBeforeRouteLeave(() => {
  if (busy.value) return false;
  if (!note.value && (text.value || url.value || files.value.length)) return window.confirm('Leave this note? The shared selection stays on this device until saved or discarded.');
});
onBeforeUnmount(clearPreviews);
</script>

<style scoped>
.capture-view { margin-block:.75rem; }
.capture-header,.capture-actions { display:flex; align-items:center; gap:.5rem; flex-wrap:wrap; }
.capture-header { justify-content:space-between; }
.capture-header h1 { margin:0; font-size:1.2rem; }
.capture-header a { font-size:var(--ln-font-small); }
.capture-view fieldset { margin:.5rem 0; }
.capture-view h2 { font-size:1.05rem; margin:.8rem 0; }
.capture-add { display:inline-flex; align-items:center; gap:.5rem; font-size:var(--ln-font-small); flex-wrap:wrap; }
.capture-add input { max-width:100%; }
.capture-files { list-style:none; margin:.6rem 0; padding:0; }
.capture-files li { display:flex; gap:.6rem; align-items:center; padding:.5rem 0; border-bottom:1px solid rgb(var(--theme-border)); }
.capture-files li>div { flex:1; min-width:0; }
.capture-files img { width:4.5rem; height:4.5rem; object-fit:cover; border-radius:var(--ln-radius-control); }
.capture-files audio { display:block; width:min(100%,18rem); margin-top:.25rem; }
.capture-files button { flex:none; font-size:var(--ln-font-small); }
.capture-view .capture-primary,.capture-open { background:rgb(var(--theme-brand)); color:white; border:1px solid rgb(var(--theme-brand)); border-radius:var(--ln-radius-control); padding:.4rem .7rem; text-decoration:none; }
.private-check { gap:.4rem; align-items:center; margin-top:.6rem; font-size:var(--ln-font-small); }
.capture-actions { margin-top:.5rem; }
</style>
