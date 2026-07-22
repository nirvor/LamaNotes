import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
} from "vue";

const allMatchesHighlightName = "lamanotes-find-matches";
const activeMatchHighlightName = "lamanotes-find-active";
const skippedElementSelector =
  "script, style, template, textarea, input, button";

export function findTextMatches(text = "", query = "", caseSensitive = false) {
  const sourceText = String(text ?? "");
  const queryText = String(query ?? "");
  if (!queryText) {
    return [];
  }

  const source = caseSensitive ? sourceText : sourceText.toLocaleLowerCase();
  const needle = caseSensitive ? queryText : queryText.toLocaleLowerCase();
  const matches = [];
  let offset = 0;
  while (offset <= source.length - needle.length) {
    const start = source.indexOf(needle, offset);
    if (start < 0) {
      break;
    }
    matches.push({ start, end: start + needle.length });
    offset = start + Math.max(needle.length, 1);
  }
  return matches;
}

export function nextDocumentMatchIndex(count, currentIndex, direction = 1) {
  if (!count) {
    return -1;
  }
  const normalizedCurrent = Number.isInteger(currentIndex) ? currentIndex : -1;
  return (normalizedCurrent + (direction < 0 ? -1 : 1) + count) % count;
}

function clearHighlights() {
  globalThis.CSS?.highlights?.delete(allMatchesHighlightName);
  globalThis.CSS?.highlights?.delete(activeMatchHighlightName);
}

function acceptedTextNode(node, root) {
  const parent = node.parentElement;
  return Boolean(
    node.data &&
      parent &&
      root.contains(parent) &&
      !parent.closest(skippedElementSelector),
  );
}

export function createDocumentRanges(root, query) {
  if (!root || !query) {
    return { matches: [], ranges: [] };
  }

  const nodeFilter = globalThis.NodeFilter;
  if (!nodeFilter || !globalThis.document?.createTreeWalker) {
    return { matches: [], ranges: [] };
  }

  const walker = document.createTreeWalker(root, nodeFilter.SHOW_TEXT, {
    acceptNode: (node) =>
      acceptedTextNode(node, root)
        ? nodeFilter.FILTER_ACCEPT
        : nodeFilter.FILTER_REJECT,
  });
  const segments = [];
  let text = "";
  let node = walker.nextNode();
  while (node) {
    const start = text.length;
    text += node.data;
    segments.push({ node, start, end: text.length });
    node = walker.nextNode();
  }

  const matches = findTextMatches(text, query);
  let startSegmentIndex = 0;
  let endSegmentIndex = 0;
  const ranges = matches
    .map((match) => {
      while (
        startSegmentIndex < segments.length &&
        match.start >= segments[startSegmentIndex].end
      ) {
        startSegmentIndex += 1;
      }
      const endOffset = Math.max(match.start, match.end - 1);
      endSegmentIndex = Math.max(endSegmentIndex, startSegmentIndex);
      while (
        endSegmentIndex < segments.length &&
        endOffset >= segments[endSegmentIndex].end
      ) {
        endSegmentIndex += 1;
      }
      const startSegment = segments[startSegmentIndex];
      const endSegment = segments[endSegmentIndex];
      if (!startSegment || !endSegment) {
        return null;
      }

      const range = document.createRange();
      range.setStart(startSegment.node, match.start - startSegment.start);
      range.setEnd(endSegment.node, match.end - endSegment.start);
      return range;
    })
    .filter(Boolean);
  return { matches, ranges };
}

function applyHighlights(ranges, currentIndex) {
  clearHighlights();
  if (!ranges.length || !globalThis.CSS?.highlights || !globalThis.Highlight) {
    return;
  }

  CSS.highlights.set(allMatchesHighlightName, new Highlight(...ranges));
  const activeRange = ranges[currentIndex];
  if (activeRange) {
    CSS.highlights.set(activeMatchHighlightName, new Highlight(activeRange));
  }
}

function scrollRangeIntoView(range) {
  const element = range?.startContainer?.parentElement;
  element?.scrollIntoView?.({ block: "center", inline: "nearest" });
}

