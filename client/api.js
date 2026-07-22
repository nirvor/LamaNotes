import * as constants from "./constants.js";

import { Note, SearchResult } from "./classes.js";

import axios from "axios";
import {
  isCloudNetworkError,
  markCloudOffline,
  markCloudOnline,
} from "./desktopShell.js";
import { getStoredToken } from "./tokenStorage.js";
import { getToastOptions } from "./helpers.js";
import {
  clearWarmLibraryCache,
  getWarmConfig,
  getWarmIndex,
  getWarmNote,
  removeWarmIndexTitles,
  removeWarmNote,
  setWarmConfig,
  setWarmIndex,
  setWarmNote,
} from "./libraryCache.js";
import router from "./router.js";

const api = axios.create();
let configCache = null;
const noteCache = new Map();
const searchCache = new Map();
let semanticIndexCache = null;
let tagCache = null;
let configRequest = null;
let semanticIndexRequest = null;
let semanticIndexRevalidatedAt = 0;
const noteRequests = new Map();
const configCacheTtlMs = 24 * 60 * 60 * 1000;
const noteCacheTtlMs = 5 * 60 * 1000;
const searchCacheTtlMs = 30 * 1000;
const semanticIndexCacheTtlMs = 2 * 60 * 1000;
const semanticIndexRevalidateCooldownMs = 5000;
const tagCacheTtlMs = 2 * 60 * 1000;

export const libraryIndexUpdatedEvent = "lamanotes:library-index-updated";
export const libraryNoteUpdatedEvent = "lamanotes:library-note-updated";
export const libraryNoteDeletedEvent = "lamanotes:library-note-deleted";

api.interceptors.request.use(
  // If the request is not for the token endpoint, add the token to the headers.
  function (config) {
    if (config.url !== "api/token") {
      const token = getStoredToken();
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
    }
    return config;
  },
  function (error) {
    return Promise.reject(error);
  },
);

api.interceptors.response.use(
  function (response) {
    markCloudOnline();
    return response;
  },
  function (error) {
    if (isCloudNetworkError(error)) {
      markCloudOffline();
    } else if (error?.response) {
      markCloudOnline();
    }
    return Promise.reject(error);
  },
);

export function apiErrorHandler(error, toast) {
  if (error.response?.status === 401) {
    const redirectPath = router.currentRoute.value.fullPath;
    router.push({
      name: "login",
      query: { [constants.params.redirect]: redirectPath },
    });
  } else {
    console.error(error);
    toast.add(
      getToastOptions(
        "Unknown error communicating with the server. Please try again.",
        "Unknown Error",
        "error",
      ),
    );
  }
}

export function clearApiCaches() {
  configCache = null;
  noteCache.clear();
  searchCache.clear();
  semanticIndexCache = null;
  tagCache = null;
  clearWarmLibraryCache();
}

function clearIndexCaches() {
  searchCache.clear();
  semanticIndexCache = null;
  tagCache = null;
}

export function getCachedConfig() {
  if (configCache?.data) {
    return { ...configCache.data };
  }
  const warmConfig = getWarmConfig();
  if (warmConfig) {
    configCache = { loadedAt: 0, data: { ...warmConfig } };
    return { ...warmConfig };
  }
  return null;
}

export async function getConfig({ force = false } = {}) {
  if (
    !force &&
    configCache?.data &&
    Date.now() - configCache.loadedAt < configCacheTtlMs
  ) {
    return { ...configCache.data };
  }

  if (!force) {
    const warmConfig = getCachedConfig();
    if (warmConfig) {
      void fetchConfig().catch(() => {});
      return warmConfig;
    }
  }

  return fetchConfig();
}

function fetchConfig() {
  if (configRequest) {
    return configRequest;
  }
  configRequest = api
    .get("api/config")
    .then((response) => {
      configCache = { loadedAt: Date.now(), data: { ...response.data } };
      setWarmConfig(response.data);
      return response.data;
    })
    .finally(() => {
      configRequest = null;
    });
  return configRequest;
}

