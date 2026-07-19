import {
  mdiCheck,
  mdiClose,
  mdiContentCopy,
  mdiFitToScreenOutline,
  mdiInformationOutline,
  mdiLinkVariant,
  mdiMagnifyMinusOutline,
  mdiMagnifyPlusOutline,
  mdiOpenInNew,
  mdiTag,
} from "@mdi/js";
import { writePlainTextToClipboard } from "../../clipboard.js";
import { isSystemTag } from "../../systemTags.js";
import { recordTagUse } from "../../tagUsage.js";

const codeBlockWrapperClass = "flatnotes-code-block-wrapper";
const codeCopyButtonClass = "flatnotes-code-copy-button";
const copiedClass = "flatnotes-code-copy-button-copied";
const failedClass = "flatnotes-code-copy-button-failed";
const inlineArrowClass = "flatnotes-inline-arrow";
const inlineLatexClass = "flatnotes-inline-latex";
const mediaButtonClass = "flatnotes-media-button";
const mediaFigureClass = "flatnotes-media-figure";
const mediaImageClass = "flatnotes-media-image";
const mediaLightboxClass = "flatnotes-media-lightbox";
const mediaLightboxDrawerOpenClass = "flatnotes-media-lightbox-drawer-open";
const mediaLightboxMenuButtonOpenClass =
  "flatnotes-media-lightbox-menu-button-open";
const mediaLightboxOpenBodyClass = "flatnotes-media-lightbox-open";
const mermaidLanguage = "mermaid";
const mermaidWrapperClass = "flatnotes-mermaid-wrapper";
const mermaidDiagramClass = "flatnotes-mermaid-diagram";
const noteLeadClass = "flatnotes-note-lead";
const noteLeadAbstractClass = "flatnotes-note-lead-abstract";
const noteLeadHeroClass = "flatnotes-note-lead-hero";
const noteLeadHeroImageClass = "flatnotes-note-lead-hero-image";
const noteLeadHiddenTitleClass = "flatnotes-note-hidden-title";
const noteLeadSourceHiddenClass = "flatnotes-note-lead-source-hidden";
const sectionDividerClass = "flatnotes-section-divider";
const bottomTagsClass = "flatnotes-bottom-tags";
const bottomTagChipClass = "flatnotes-bottom-tag-chip";
const taskCheckboxClass = "flatnotes-task-checkbox";
const taskCheckboxSavingClass = "flatnotes-task-checkbox-saving";
const resetDelayMs = 1600;
const maxInlineLatexLength = 500;
const maxLeadSearchElements = 18;
const maxLeadAbstractItems = 3;
const abstractHeadingTexts = new Set([
  "abstract",
  "kurzantwort",
  "kurzfassung",
  "summary",
  "tl;dr",
  "tldr",
  "key points",
  "takeaways",
]);
const ignoredLatexSelector = [
  "a",
  "code",
  "kbd",
  "pre",
  "samp",
  "script",
  "style",
  "textarea",
  ".flatnotes-code-block-wrapper",
  ".katex",
].join(",");
const ignoredArrowSelector = [
  "a",
  "code",
  "kbd",
  "pre",
  "samp",
  "script",
  "style",
  "textarea",
  ".flatnotes-code-block-wrapper",
  ".flatnotes-bottom-tags",
  ".katex",
  `.${inlineArrowClass}`,
  `.${inlineLatexClass}`,
].join(",");

const latexMacros = {
  "\\abs": "\\left\\lvert #1 \\right\\rvert",
  "\\bqty": "\\left[ #1 \\right]",
  "\\bra": "\\left\\langle #1 \\right|",
  "\\braket": "\\left\\langle #1 \\middle| #2 \\right\\rangle",
  "\\Bqty": "\\left\\lbrace #1 \\right\\rbrace",
  "\\curl": "\\nabla\\times",
  "\\dd": "\\,\\mathrm{d}",
  "\\divergence": "\\nabla\\cdot",
  "\\dv": "\\frac{\\mathrm{d} #1}{\\mathrm{d} #2}",
  "\\eval": "\\left. #1 \\right|_{#2}",
  "\\grad": "\\nabla",
  "\\ket": "\\left| #1 \\right\\rangle",
  "\\norm": "\\left\\lVert #1 \\right\\rVert",
  "\\num": "#1",
  "\\per": "\\,/",
  "\\pdv": "\\frac{\\partial #1}{\\partial #2}",
  "\\pqty": "\\left( #1 \\right)",
  "\\qty": "#1\\,#2",
  "\\si": "\\mathrm{#1}",
  "\\unit": "\\,\\mathrm{#1}",
  "\\va": "\\vec{#1}",
  "\\vb": "\\mathbf{#1}",
  "\\vu": "\\hat{\\mathbf{#1}}",
  "\\vqty": "\\left\\lvert #1 \\right\\rvert",
  "\\ampere": "\\mathrm{A}",
  "\\celsius": "^{\\circ}\\mathrm{C}",
  "\\electronvolt": "\\mathrm{eV}",
  "\\hertz": "\\mathrm{Hz}",
  "\\joule": "\\mathrm{J}",
  "\\kilogram": "\\mathrm{kg}",
  "\\meter": "\\mathrm{m}",
  "\\newton": "\\mathrm{N}",
  "\\ohm": "\\Omega",
  "\\second": "\\mathrm{s}",
  "\\tesla": "\\mathrm{T}",
  "\\volt": "\\mathrm{V}",
  "\\watt": "\\mathrm{W}",
};

const latexRenderOptions = {
  displayMode: false,
  macros: latexMacros,
  strict: "ignore",
  throwOnError: true,
  trust: false,
};

let mermaidInstance;
let katexInstance;
let mermaidRenderCounter = 0;
let mediaLightboxElement;
let mediaLightboxLastFocusedElement;
let mediaLightboxObjectUrl = "";
let mediaLightboxZoom = 1;

function createIcon(path) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("focusable", "false");

  const iconPath = document.createElementNS(
    "http://www.w3.org/2000/svg",
    "path",
  );
  iconPath.setAttribute("d", path);
  svg.append(iconPath);

  return svg;
}

