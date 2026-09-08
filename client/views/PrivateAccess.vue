<template>
  <section class="private-view">
    <h1>Private access</h1>
    <p class="private-help">
      Only notes you select here may enter your private assistant workflow. Tags
      never grant access.
    </p>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="message" role="status">{{ message }}</p>
    <fieldset :disabled="busy">
      <legend>Personal notes</legend>
      <ul class="private-rows">
        <li v-for="note in notes" :key="note.title">
          <label
            ><input v-model="selected" type="checkbox" :value="note.title" />{{
              note.title
            }}</label
          >
          <RouterLink
            v-if="enrolled[note.title]"
            :to="`/n/${enrolled[note.title]}/media`"
            >Media</RouterLink
          >
          <button
            v-if="enrolled[note.title]"
            type="button"
            class="private-small-action"
            @click="removeGrant(note.title)"
          >
            Remove access
          </button>
        </li>
      </ul>
      <p v-if="!notes.length" class="private-help">No HTML notes available.</p>
      <button
        type="button"
        :disabled="!selected.length"
        @click="confirmEnrollment = true"
      >
        Allow selected personal notes
      </button>
    </fieldset>
    <fieldset :disabled="busy">
      <legend>Assistant access</legend>
      <label class="private-field"
        >Client name<input
          v-model="clientId"
          maxlength="128"
          autocomplete="off"
          spellcheck="false"
      /></label>
      <label class="private-check"
        ><input v-model="allowCreate" type="checkbox" />Also allow explicitly
        requested new captures and notes</label
      >
      <p class="private-help">
        Read access covers only the selected, enrolled notes. Access expires in
        one hour and can be revoked here.
      </p>
      <button type="button" :disabled="!canIssue" @click="issue">
        Create access
      </button>
      <button v-if="oneTimeToken" type="button" @click="copyToken">
        Copy token once
      </button>
      <ul class="private-rows">
        <li v-for="cap in capabilities" :key="cap.capabilityId">
          <span
            >{{ cap.clientId }}
            <small>{{
              cap.revoked
                ? "Revoked"
                : new Date(cap.expiresAt * 1000).toLocaleString()
            }}</small></span
          >
          <button
            v-if="!cap.revoked"
            type="button"
            class="private-small-action"
            @click="revoke(cap.capabilityId)"
          >
            Revoke
          </button>
        </li>
      </ul>
    </fieldset>
    <ConfirmModal
      v-model="confirmEnrollment"
      title="Allow private assistant access?"
      message="Confirm that the selected notes are personal. Their text, titles and attached media may be read by explicitly granted private clients. Professional material must stay excluded."
      confirm-button-text="Allow selected notes"
      @confirm="enroll"
    />
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import { getNote, getSemanticIndex, clearApiCaches } from "../api.js";
import { privateRequest } from "../privateApi.js";
import ConfirmModal from "../components/ConfirmModal.vue";

const notes = ref([]),
  selected = ref([]),
  enrolled = ref({}),
  capabilities = ref([]);
const error = ref(""),
  message = ref(""),
  busy = ref(false),
  confirmEnrollment = ref(false);
const clientId = ref("openclaw-private"),
  allowCreate = ref(false),
  oneTimeToken = ref("");
const canIssue = computed(
  () =>
    /^[A-Za-z0-9_-]{1,128}$/.test(clientId.value) &&
    (allowCreate.value || selected.value.length > 0) &&
    selected.value.every((title) => enrolled.value[title]),
);

async function act(operation) {
  busy.value = true;
  error.value = "";
  message.value = "";
  try {
    await operation();
  } catch (problem) {
    error.value = problem.message;
  } finally {
    busy.value = false;
  }
}
async function load() {
  const [index, access, caps] = await Promise.all([
    getSemanticIndex(),
    privateRequest("/index"),
    privateRequest("/capabilities"),
  ]);
  notes.value = index.filter((note) => note.format === "html");
  enrolled.value = Object.fromEntries(
    access.items.map((note) => [note.title, note.noteId]),
  );
  capabilities.value = caps.items;
}
function enroll() {
  return act(async () => {
    for (const title of selected.value) {
      const note = await getNote(title, { force: true });
      await privateRequest("/grants/notes", {
        method: "POST",
        body: { title, expectedVersion: note.version, personal: true },
      });
    }
    clearApiCaches();
    await load();
    message.value =
      "Selected notes are enrolled. No client receives access until you create a grant.";
  });
}
function removeGrant(title) {
  return act(async () => {
    await privateRequest(`/grants/${enrolled.value[title]}`, {
      method: "DELETE",
    });
    selected.value = selected.value.filter((value) => value !== title);
    await load();
    message.value = "Private assistant access removed. The note is unchanged.";
  });
}
function issue() {
  return act(async () => {
    const scopes = ["notes:read", "assets:read", "references:read"];
    if (allowCreate.value)
      scopes.push(
        "notes:create",
        "captures:create",
        "captures:read",
        "assets:create",
      );
    const grant = await privateRequest("/capabilities", {
      method: "POST",
      body: {
        clientId: clientId.value,
        scopes,
        expiresIn: 3600,
        noteIds: selected.value.map((title) => enrolled.value[title]),
        captureIds: [],
      },
    });
    oneTimeToken.value = grant.token;
    await load();
    message.value =
      "Access created. Copy the token to the trusted client setup; it is not stored in this browser.";
  });
}
async function copyToken() {
  try {
    await navigator.clipboard.writeText(oneTimeToken.value);
    oneTimeToken.value = "";
    message.value = "Token copied. Keep it out of chats and notes.";
  } catch {
    error.value =
      "Clipboard unavailable. Revoke this grant and use a supported secure browser.";
  }
}
function revoke(id) {
  return act(async () => {
    await privateRequest(`/capabilities/${id}`, { method: "DELETE" });
    oneTimeToken.value = "";
    await load();
  });
}
onMounted(() => act(load));
</script>