export async function getToken(username, password, totp, rememberMe = false) {
  try {
    const response = await api.post("api/token", {
      username: username,
      password: totp ? password + totp : password,
      rememberMe: rememberMe,
    });
    return response.data.access_token;
  } catch (response) {
    return Promise.reject(response);
  }
}

export async function logOutSession() {
  try {
    await api.post("api/logout");
  } catch (error) {
    if (error?.response?.status !== 401) {
      return Promise.reject(error);
    }
  }
}

export async function authCheck() {
  try {
    const response = await api.get("api/auth-check");
    return response.data;
  } catch (response) {
    return Promise.reject(response);
  }
}

export async function getNotes(term, sort, order, limit) {
  const cacheKey = JSON.stringify([term, sort, order, limit]);
  const cached = searchCache.get(cacheKey);
  if (cached && Date.now() - cached.loadedAt < searchCacheTtlMs) {
    return cached.data.map((note) => new SearchResult(note));
  }

  try {
    const response = await api.get("api/search", {
      params: {
        term: term,
        sort: sort,
        order: order,
        limit: limit,
      },
    });
    searchCache.set(cacheKey, {
      loadedAt: Date.now(),
      data: response.data,
    });
    return response.data.map((note) => new SearchResult(note));
  } catch (response) {
    return Promise.reject(response);
  }
}

export async function createNote(title, content, format = "html") {
  try {
    const response = await api.post("api/notes", {
      title: title,
      content: content,
      format: format,
    });
    cacheNote(response.data);
    clearIndexCaches();
    void getSemanticIndex({ force: true }).catch(() => {});
    return new Note(response.data);
  } catch (response) {
    return Promise.reject(response);
  }
}

export async function getNote(title) {
  const cacheKey = String(title || "");
  const cached = noteCache.get(cacheKey);
  if (cached && Date.now() - cached.loadedAt < noteCacheTtlMs) {
    return new Note({ ...cached.data });
  }

  const warmNote = getWarmNote(cacheKey);
  if (warmNote) {
    noteCache.set(cacheKey, { loadedAt: 0, data: { ...warmNote } });
    void fetchNote(cacheKey).catch(() => {});
    return new Note(warmNote);
  }

  return fetchNote(cacheKey);
}

export function prefetchNote(title) {
  const cacheKey = String(title || "").trim();
  if (!cacheKey) {
    return Promise.resolve();
  }
  return getNote(cacheKey).then(() => undefined);
}

export async function getNoteContext(title) {
  try {
    const response = await api.get(
      `api/notes/${encodeURIComponent(title)}/context`,
    );
    return response.data;
  } catch (response) {
    return Promise.reject(response);
  }
}

export async function getNotePublication(title) {
  try {
    const response = await api.get(
      `api/notes/${encodeURIComponent(title)}/publication`,
      { headers: { "Cache-Control": "no-cache" } },
    );
    return response.data;
  } catch (response) {
    return Promise.reject(response);
  }
}

export async function publishNote(title, publication) {
  try {
    const response = await api.post(
      `api/notes/${encodeURIComponent(title)}/publication`,
      publication,
    );
    return response.data;
  } catch (response) {
    return Promise.reject(response);
  }
}

export function getCachedSemanticIndex() {
  if (semanticIndexCache?.data) {
    return semanticIndexCache.data.map((note) => ({ ...note }));
  }
  const warmIndex = getWarmIndex();
  if (warmIndex) {
    semanticIndexCache = { loadedAt: 0, data: cloneIndex(warmIndex) };
    return cloneIndex(warmIndex);
  }
  return [];
}

export async function getSemanticIndex({ force = false } = {}) {
  if (
    !force &&
    semanticIndexCache &&
    Date.now() - semanticIndexCache.loadedAt < semanticIndexCacheTtlMs
  ) {
    return semanticIndexCache.data.map((note) => ({ ...note }));
  }

  if (!force) {
    const warmIndex = getCachedSemanticIndex();
    if (warmIndex.length) {
      if (
        Date.now() - semanticIndexRevalidatedAt >=
        semanticIndexRevalidateCooldownMs
      ) {
        void fetchSemanticIndex().catch(() => {});
      }
      return warmIndex;
    }
  }

  return fetchSemanticIndex();
}