function setButtonState(button, state) {
  button.classList.remove(copiedClass, failedClass);
  button.replaceChildren(
    createIcon(state === "copied" ? mdiCheck : mdiContentCopy),
  );

  if (state === "copied") {
    button.classList.add(copiedClass);
    button.setAttribute("aria-label", "Code copied");
    button.setAttribute("title", "Code copied");
    return;
  }

  if (state === "failed") {
    button.classList.add(failedClass);
    button.setAttribute("aria-label", "Copy failed");
    button.setAttribute("title", "Copy failed");
    return;
  }

  button.setAttribute("aria-label", "Copy code");
  button.setAttribute("title", "Copy code");
}

function getBasePath() {
  const basePath = document.querySelector("base")?.getAttribute("href") || "/";
  return basePath === "/" ? "" : basePath.replace(/\/$/, "");
}

function createIconButton({ className, label, path, text }) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = className;
  button.setAttribute("aria-label", label);
  button.setAttribute("title", label);
  button.append(createIcon(path));

  if (text) {
    const labelElement = document.createElement("span");
    labelElement.textContent = text;
    button.append(labelElement);
  }

  return button;
}

function getImageCaption(mediaElement) {
  const directCaption =
    mediaElement.getAttribute("alt")?.trim() ||
    mediaElement.getAttribute("aria-label")?.trim() ||
    mediaElement.querySelector(":scope > title")?.textContent?.trim();
  const figureCaption = mediaElement
    .closest("figure")
    ?.querySelector(":scope > figcaption")
    ?.textContent?.trim();
  return directCaption || figureCaption || "";
}

function getImageUrl(mediaElement) {
  if (mediaElement instanceof SVGElement) {
    const source = new XMLSerializer().serializeToString(mediaElement);
    mediaLightboxObjectUrl = URL.createObjectURL(
      new Blob([source], { type: "image/svg+xml" }),
    );
    return mediaLightboxObjectUrl;
  }

  const source = mediaElement.currentSrc || mediaElement.getAttribute("src");
  if (!source) {
    return "";
  }

  try {
    return new URL(source, window.location.href).href;
  } catch {
    return source;
  }
}

function closeImageLightbox() {
  if (!mediaLightboxElement) {
    return;
  }

  setImageLightboxDrawerOpen(false);
  mediaLightboxElement.overlay.hidden = true;
  document.body.classList.remove(mediaLightboxOpenBodyClass);
  if (mediaLightboxObjectUrl) {
    URL.revokeObjectURL(mediaLightboxObjectUrl);
    mediaLightboxObjectUrl = "";
  }

  if (mediaLightboxLastFocusedElement?.focus) {
    mediaLightboxLastFocusedElement.focus();
  }
}

function setImageLightboxZoom(nextZoom) {
  if (!mediaLightboxElement) {
    return;
  }

  mediaLightboxZoom = Math.min(4, Math.max(0.5, nextZoom));
  mediaLightboxElement.image.style.setProperty(
    "--flatnotes-media-zoom",
    String(mediaLightboxZoom),
  );
  mediaLightboxElement.resetZoomButton.setAttribute(
    "aria-label",
    `Reset zoom (${Math.round(mediaLightboxZoom * 100)}%)`,
  );
  mediaLightboxElement.resetZoomButton.setAttribute(
    "title",
    `Reset zoom (${Math.round(mediaLightboxZoom * 100)}%)`,
  );
}

function setImageLightboxDrawerOpen(isOpen, options = {}) {
  if (!mediaLightboxElement) {
    return;
  }

  const { drawer, drawerButton } = mediaLightboxElement;
  drawer.classList.toggle(mediaLightboxDrawerOpenClass, isOpen);
  drawer.setAttribute("aria-hidden", String(!isOpen));
  drawer.inert = !isOpen;
  drawerButton.classList.toggle(mediaLightboxMenuButtonOpenClass, isOpen);
  drawerButton.setAttribute("aria-expanded", String(isOpen));
  drawerButton.setAttribute(
    "aria-label",
    isOpen ? "Close media actions" : "Open media actions",
  );
  drawerButton.setAttribute(
    "title",
    isOpen ? "Close media actions" : "Open media actions",
  );

  if (options.focus) {
    if (isOpen) {
      drawer.querySelector("a, button")?.focus();
    } else {
      drawerButton.focus();
    }
  }
}

function toggleImageLightboxDrawer() {
  if (!mediaLightboxElement) {
    return;
  }

  const isOpen = mediaLightboxElement.drawer.classList.contains(
    mediaLightboxDrawerOpenClass,
  );
  setImageLightboxDrawerOpen(!isOpen, { focus: true });
}

function safeSetPointerCapture(element, pointerId) {
  try {
    element.setPointerCapture?.(pointerId);
  } catch {
    // Synthetic or interrupted pointer events may not be capturable.
  }
}

function attachImageLightboxGestures(overlay, drawer) {
  const edgeWidth = 36;
  const maxVerticalDrift = 90;
  const minSwipeDistance = 56;
  let edgeGesture = null;
  let drawerGesture = null;

  function isTouchLike(event) {
    return event.pointerType === "touch" || event.pointerType === "pen";
  }

  function isIgnoredTarget(target) {
    return (
      target instanceof Element &&
      target.closest(
        ".flatnotes-media-lightbox-drawer, .flatnotes-media-lightbox-menu-button",
      )
    );
  }

  overlay.addEventListener("pointerdown", (event) => {
    if (
      overlay.hidden ||
      !isTouchLike(event) ||
      isIgnoredTarget(event.target) ||
      event.clientX < window.innerWidth - edgeWidth
    ) {
      return;
    }

    edgeGesture = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
    };
    safeSetPointerCapture(overlay, event.pointerId);
  });

  overlay.addEventListener("pointerup", (event) => {
    if (!edgeGesture || event.pointerId !== edgeGesture.pointerId) {
      return;
    }

    const deltaX = event.clientX - edgeGesture.startX;
    const deltaY = Math.abs(event.clientY - edgeGesture.startY);
    edgeGesture = null;

    if (deltaX <= -minSwipeDistance && deltaY <= maxVerticalDrift) {
      setImageLightboxDrawerOpen(true, { focus: true });
    }
  });

  overlay.addEventListener("pointercancel", () => {
    edgeGesture = null;
  });

  drawer.addEventListener("pointerdown", (event) => {
    if (!isTouchLike(event)) {
      return;
    }

    drawerGesture = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
    };
    safeSetPointerCapture(drawer, event.pointerId);
  });

  drawer.addEventListener("pointerup", (event) => {
    if (!drawerGesture || event.pointerId !== drawerGesture.pointerId) {
      return;
    }

    const deltaX = event.clientX - drawerGesture.startX;
    const deltaY = Math.abs(event.clientY - drawerGesture.startY);
    drawerGesture = null;

    if (deltaX >= minSwipeDistance && deltaY <= maxVerticalDrift) {
      setImageLightboxDrawerOpen(false, { focus: true });
    }
  });

  drawer.addEventListener("pointercancel", () => {
    drawerGesture = null;
  });
}

