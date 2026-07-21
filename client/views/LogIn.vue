<template>
  <div class="flex h-full flex-col items-center justify-center">
    <form @submit.prevent="logIn" class="flex max-w-80 flex-col items-center">
      <CustomButton
        v-if="globalStore.config.googleAuthEnabled"
        type="button"
        :iconPath="mdiGoogle"
        label="Continue with Google"
        style="cta"
        class="mb-4 w-full justify-center py-1.5"
        @click="logInWithGoogle"
      />
      <div
        v-if="
          globalStore.config.googleAuthEnabled &&
          globalStore.config.passwordLoginEnabled !== false
        "
        class="mb-4 flex w-full items-center gap-2 text-xs text-theme-text-muted"
      >
        <span class="h-px flex-1 bg-theme-border"></span>
        <span>or</span>
        <span class="h-px flex-1 bg-theme-border"></span>
      </div>
      <TextInput
        v-if="globalStore.config.passwordLoginEnabled !== false"
        v-model="username"
        id="username"
        placeholder="Username"
        class="mb-1"
        autocomplete="username"
        required
      />
      <TextInput
        v-if="globalStore.config.passwordLoginEnabled !== false"
        v-model="password"
        id="password"
        placeholder="Password"
        type="password"
        class="mb-1"
        autocomplete="current-password"
        required
      />
      <TextInput
        v-if="
          globalStore.config.passwordLoginEnabled !== false &&
          globalStore.config.authType == authTypes.totp
        "
        v-model="totp"
        id="one-time-code"
        placeholder="2FA Code"
        class="mb-1"
        autocomplete="one-time-code"
        required
      />
      <div
        v-if="globalStore.config.passwordLoginEnabled !== false"
        class="mb-4 flex"
      >
        <input
          type="checkbox"
          id="remember-me"
          v-model="rememberMe"
          class="mr-1"
        />
        <label for="remember-me">Remember Me</label>
      </div>
      <CustomButton
        v-if="globalStore.config.passwordLoginEnabled !== false"
        :iconPath="mdilLogin"
        label="Log In"
      />
    </form>
  </div>
</template>

<script setup>
import { mdiGoogle } from "@mdi/js";
import { mdilLogin } from "@mdi/light-js";
import { useToast } from "primevue/usetoast";
import { ref } from "vue";
import { useRouter } from "vue-router";

import { apiErrorHandler, getToken } from "../api.js";
import CustomButton from "../components/CustomButton.vue";
import TextInput from "../components/TextInput.vue";
import { authTypes } from "../constants.js";
import { desktopShell } from "../desktopShell.js";
import { useGlobalStore } from "../globalStore.js";
import { getToastOptions } from "../helpers.js";
import { storeToken } from "../tokenStorage.js";

const props = defineProps({ redirect: String });

const globalStore = useGlobalStore();
const router = useRouter();
const toast = useToast();

const username = ref("");
const password = ref("");
const totp = ref("");
const rememberMe = ref(desktopShell.enabled);

function logIn() {
  getToken(username.value, password.value, totp.value, rememberMe.value)
    .then((access_token) => {
      storeToken(access_token, rememberMe.value);
      if (props.redirect) {
        router.push(props.redirect);
      } else {
        router.push({ name: "home" });
      }
    })
    .catch((error) => {
      username.value = "";
      password.value = "";
      totp.value = "";

      if (error.response?.status === 401) {
        toast.add(
          getToastOptions(
            "Please check your credentials and try again.",
            "Login Failed",
            "error",
          ),
        );
      } else {
        apiErrorHandler(error, toast);
      }
    });
}

function logInWithGoogle() {
  if (desktopShell.enabled && window.pywebview?.api?.start_google_login) {
    Promise.resolve(window.pywebview.api.start_google_login())
      .then((result) => {
        if (!result?.opened) {
          throw new Error(result?.error || "Could not open Google login.");
        }
      })
      .catch(() => {
        toast.add(
          getToastOptions(
            "Could not open the secure browser login.",
            "Google Login Failed",
            "error",
          ),
        );
      });
    return;
  }

  const nextPath =
    typeof props.redirect === "string" && props.redirect.startsWith("/")
      ? props.redirect
      : "/";
  window.location.assign(
    `api/auth/google/start?flow=web&next=${encodeURIComponent(nextPath)}`,
  );
}

// Redirect to home if authentication is disabled.
if (globalStore.config.authType === authTypes.none) {
  router.push({ name: "home" });
}
</script>