export async function updateNote(title, newTitle, newContent, format = "html") {
  try {
    const response = await api.patch(`api/notes/${encodeURIComponent(title)}`, {
      newTitle: newTitle,
      newContent: newContent,
      newFormat: format,
    });
    noteCache.delete(String(title || ""));
    removeWarmNote(title);
    removeWarmIndexTitles([title, newTitle]);
    cacheNote(response.data);
    clearIndexCaches();
    void getSemanticIndex({ force: true }).catch(() => {});
    return new Note(response.data);
  } catch (response) {
    return Promise.reject(response);
  }
}

export async function deleteNote(title) {
  try {
    await api.delete(`api/notes/${encodeURIComponent(title)}`);
    noteCache.delete(String(title || ""));
    removeWarmNote(title);
    removeWarmIndexTitles(title);
    clearIndexCaches();
    dispatchLibraryEvent(libraryNoteDeletedEvent, { title: String(title) });
    void getSemanticIndex({ force: true }).catch(() => {});
  } catch (response) {
    return Promise.reject(response);
  }
}

export async function getTags() {
  if (tagCache && Date.now() - tagCache.loadedAt < tagCacheTtlMs) {
    return [...tagCache.data];
  }

  try {
    const response = await api.get("api/tags");
    tagCache = {
      loadedAt: Date.now(),
      data: [...response.data],
    };
    return response.data;
  } catch (response) {
    return Promise.reject(response);
  }
}

function cacheNote(note) {
  if (!note?.title) {
    return;
  }

  noteCache.set(String(note.title), {
    loadedAt: Date.now(),
    data: { ...note },
  });
  setWarmNote(note);
}

function fetchNote(title) {
  const cacheKey = String(title || "");
  if (noteRequests.has(cacheKey)) {
    return noteRequests.get(cacheKey);
  }
  const request = api
    .get(`api/notes/${encodeURIComponent(cacheKey)}`)
    .then((response) => {
      cacheNote(response.data);
      dispatchLibraryEvent(libraryNoteUpdatedEvent, { ...response.data });
      return new Note(response.data);
    })
    .catch((error) => {
      if (error.response?.status === 404) {
        noteCache.delete(cacheKey);
        removeWarmNote(cacheKey);
        removeWarmIndexTitles(cacheKey);
        dispatchLibraryEvent(libraryNoteDeletedEvent, { title: cacheKey });
      }
      return Promise.reject(error);
    })
    .finally(() => {
      noteRequests.delete(cacheKey);
    });
  noteRequests.set(cacheKey, request);
  return request;
}

function fetchSemanticIndex() {
  if (semanticIndexRequest) {
    return semanticIndexRequest;
  }
  semanticIndexRevalidatedAt = Date.now();
  semanticIndexRequest = api
    .get("api/index")
    .then((response) => {
      const index = cloneIndex(response.data);
      semanticIndexCache = { loadedAt: Date.now(), data: index };
      tagCache = null;
      setWarmIndex(index);
      dispatchLibraryEvent(libraryIndexUpdatedEvent, cloneIndex(index));
      return cloneIndex(index);
    })
    .finally(() => {
      semanticIndexRequest = null;
    });
  return semanticIndexRequest;
}

function cloneIndex(index) {
  return (Array.isArray(index) ? index : []).map((note) => ({
    ...note,
    tags: Array.isArray(note.tags) ? [...note.tags] : [],
  }));
}

function dispatchLibraryEvent(name, detail) {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent(name, { detail }));
  }
}

export async function createAttachment(file) {
  try {
    const formData = new FormData();
    formData.append("file", file);
    const response = await api.post("api/attachments", formData, {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    });
    return response.data;
  } catch (response) {
    return Promise.reject(response);
  }
}