function createImageLightbox() {
  const overlay = document.createElement("div");
  overlay.className = mediaLightboxClass;
  overlay.hidden = true;
  overlay.setAttribute("role", "dialog");
  overlay.setAttribute("aria-modal", "true");
  overlay.setAttribute("aria-label", "Media preview");

  const panel = document.createElement("div");
  panel.className = "flatnotes-media-lightbox-panel";

  const image = document.createElement("img");
  image.className = "flatnotes-media-lightbox-image";
  image.alt = "";

  const controls = document.createElement("div");
  controls.className = "flatnotes-media-lightbox-controls";
  const zoomOutButton = createIconButton({
    className: "flatnotes-media-lightbox-control",
    label: "Zoom out",
    path: mdiMagnifyMinusOutline,
  });
  const resetZoomButton = createIconButton({
    className: "flatnotes-media-lightbox-control",
    label: "Reset zoom",
    path: mdiFitToScreenOutline,
  });
  const zoomInButton = createIconButton({
    className: "flatnotes-media-lightbox-control",
    label: "Zoom in",
    path: mdiMagnifyPlusOutline,
  });
  const closeButton = createIconButton({
    className: "flatnotes-media-lightbox-control",
    label: "Close media preview",
    path: mdiClose,
  });
  controls.append(zoomOutButton, resetZoomButton, zoomInButton, closeButton);

  const drawerButton = createIconButton({
    className:
      "flatnotes-media-lightbox-control flatnotes-media-lightbox-menu-button",
    label: "Open media actions",
    path: mdiInformationOutline,
  });
  drawerButton.setAttribute("aria-controls", "flatnotes-media-lightbox-drawer");
  drawerButton.setAttribute("aria-expanded", "false");

  const drawer = document.createElement("aside");
  drawer.id = "flatnotes-media-lightbox-drawer";
  drawer.className = "flatnotes-media-lightbox-drawer";
  drawer.setAttribute("aria-hidden", "true");
  drawer.setAttribute("aria-label", "Media actions");
  drawer.inert = true;

  const drawerHeader = document.createElement("div");
  drawerHeader.className = "flatnotes-media-lightbox-drawer-header";

  const drawerTitle = document.createElement("div");
  drawerTitle.className = "flatnotes-media-lightbox-drawer-title";
  drawerTitle.textContent = "Media";

  const drawerCloseButton = createIconButton({
    className: "flatnotes-media-lightbox-drawer-close",
    label: "Close media actions",
    path: mdiClose,
  });

  drawerHeader.append(drawerTitle, drawerCloseButton);

  const captionBlock = document.createElement("div");
  captionBlock.className = "flatnotes-media-lightbox-caption-block";

  const captionLabel = document.createElement("div");
  captionLabel.className = "flatnotes-media-lightbox-caption-label";
  captionLabel.textContent = "Caption";

  const caption = document.createElement("div");
  caption.className = "flatnotes-media-lightbox-caption";

  captionBlock.append(captionLabel, caption);

  const actions = document.createElement("div");
  actions.className = "flatnotes-media-lightbox-drawer-actions";

  const originalLink = document.createElement("a");
  originalLink.className = "flatnotes-media-lightbox-drawer-action";
  originalLink.target = "_blank";
  originalLink.rel = "noopener noreferrer";
  originalLink.setAttribute("aria-label", "Open original media");
  originalLink.setAttribute("title", "Open original media");
  originalLink.append(
    createIcon(mdiOpenInNew),
    document.createTextNode("Open original"),
  );

  const copyButton = createIconButton({
    className: "flatnotes-media-lightbox-drawer-action",
    label: "Copy image link",
    path: mdiLinkVariant,
    text: "Copy link",
  });

  const closePreviewButton = createIconButton({
    className: "flatnotes-media-lightbox-drawer-action",
    label: "Close image preview",
    path: mdiClose,
    text: "Close preview",
  });

  actions.append(originalLink, copyButton, closePreviewButton);
  drawer.append(drawerHeader, captionBlock, actions);

  controls.insertBefore(drawerButton, closeButton);
  panel.append(image);
  overlay.append(panel, controls, drawer);
  document.body.append(overlay);

  overlay.addEventListener("click", (event) => {
    if (event.target === overlay) {
      closeImageLightbox();
    }
  });

  drawerButton.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    toggleImageLightboxDrawer();
  });

  drawerCloseButton.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    setImageLightboxDrawerOpen(false, { focus: true });
  });

  closePreviewButton.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    closeImageLightbox();
  });

  closeButton.addEventListener("click", closeImageLightbox);
  zoomOutButton.addEventListener("click", () =>
    setImageLightboxZoom(mediaLightboxZoom - 0.25),
  );
  resetZoomButton.addEventListener("click", () => setImageLightboxZoom(1));
  zoomInButton.addEventListener("click", () =>
    setImageLightboxZoom(mediaLightboxZoom + 0.25),
  );
  image.addEventListener("dblclick", () =>
    setImageLightboxZoom(mediaLightboxZoom === 1 ? 2 : 1),
  );

  document.addEventListener("keydown", (event) => {
    if (overlay.hidden) {
      return;
    }
    if (event.key === "Escape") {
      closeImageLightbox();
    } else if (event.key === "+" || event.key === "=") {
      setImageLightboxZoom(mediaLightboxZoom + 0.25);
    } else if (event.key === "-") {
      setImageLightboxZoom(mediaLightboxZoom - 0.25);
    } else if (event.key === "0") {
      setImageLightboxZoom(1);
    }
  });

  copyButton.addEventListener("click", async () => {
    const url = copyButton.dataset.flatnotesImageUrl;
    if (!url) {
      return;
    }

    copyButton.disabled = true;
    try {
      await writePlainTextToClipboard(url);
      copyButton.querySelector("span").textContent = "Copied";
    } catch {
      copyButton.querySelector("span").textContent = "Failed";
    } finally {
      window.setTimeout(() => {
        copyButton.querySelector("span").textContent = "Copy link";
        copyButton.disabled = false;
      }, resetDelayMs);
    }
  });

  attachImageLightboxGestures(overlay, drawer);

  return {
    caption,
    closeButton,
    closePreviewButton,
    copyButton,
    drawer,
    drawerButton,
    drawerCloseButton,
    image,
    originalLink,
    overlay,
    resetZoomButton,
    zoomInButton,
    zoomOutButton,
  };
}

