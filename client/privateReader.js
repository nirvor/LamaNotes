import { createApp } from "vue";
import PrivateReader from "./views/PrivateReader.vue";

// This entry never loads the owner app, its store or Library bootstrap.
createApp(PrivateReader).mount("#app");