function selectedFindText() {
  const selected = String(globalThis.getSelection?.()?.toString() || "").trim();
  return selected && selected.length <= 120 && !/[\r\n]/.test(selected)
    ? selected
    : "";
}

export function useDocumentFind({
  isEditing,
  getEditorText,
  selectEditorRange,
  setEditorMatches,
  getViewRoot,
} = {}) {
  const visible = ref(false);
  const query = ref("");
  const matches = ref([]);
  const currentIndex = ref(-1);
  const findBar = ref();
  const total = computed(() => matches.value.length);
  const current = computed(() =>
    currentIndex.value >= 0 ? currentIndex.value + 1 : 0,
  );
  let viewRanges = [];
  let refreshFrame = null;
  let previousFocus = null;

  function presentCurrentMatch() {
    if (currentIndex.value < 0) {
      return;
    }
    if (isEditing?.()) {
      setEditorMatches?.(matches.value, currentIndex.value);
      const match = matches.value[currentIndex.value];
      selectEditorRange?.(match.start, match.end);
      return;
    }

    applyHighlights(viewRanges, currentIndex.value);
    scrollRangeIntoView(viewRanges[currentIndex.value]);
  }

  function refresh({ resetCurrent = false } = {}) {
    if (refreshFrame != null) {
      cancelAnimationFrame(refreshFrame);
    }
    refreshFrame = requestAnimationFrame(() => {
      refreshFrame = null;
      clearHighlights();
      viewRanges = [];
      if (!visible.value || !query.value) {
        matches.value = [];
        currentIndex.value = -1;
        setEditorMatches?.([], -1);
        return;
      }

      if (isEditing?.()) {
        matches.value = findTextMatches(getEditorText?.() || "", query.value);
      } else {
        const result = createDocumentRanges(getViewRoot?.(), query.value);
        matches.value = result.matches;
        viewRanges = result.ranges;
      }

      if (!matches.value.length) {
        currentIndex.value = -1;
        setEditorMatches?.([], -1);
        return;
      }
      if (
        resetCurrent ||
        currentIndex.value < 0 ||
        currentIndex.value >= matches.value.length
      ) {
        currentIndex.value = 0;
      }
      presentCurrentMatch();
    });
  }

  function open() {
    if (!visible.value) {
      previousFocus = document.activeElement;
      const selected = selectedFindText();
      if (selected) {
        query.value = selected;
      }
      visible.value = true;
      refresh({ resetCurrent: true });
    }
    nextTick(() => findBar.value?.focusSelect?.());
  }

  function close({ restoreFocus = true } = {}) {
    visible.value = false;
    matches.value = [];
    currentIndex.value = -1;
    viewRanges = [];
    clearHighlights();
    setEditorMatches?.([], -1);
    if (restoreFocus && previousFocus instanceof HTMLElement) {
      nextTick(() => previousFocus?.focus?.({ preventScroll: true }));
    }
    previousFocus = null;
  }

  function move(direction = 1) {
    currentIndex.value = nextDocumentMatchIndex(
      matches.value.length,
      currentIndex.value,
      direction,
    );
    presentCurrentMatch();
  }

  function contentChanged() {
    if (visible.value) {
      refresh();
    }
  }

  function keydownHandler(event) {
    if (
      (event.ctrlKey || event.metaKey) &&
      !event.altKey &&
      event.key.toLowerCase() === "f"
    ) {
      event.preventDefault();
      event.stopPropagation();
      open();
      return;
    }
    if (visible.value && event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      close();
    }
  }

  watch(query, () => refresh({ resetCurrent: true }));
  onMounted(() => window.addEventListener("keydown", keydownHandler, true));
  onBeforeUnmount(() => {
    window.removeEventListener("keydown", keydownHandler, true);
    if (refreshFrame != null) {
      cancelAnimationFrame(refreshFrame);
    }
    close({ restoreFocus: false });
  });

  return {
    close,
    contentChanged,
    current,
    currentIndex,
    findBar,
    move,
    open,
    query,
    refresh,
    total,
    visible,
  };
}