function getImageLightbox() {
  if (!mediaLightboxElement) {
    mediaLightboxElement = createImageLightbox();
  }

  return mediaLightboxElement;
}

function openImageLightbox(mediaElement) {
  if (mediaLightboxObjectUrl) {
    URL.revokeObjectURL(mediaLightboxObjectUrl);
    mediaLightboxObjectUrl = "";
  }
  const url = getImageUrl(mediaElement);
  if (!url) {
    return;
  }

  const { caption, copyButton, drawerButton, image, originalLink, overlay } =
    getImageLightbox();
  const captionText = getImageCaption(mediaElement);

  mediaLightboxLastFocusedElement = document.activeElement;
  image.src = url;
  image.alt = captionText || "Preview image";
  caption.textContent = captionText || "Image preview";
  caption.classList.toggle(
    "flatnotes-media-lightbox-caption-muted",
    !captionText,
  );
  originalLink.href = url;
  copyButton.dataset.flatnotesImageUrl = url;
  overlay.hidden = false;
  document.body.classList.add(mediaLightboxOpenBodyClass);
  setImageLightboxZoom(1);
  setImageLightboxDrawerOpen(false);
  drawerButton.focus();
}

function isSoloImageParagraph(imageElement) {
  const parent = imageElement.parentElement;
  return (
    parent?.tagName === "P" &&
    [...parent.childNodes].every(
      (node) => node === imageElement || !node.textContent.trim(),
    )
  );
}

function createMediaFigure(imageElement) {
  const figure = document.createElement("figure");
  figure.className = mediaFigureClass;

  const button = document.createElement("button");
  button.type = "button";
  button.className = mediaButtonClass;
  button.setAttribute("aria-label", "Open image preview");
  button.setAttribute("title", "Open image preview");

  imageElement.classList.add(mediaImageClass);
  imageElement.loading = imageElement.loading || "lazy";
  imageElement.decoding = imageElement.decoding || "async";
  button.append(imageElement);

  const captionText = getImageCaption(imageElement);
  if (captionText) {
    const caption = document.createElement("figcaption");
    caption.textContent = captionText;
    figure.append(button, caption);
  } else {
    figure.append(button);
  }

  button.addEventListener("click", () => openImageLightbox(imageElement));
  return figure;
}

function decorateMediaImage(imageElement) {
  if (
    imageElement.dataset.flatnotesMediaEnhanced === "true" ||
    imageElement.closest(`.${mediaFigureClass}`) ||
    imageElement.closest("a") ||
    !getImageUrl(imageElement)
  ) {
    return;
  }

  imageElement.dataset.flatnotesMediaEnhanced = "true";

  if (isSoloImageParagraph(imageElement)) {
    const paragraph = imageElement.parentElement;
    const figure = createMediaFigure(imageElement);
    paragraph.replaceWith(figure);
    return;
  }

  if (
    imageElement.parentElement?.classList.contains("toastui-editor-contents")
  ) {
    imageElement.replaceWith(createMediaFigure(imageElement));
    return;
  }

  imageElement.classList.add(mediaImageClass);
  imageElement.setAttribute("role", "button");
  imageElement.setAttribute("tabindex", "0");
  imageElement.setAttribute("title", "Open media detail");
  imageElement.addEventListener("click", () => openImageLightbox(imageElement));
  imageElement.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      openImageLightbox(imageElement);
    }
  });
}

function decorateMediaDiagram(svgElement) {
  if (svgElement.dataset.flatnotesMediaEnhanced === "true") {
    return;
  }

  svgElement.dataset.flatnotesMediaEnhanced = "true";
  svgElement.classList.add(mediaImageClass);
  svgElement.setAttribute("role", "button");
  svgElement.setAttribute("tabindex", "0");
  svgElement.setAttribute("title", "Open media detail");
  svgElement.addEventListener("click", () => openImageLightbox(svgElement));
  svgElement.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      openImageLightbox(svgElement);
    }
  });
}

export function enhanceMediaImages(rootElement) {
  if (!rootElement) {
    return;
  }

  const contentRoot = rootElement.querySelector(".toastui-editor-contents");
  if (!contentRoot) {
    return;
  }

  contentRoot.querySelectorAll("img").forEach(decorateMediaImage);
  contentRoot
    .querySelectorAll(
      [
        ".flatnotes-mermaid-diagram svg",
        '[data-flatnotes-component="plot"] svg',
        '[data-flatnotes-component="diagram"] svg',
        '[data-flatnotes-component="map"] svg',
        ".flatnote-plot svg",
        ".flatnote-diagram svg",
        ".flatnote-map svg",
        "figure > svg",
      ].join(","),
    )
    .forEach(decorateMediaDiagram);
}

function normalizeLeadText(text) {
  return text.replace(/\s+/g, " ").trim().toLowerCase();
}

