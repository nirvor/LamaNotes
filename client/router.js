import * as constants from "./constants.js";

import { createRouter, createWebHistory } from "vue-router";

import { authCheck, clearApiCaches } from "./api.js";
import { desktopShell, setDesktopWindowTitle } from "./desktopShell.js";
import { clearStoredToken, getStoredToken } from "./tokenStorage.js";

const loadHomeView = () => import("./views/Home.vue");
const loadNoteView = () => import("./views/Note.vue");
const loadLoginView = () => import("./views/LogIn.vue");
const loadOpenFileView = () => import("./views/OpenFile.vue");
const loadSearchView = () => import("./views/SearchResults.vue");

function parseSearchSort(sortBy) {
  const parsedSort = Number(sortBy);
  return Object.values(constants.searchSortOptions).includes(parsedSort)
    ? parsedSort
    : constants.searchSortOptions.lastModified;
}
const router = createRouter({
  history: createWebHistory(""),
  routes: [
    {
      path: "/",
      name: "home",
      component: loadHomeView,
    },
    {
      path: "/login",
      name: "login",
      component: loadLoginView,
      props: (route) => ({ redirect: route.query[constants.params.redirect] }),
    },
    {
      path: "/note/:title",
      name: "note",
      component: loadNoteView,
      props: true,
    },
    {
      path: "/new",
      name: "new",
      component: loadNoteView,
      props: (route) => ({ initialTitle: route.query.title }),
    },
    {
      path: "/open-file",
      name: "openFile",
      component: loadOpenFileView,
    },
    {
      path: "/search",
      name: "search",
      component: loadSearchView,
      props: (route) => ({
        searchTerm: route.query[constants.params.searchTerm],
        sortBy: parseSearchSort(route.query[constants.params.sortBy]),
      }),
    },
  ],
});

// Check the user is authenticated on first navigation (unless going to login)
let authChecked = false;
let homeViewsPrefetched = false;

function prefetchHomeViews() {
  if (homeViewsPrefetched) {
    return;
  }
  homeViewsPrefetched = true;
  const load = () => {
    Promise.allSettled([loadNoteView(), loadSearchView()]);
  };
  if ("requestIdleCallback" in window) {
    window.requestIdleCallback(load, { timeout: 1800 });
  } else {
    window.setTimeout(load, 700);
  }
}

router.beforeEach(async (to) => {
  if (authChecked || to.name === "login") {
    return;
  }
  if (desktopShell.enabled && to.name === "openFile" && !getStoredToken()) {
    return;
  }
  if (desktopShell.enabled && getStoredToken()) {
    authChecked = true;
    void authCheck().catch((error) => {
      if (error.response?.status === 401) {
        clearApiCaches();
        clearStoredToken();
        void router.replace({
          name: "login",
          query: { [constants.params.redirect]: to.fullPath },
        });
      }
    });
    return;
  }
  try {
    await authCheck();
    return;
  } catch (error) {
    if (error.response && error.response.status === 401) {
      return {
        name: "login",
        query: { [constants.params.redirect]: to.fullPath },
      };
    }
  } finally {
    authChecked = true;
  }
});

router.afterEach((to) => {
  let title = "NirvNotes";
  if (to.name === "note") {
    if (to.params.title) {
      title = String(to.params.title);
    } else {
      title = "New Note";
    }
  } else if (to.name === "openFile") {
    title = "Open File";
  }
  document.title = title;
  if (desktopShell.enabled) {
    if (to.name === "note" && to.params.title) {
      setDesktopWindowTitle(`${String(to.params.title)}.html`);
    } else if (to.name === "new") {
      setDesktopWindowTitle("New Note.html");
    } else if (to.name === "openFile") {
      setDesktopWindowTitle("Open File");
    } else {
      setDesktopWindowTitle("");
    }
  }
  if (to.name === "home") {
    prefetchHomeViews();
  }
});

export default router;