function getMeaningfulChildren(contentRoot) {
  return [...contentRoot.children].filter((element) => {
    if (element.classList.contains(noteLeadClass)) {
      return false;
    }

    return element.textContent.trim() || element.querySelector("img");
  });
}

function getPrimaryContentContainer(contentRoot) {
  const children = getMeaningfulChildren(contentRoot);
  if (
    children.length === 1 &&
    children[0].matches("article, main, .flatnote")
  ) {
    return children[0];
  }

  return contentRoot;
}

function hideDuplicateMarkdownTitle(contentRoot, noteTitle) {
  if (!noteTitle) {
    return;
  }

  const firstElement = getMeaningfulChildren(contentRoot)
    .slice(0, 4)
    .find((element) => element.tagName === "H1");
  if (
    !firstElement ||
    normalizeLeadText(firstElement.textContent) !== normalizeLeadText(noteTitle)
  ) {
    return;
  }

  firstElement.classList.add(noteLeadHiddenTitleClass);
  firstElement.setAttribute("aria-hidden", "true");
}

function isAbstractHeading(element) {
  if (!/^H[1-6]$/.test(element.tagName)) {
    return false;
  }

  return abstractHeadingTexts.has(normalizeLeadText(element.textContent));
}

function findNextList(children, startIndex) {
  for (
    let index = startIndex + 1;
    index < Math.min(children.length, startIndex + 5);
    index += 1
  ) {
    const element = children[index];
    if (/^H[1-6]$/.test(element.tagName)) {
      return null;
    }

    if (element.matches("ul, ol")) {
      return element;
    }
  }

  return null;
}

function isUsableLeadList(listElement) {
  if (!listElement || !listElement.matches("ul, ol")) {
    return false;
  }

  if (listElement.querySelector("input[type='checkbox']")) {
    return false;
  }

  const items = [...listElement.querySelectorAll(":scope > li")];
  return items.length >= 2 && items.length <= 9;
}

function findLeadAbstractList(contentRoot) {
  const children = getMeaningfulChildren(contentRoot).slice(
    0,
    maxLeadSearchElements,
  );

  for (let index = 0; index < children.length; index += 1) {
    if (!isAbstractHeading(children[index])) {
      continue;
    }

    const listElement = findNextList(children, index);
    if (isUsableLeadList(listElement)) {
      return {
        headingElement: children[index],
        listElement,
        shouldHideSource: true,
      };
    }
  }

  const fallbackList = children.find((element) => isUsableLeadList(element));
  if (!fallbackList) {
    return null;
  }

  return {
    headingElement: null,
    listElement: fallbackList,
    shouldHideSource: false,
  };
}

function createLeadAbstract(sourceList) {
  const abstract = document.createElement("section");
  abstract.className = noteLeadAbstractClass;
  abstract.setAttribute("aria-label", "Note summary");

  const list = sourceList.cloneNode(true);
  list.querySelectorAll("input").forEach((input) => input.remove());
  [...list.querySelectorAll(":scope > li")]
    .slice(maxLeadAbstractItems)
    .forEach((item) => item.remove());

  abstract.append(list);
  return abstract;
}

function hidePromotedLeadSource(abstractMatch) {
  if (!abstractMatch?.shouldHideSource) {
    return;
  }

  [abstractMatch.headingElement, abstractMatch.listElement]
    .filter(Boolean)
    .forEach((element) => {
      element.classList.add(noteLeadSourceHiddenClass);
      element.setAttribute("aria-hidden", "true");
    });
}

function hidePromotedHeroSource(sourceImage) {
  if (!sourceImage) {
    return;
  }

  const sourceContainer =
    sourceImage.closest(`.${mediaFigureClass}`) ||
    sourceImage.closest("p") ||
    sourceImage;

  sourceContainer.classList.add(noteLeadSourceHiddenClass);
  sourceContainer.setAttribute("aria-hidden", "true");
}

function getFirstLeadImage(contentRoot) {
  return contentRoot.querySelector(
    `.${mediaFigureClass} img, .toastui-editor-contents > img, .toastui-editor-contents p > img`,
  );
}

function createLeadHero(sourceImage) {
  const imageSource = sourceImage.currentSrc || sourceImage.getAttribute("src");
  if (!imageSource) {
    return null;
  }

  const figure = document.createElement("figure");
  figure.className = noteLeadHeroClass;

  const button = document.createElement("button");
  button.type = "button";
  button.className = "flatnotes-note-lead-hero-button";
  button.setAttribute("aria-label", "Open hero image preview");
  button.setAttribute("title", "Open image preview");

  const image = document.createElement("img");
  image.className = noteLeadHeroImageClass;
  image.src = imageSource;
  image.alt = getImageCaption(sourceImage) || "Note image";
  image.loading = "eager";
  image.decoding = "async";

  button.addEventListener("click", () => openImageLightbox(image));
  button.append(image);
  figure.append(button);

  const captionText = getImageCaption(sourceImage);
  if (captionText) {
    const caption = document.createElement("figcaption");
    caption.textContent = captionText;
    figure.append(caption);
  }

  return figure;
}

export function enhanceNoteLead(rootElement, options = {}) {
  if (!rootElement) {
    return;
  }

  const outerContentRoot = rootElement.querySelector(
    ".toastui-editor-contents",
  );
  const contentRoot = outerContentRoot
    ? getPrimaryContentContainer(outerContentRoot)
    : null;
  if (!contentRoot || contentRoot.querySelector(`.${noteLeadClass}`)) {
    return;
  }

  hideDuplicateMarkdownTitle(contentRoot, options.noteTitle);

  if (contentRoot.querySelector(".flatnote-hero, .flatnote-banner")) {
    return;
  }

  const abstractMatch = findLeadAbstractList(contentRoot);
  const heroImage = getFirstLeadImage(contentRoot);
  if (!abstractMatch && !heroImage) {
    return;
  }

  const lead = document.createElement("section");
  lead.className = noteLeadClass;

  if (abstractMatch) {
    lead.append(createLeadAbstract(abstractMatch.listElement));
  }

  let promotedHeroImage = null;
  if (heroImage) {
    const hero = createLeadHero(heroImage);
    if (hero) {
      lead.append(hero);
      promotedHeroImage = heroImage;
    }
  }

  if (!lead.children.length) {
    return;
  }

  hidePromotedLeadSource(abstractMatch);
  hidePromotedHeroSource(promotedHeroImage);
  contentRoot.prepend(lead);
}

function normalizeTag(tag) {
  return tag.replace(/^#/, "").trim().toLowerCase();
}

function getTagsFromText(text) {
  return [...text.matchAll(/#[a-zA-Z0-9_-]+/g)].map((match) =>
    normalizeTag(match[0]),
  );
}

function isBottomTagElement(element) {
  if (element.closest("pre, code")) {
    return false;
  }

  const text = element.textContent.trim();
  return /^#[a-zA-Z0-9_-]+(?:\s+#[a-zA-Z0-9_-]+)*$/.test(text);
}

function createTagSearchHref(tag) {
  const query = new URLSearchParams({ term: `#${tag}` });
  return `${getBasePath()}/search?${query.toString()}`;
}

function createBottomTagChip(tag) {
  const chip = document.createElement("a");
  chip.className = bottomTagChipClass;
  chip.href = createTagSearchHref(tag);
  chip.setAttribute("title", `Search #${tag}`);
  chip.addEventListener("click", () => recordTagUse(tag));
  chip.append(createIcon(mdiTag), document.createTextNode(tag));
  return chip;
}

function findBottomTagElements(contentRoot) {
  const tagElements = [];
  const children = [...contentRoot.children];

  for (let index = children.length - 1; index >= 0; index -= 1) {
    const element = children[index];
    if (!element.textContent.trim()) {
      continue;
    }

    if (!isBottomTagElement(element)) {
      break;
    }

    tagElements.unshift(element);
  }

  return tagElements;
}

export function enhanceBottomTags(rootElement) {
  if (!rootElement) {
    return;
  }

  const outerContentRoot = rootElement.querySelector(
    ".toastui-editor-contents",
  );
  const contentRoot = outerContentRoot
    ? getPrimaryContentContainer(outerContentRoot)
    : null;
  if (!contentRoot || contentRoot.querySelector(`.${bottomTagsClass}`)) {
    return;
  }

  const tagElements = findBottomTagElements(contentRoot);
  const tags = [
    ...new Set(
      tagElements.flatMap((element) => getTagsFromText(element.textContent)),
    ),
  ].filter((tag) => !isSystemTag(tag));

  if (tags.length === 0) {
    return;
  }

  const wrapper = document.createElement("div");
  wrapper.className = bottomTagsClass;
  wrapper.setAttribute("aria-label", "Note tags");

  const chipRow = document.createElement("div");
  chipRow.className = "flatnotes-bottom-tags-row";
  tags.forEach((tag) => chipRow.append(createBottomTagChip(tag)));
  wrapper.append(chipRow);

  const previousElement = tagElements[0].previousElementSibling;
  tagElements[0].replaceWith(wrapper);
  if (previousElement?.tagName?.toLowerCase() === "hr") {
    previousElement.remove();
  }
  tagElements.slice(1).forEach((element) => element.remove());
}

export function enhanceSectionDividers(rootElement) {
  const horizontalRules = Array.from(rootElement.querySelectorAll("hr"));
  horizontalRules.forEach((rule) => {
    if (!rule.isConnected || rule.nextElementSibling?.tagName !== "HR") {
      return;
    }

    rule.classList.add(sectionDividerClass);
    while (rule.nextElementSibling?.tagName === "HR") {
      rule.nextElementSibling.remove();
    }
  });
}

function getCodeText(preElement) {
  const codeElement = preElement.querySelector("code");
  return codeElement ? codeElement.textContent : preElement.textContent;
}

function decorateCodeBlock(preElement) {
  if (preElement.closest(`.${codeBlockWrapperClass}`)) {
    return;
  }

  const wrapper = document.createElement("div");
  wrapper.className = codeBlockWrapperClass;
  preElement.parentNode.insertBefore(wrapper, preElement);
  wrapper.append(preElement);

  const button = document.createElement("button");
  button.type = "button";
  button.className = codeCopyButtonClass;
  setButtonState(button);

  button.addEventListener("click", async () => {
    button.disabled = true;
    try {
      await writePlainTextToClipboard(getCodeText(preElement));
      setButtonState(button, "copied");
    } catch {
      setButtonState(button, "failed");
    } finally {
      window.setTimeout(() => {
        setButtonState(button);
        button.disabled = false;
      }, resetDelayMs);
    }
  });

  wrapper.append(button);
}

export function enhanceCodeBlocks(rootElement) {
  if (!rootElement) {
    return;
  }

  rootElement
    .querySelectorAll(".toastui-editor-contents pre")
    .forEach((preElement) => {
      if (getCodeLanguage(preElement) !== mermaidLanguage) {
        decorateCodeBlock(preElement);
      }
    });
}

function setTaskCheckboxesBusy(rootElement, isBusy, taskListOptions) {
  rootElement.querySelectorAll(`.${taskCheckboxClass}`).forEach((checkbox) => {
    checkbox.disabled = isBusy || !!taskListOptions.disabled;
    checkbox.classList.toggle(taskCheckboxSavingClass, isBusy);
  });
}

function decorateTaskCheckbox(checkbox, index, rootElement, taskListOptions) {
  checkbox.classList.add(taskCheckboxClass);
  checkbox.dataset.flatnotesTaskIndex = String(index);
  checkbox.disabled = !!taskListOptions.disabled || !taskListOptions.onToggle;
  checkbox.setAttribute(
    "title",
    checkbox.disabled ? "Open edit mode to change this item" : "Toggle item",
  );

  if (checkbox.flatnotesTaskChangeHandler) {
    checkbox.removeEventListener("change", checkbox.flatnotesTaskChangeHandler);
  }

  checkbox.flatnotesTaskChangeHandler = async () => {
    if (checkbox.disabled || !taskListOptions.onToggle) {
      return;
    }

    const checked = checkbox.checked;
    const previousChecked = !checked;
    setTaskCheckboxesBusy(rootElement, true, taskListOptions);

    try {
      await taskListOptions.onToggle({
        checked,
        index,
      });
    } catch {
      checkbox.checked = previousChecked;
    } finally {
      setTaskCheckboxesBusy(rootElement, false, taskListOptions);
    }
  };

  checkbox.addEventListener("change", checkbox.flatnotesTaskChangeHandler);
}

function ensureTaskCheckbox(taskItem) {
  const existingCheckbox = taskItem.querySelector(
    `:scope > input[type='checkbox'].${taskCheckboxClass}`,
  );
  if (existingCheckbox) {
    return existingCheckbox;
  }

  const checkbox = document.createElement("input");
  checkbox.type = "checkbox";
  checkbox.checked =
    taskItem.hasAttribute("data-task-checked") ||
    taskItem.classList.contains("checked");

  taskItem.insertBefore(checkbox, taskItem.firstChild);
  return checkbox;
}

export function enhanceTaskListCheckboxes(rootElement, taskListOptions = {}) {
  if (!rootElement) {
    return;
  }

  const taskItems = rootElement.querySelectorAll(
    ".toastui-editor-contents li.task-list-item",
  );

  taskItems.forEach((taskItem, index) => {
    const checkbox = ensureTaskCheckbox(taskItem);
    decorateTaskCheckbox(checkbox, index, rootElement, taskListOptions);
  });
}

function isEscaped(text, index) {
  let slashCount = 0;
  for (
    let cursor = index - 1;
    cursor >= 0 && text[cursor] === "\\";
    cursor -= 1
  ) {
    slashCount += 1;
  }

  return slashCount % 2 === 1;
}

function findClosingDollar(text, openingIndex) {
  for (
    let cursor = openingIndex + 1;
    cursor < text.length && cursor - openingIndex <= maxInlineLatexLength;
    cursor += 1
  ) {
    if (text[cursor] === "\n" || text[cursor] === "\r") {
      return -1;
    }

    if (text[cursor] === "$" && !isEscaped(text, cursor)) {
      return cursor;
    }
  }

  return -1;
}

function parseInlineLatexSegments(text) {
  const segments = [];
  let cursor = 0;

  while (cursor < text.length) {
    const openingIndex = text.indexOf("$", cursor);
    if (openingIndex === -1) {
      break;
    }

    const nextCharacter = text[openingIndex + 1];
    if (
      isEscaped(text, openingIndex) ||
      nextCharacter === "$" ||
      nextCharacter === undefined ||
      /\s/.test(nextCharacter)
    ) {
      cursor = openingIndex + 1;
      continue;
    }

    const closingIndex = findClosingDollar(text, openingIndex);
    if (closingIndex === -1) {
      break;
    }

    const latexSource = text.slice(openingIndex + 1, closingIndex);
    const previousCharacter = text[closingIndex - 1];
    if (!latexSource || /\s/.test(previousCharacter)) {
      cursor = openingIndex + 1;
      continue;
    }

    segments.push({
      end: closingIndex + 1,
      latexSource,
      start: openingIndex,
    });
    cursor = closingIndex + 1;
  }

  return segments;
}

function shouldSkipLatexTextNode(textNode) {
  const parentElement = textNode.parentElement;
  return !parentElement || parentElement.closest(ignoredLatexSelector);
}

async function getKatexInstance() {
  if (!katexInstance) {
    const katexModule = await import("katex");
    katexInstance = katexModule.default;
  }
  return katexInstance;
}

function renderInlineLatex(latexSource, katex) {
  const wrapper = document.createElement("span");
  wrapper.className = inlineLatexClass;
  wrapper.setAttribute("data-latex-source", latexSource);

  try {
    wrapper.innerHTML = katex.renderToString(latexSource, latexRenderOptions);
  } catch {
    return null;
  }

  return wrapper;
}

function replaceTextNodeWithInlineLatex(textNode, katex) {
  const text = textNode.textContent;
  const segments = parseInlineLatexSegments(text);
  if (segments.length === 0) {
    return;
  }

  const fragment = document.createDocumentFragment();
  let cursor = 0;

  segments.forEach(({ end, latexSource, start }) => {
    if (start > cursor) {
      fragment.append(document.createTextNode(text.slice(cursor, start)));
    }

    const renderedLatex = renderInlineLatex(latexSource, katex);
    fragment.append(
      renderedLatex || document.createTextNode(text.slice(start, end)),
    );
    cursor = end;
  });

  if (cursor < text.length) {
    fragment.append(document.createTextNode(text.slice(cursor)));
  }

  textNode.parentNode.replaceChild(fragment, textNode);
}

export async function enhanceInlineLatex(rootElement) {
  if (!rootElement) {
    return;
  }

  const contentRoot = rootElement.querySelector(".toastui-editor-contents");
  if (!contentRoot) {
    return;
  }

  const textNodes = [];
  const walker = document.createTreeWalker(contentRoot, NodeFilter.SHOW_TEXT, {
    acceptNode(textNode) {
      if (
        shouldSkipLatexTextNode(textNode) ||
        !textNode.textContent.includes("$") ||
        parseInlineLatexSegments(textNode.textContent).length === 0
      ) {
        return NodeFilter.FILTER_REJECT;
      }

      return NodeFilter.FILTER_ACCEPT;
    },
  });

  while (walker.nextNode()) {
    textNodes.push(walker.currentNode);
  }

  if (textNodes.length === 0) {
    return;
  }

  const katex = await getKatexInstance();
  textNodes.forEach((textNode) =>
    replaceTextNodeWithInlineLatex(textNode, katex),
  );
}

function shouldSkipArrowTextNode(textNode) {
  const parentElement = textNode.parentElement;
  return !parentElement || !!parentElement.closest(ignoredArrowSelector);
}

function replaceTextNodeWithInlineArrows(textNode) {
  const text = textNode.textContent;
  if (!text.includes("->")) {
    return;
  }

  const fragment = document.createDocumentFragment();
  const segments = text.split("->");

  segments.forEach((segment, index) => {
    if (segment) {
      fragment.append(document.createTextNode(segment));
    }

    if (index < segments.length - 1) {
      const arrow = document.createElement("span");
      arrow.className = inlineArrowClass;
      arrow.textContent = "\u2192";
      fragment.append(arrow);
    }
  });

  textNode.parentNode.replaceChild(fragment, textNode);
}

export function enhanceInlineArrows(rootElement) {
  if (!rootElement) {
    return;
  }

  const contentRoot = rootElement.querySelector(
    ".toastui-editor-contents:not(.flatnotes-html-contents)",
  );
  if (!contentRoot) {
    return;
  }

  const textNodes = [];
  const walker = document.createTreeWalker(contentRoot, NodeFilter.SHOW_TEXT, {
    acceptNode(textNode) {
      if (
        shouldSkipArrowTextNode(textNode) ||
        !textNode.textContent.includes("->")
      ) {
        return NodeFilter.FILTER_REJECT;
      }

      return NodeFilter.FILTER_ACCEPT;
    },
  });

  while (walker.nextNode()) {
    textNodes.push(walker.currentNode);
  }

  textNodes.forEach(replaceTextNodeWithInlineArrows);
}

function getThemeColor(name, fallback) {
  const value = getComputedStyle(document.body).getPropertyValue(name).trim();

  return value ? `rgb(${value})` : fallback;
}

function getMermaidThemeVariables() {
  const background = getThemeColor("--theme-background", "#ffffff");
  const elevated = getThemeColor("--theme-background-elevated", "#f3f4f5");
  const text = getThemeColor("--theme-text", "#2c3139");
  const muted = getThemeColor("--theme-text-muted", "#8891a1");
  const border = getThemeColor("--theme-border", "#eceef0");
  const brand = getThemeColor("--theme-brand", "#f8a66b");

  return {
    background,
    clusterBkg: background,
    clusterBorder: border,
    fontFamily: "Poppins, sans-serif",
    lineColor: muted,
    mainBkg: elevated,
    noteBkg: elevated,
    noteTextColor: text,
    primaryBorderColor: border,
    primaryColor: elevated,
    primaryTextColor: text,
    secondaryColor: background,
    tertiaryColor: brand,
    textColor: text,
  };
}

async function getMermaidInstance() {
  if (!mermaidInstance) {
    const mermaidModule = await import("mermaid");
    mermaidInstance = mermaidModule.default;
  }

  mermaidInstance.initialize({
    flowchart: {
      htmlLabels: false,
      useMaxWidth: true,
    },
    securityLevel: "strict",
    sequence: {
      useMaxWidth: true,
    },
    startOnLoad: false,
    suppressErrorRendering: true,
    theme: "base",
    themeVariables: getMermaidThemeVariables(),
  });

  return mermaidInstance;
}

function getCodeLanguage(preElement) {
  const codeElement = preElement.querySelector("code");
  const directLanguage = codeElement?.dataset.language;

  if (directLanguage) {
    return directLanguage.trim().toLowerCase();
  }

  const classNames = [
    ...preElement.classList,
    ...(codeElement ? [...codeElement.classList] : []),
  ];
  const languageClass = classNames.find((className) =>
    /^(lang|language)-/i.test(className),
  );

  return languageClass
    ? languageClass
        .replace(/^(lang|language)-/i, "")
        .trim()
        .toLowerCase()
    : "";
}

function isMermaidCodeBlock(preElement) {
  return (
    !preElement.closest(`.${mermaidWrapperClass}`) &&
    getCodeLanguage(preElement) === mermaidLanguage
  );
}

function getMermaidSource(preElement) {
  const codeElement = preElement.querySelector("code");
  return (
    codeElement ? codeElement.textContent : preElement.textContent
  ).trim();
}

async function renderMermaidBlock(preElement, mermaid) {
  const mermaidSource = getMermaidSource(preElement);
  if (!mermaidSource) {
    return;
  }

  const diagramId = `flatnotes-mermaid-${Date.now()}-${mermaidRenderCounter}`;
  mermaidRenderCounter += 1;

  let renderedDiagram;
  try {
    renderedDiagram = await mermaid.render(diagramId, mermaidSource);
  } catch {
    return;
  }

  const svg =
    typeof renderedDiagram === "string" ? renderedDiagram : renderedDiagram.svg;
  if (!svg) {
    return;
  }

  const wrapper = document.createElement("div");
  wrapper.className = mermaidWrapperClass;

  const diagram = document.createElement("div");
  diagram.className = mermaidDiagramClass;
  diagram.setAttribute("data-mermaid-source", mermaidSource);
  diagram.innerHTML = svg;

  wrapper.append(diagram);
  preElement.replaceWith(wrapper);
  renderedDiagram.bindFunctions?.(diagram);
}

export async function enhanceMermaidDiagrams(rootElement) {
  if (!rootElement) {
    return;
  }

  const contentRoot = rootElement.querySelector(".toastui-editor-contents");
  if (!contentRoot) {
    return;
  }

  const mermaidBlocks = [...contentRoot.querySelectorAll("pre")].filter(
    isMermaidCodeBlock,
  );
  if (mermaidBlocks.length === 0) {
    return;
  }

  let mermaid;
  try {
    mermaid = await getMermaidInstance();
  } catch {
    return;
  }

  for (const preElement of mermaidBlocks) {
    await renderMermaidBlock(preElement, mermaid);
  }
}

export async function enhanceRenderedMarkdown(rootElement, options = {}) {
  enhanceInlineArrows(rootElement);
  enhanceCodeBlocks(rootElement);
  enhanceMediaImages(rootElement);
  if (options.noteLead !== false) {
    enhanceNoteLead(rootElement, options);
  }
  enhanceSectionDividers(rootElement);
  enhanceBottomTags(rootElement);
  enhanceTaskListCheckboxes(rootElement, options.taskList);
  await Promise.all([
    enhanceInlineLatex(rootElement),
    enhanceMermaidDiagrams(rootElement),
  ]);
  enhanceMediaImages(rootElement);
}
