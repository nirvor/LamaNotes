# Thomas VPS flatnotes rendering deployment plan

Date: 2026-05-24

Fork: https://github.com/nirvor/flatnotes

Upstream: https://github.com/dullage/flatnotes

Local checkout: `C:\Users\thoma\Desktop\work\flatnotes-custom`

Target VPS path: `/srv/flatnotes`

Current VPS image: `dullage/flatnotes:latest`

Current persistent data path: `/srv/flatnotes/data`

## Current architecture notes

flatnotes is a Vue client plus Python/FastAPI server packaged in one Docker image. The notes remain normal Markdown files in `/data`, which is mounted from `/srv/flatnotes/data` on the VPS. The requested features are view-layer features and should stay in the client unless later requirements say otherwise.

Relevant client files:

- `client/views/Note.vue` switches between view mode and edit mode.
- `client/components/toastui/ToastViewer.vue` creates the TOAST UI viewer used in view mode.
- `client/components/toastui/ToastEditor.vue` creates the editor used in edit mode.
- `client/components/toastui/baseOptions.js` registers TOAST UI shared options, code highlighting, and custom renderers.
- `client/components/toastui/toastui-editor-overrides.scss` controls viewer/editor styling.

Baseline check completed:

- `npm ci` works on the fork checkout.
- `npm run build` works on the upstream baseline.
- `npm audit --omit=dev` currently reports upstream dependency warnings, mainly `axios`, `dompurify` via `@toast-ui/editor`, `follow-redirects`, and `postcss`. This is not caused by our planned features, but should be handled before exposing broader public access.

## Deployment lane

Use a custom image, not direct edits inside the running container.

Minimal first deployment lane:

1. Commit feature branch in the fork.
2. Build the Docker image from the fork on the VPS or locally.
3. Tag it explicitly, for example `flatnotes-thomas:copy-v1`, `flatnotes-thomas:mermaid-v1`, `flatnotes-thomas:katex-v1`.
4. Back up `/srv/flatnotes/data` and `/srv/flatnotes/docker-compose.yml`.
5. Change only the `flatnotes` service image in `/srv/flatnotes/docker-compose.yml`.
6. Run `docker compose up -d flatnotes`.
7. Verify `/health`, login, existing notes, code blocks, Mermaid, and inline math.

Rollback is simple:

1. Restore the old image line, currently `dullage/flatnotes:latest`.
2. Run `docker compose up -d flatnotes`.
3. Keep `/srv/flatnotes/data` untouched.

Later, if this becomes a maintained fork, switch from local tags to GitHub Container Registry, for example `ghcr.io/nirvor/flatnotes:thomas-v1`.

## Step 1: Copy button for code blocks

Goal: In view mode, every normal fenced code block gets a small copy icon in the top-right corner. It copies the code block text, not the whole note.

Implementation shape:

- Add a small client helper under `client/components/toastui/renderEnhancements.js`.
- In `ToastViewer.vue`, after `new Viewer(...)`, call a helper such as `enhanceCodeBlocks(viewerElement.value)`.
- Target rendered code blocks with `.toastui-editor-contents pre`.
- Wrap or decorate each `pre` with a positioned container and inject a button.
- Use `navigator.clipboard.writeText(codeText)` first.
- Keep a fallback for older browser contexts if clipboard permissions fail.
- Add CSS in `toastui-editor-overrides.scss` for dark and light themes.
- Use an icon-like button with `aria-label="Copy code"` and `title="Copy code"`.

Acceptance test:

- A code block in `FINN Firmenuebersicht` has a visible copy control.
- Clicking it copies exactly the visible source, including line breaks.
- Mermaid blocks are either skipped in later Step 2 or get a separate "copy source" behavior.
- No copy button appears on inline code.

Deployment:

- Build image `flatnotes-thomas:copy-v1`.
- Deploy to VPS.
- Verify with the current FINN test note.
- Roll back by restoring `dullage/flatnotes:latest` if the viewer breaks.

Risk:

- Low. This is a DOM enhancement after rendering. It does not change stored Markdown or the API.

## Step 2: Mermaid rendering

Goal: Fenced blocks like this should render as diagrams in view mode:

````text
```mermaid
flowchart LR
  A --> B
````

```

Implementation shape:

- Add `mermaid` as a dependency.
- Prefer post-processing rendered code blocks in the viewer instead of replacing the Markdown parser first. This keeps the stored Markdown standard and avoids fighting TOAST UI internals.
- In the same enhancement helper, find `pre code.language-mermaid` or equivalent rendered language markers.
- Extract text content from the code block.
- Replace the block with a diagram container, e.g. `.flatnotes-mermaid`.
- Initialize Mermaid manually with `startOnLoad: false`.
- Use `securityLevel: "strict"` as the first default. Do not enable loose HTML labels unless there is a specific reason.
- Render each block with a deterministic id.
- If Mermaid fails, show the original source block plus a short visible error. Do not leave a blank hole.
- Keep a small "copy source" button for Mermaid source if useful.

Acceptance test:

- The existing FINN flowchart renders as an SVG diagram.
- Bad Mermaid source displays a readable fallback.
- Normal code blocks still display and copy.
- The app still works in dark mode.
- The generated SVG does not require external services.

Deployment:

- Build image `flatnotes-thomas:mermaid-v1`.
- Deploy after Step 1 is stable.
- Verify with a flatnotes test note containing `flowchart`, `sequenceDiagram`, and one intentionally broken Mermaid block.

Risk:

- Medium. Mermaid is large and touches generated SVG. Keep strict security and consider dynamic import so the main note viewer chunk does not grow too much.

## Step 3: Inline LaTeX rendering

Goal: In view mode, inline expressions like `$E = mc^2$` render as math, while code blocks and inline code stay untouched.

Implementation shape:

- Add `katex` as a dependency.
- Import KaTeX CSS once in the viewer path.
- Use KaTeX auto-render on the viewer root after Mermaid handling.
- Configure delimiters in this order:
  - `$$...$$` display math
  - `$...$` inline math
  - `\(...\)` inline math
  - `\[...\]` display math
- Use `throwOnError: false`.
- Keep `ignoredTags` including `pre` and `code`.
- Add `ignoredClasses` for Mermaid containers and any code-copy UI.
- If needed later, support display equations more deliberately, but the first requested target is inline `$...$`.

Acceptance test:

- `$E = mc^2$` renders inline.
- Code like `` `$not_math$` `` remains code.
- Fenced code blocks containing `$...$` are not modified.
- Broken math renders safely instead of crashing the viewer.
- Mermaid diagrams are not corrupted by the math renderer.

Deployment:

- Build image `flatnotes-thomas:katex-v1`.
- Deploy after Step 2 is stable.
- Verify with one test note containing inline math, display math, code with dollar signs, and a Mermaid diagram.

Risk:

- Medium. `$...$` can conflict with normal prose about prices. In Thomas' notes this is acceptable only if false positives are rare. If Euro/USD prose becomes annoying, switch to `\(...\)` as default and keep `$...$` optional.

## Final QA checklist before production use

- `npm run build`
- `docker build -t flatnotes-thomas:<tag> .`
- local container smoke test with a temporary data folder
- VPS backup of `/srv/flatnotes/data`
- VPS backup of `/srv/flatnotes/docker-compose.yml`
- deploy one feature tag at a time
- verify existing notes, search, edit/save, image attachments, code copy, Mermaid, and inline math
- keep old image tag available for rollback

## Source notes

- Upstream flatnotes README: https://github.com/dullage/flatnotes
- TOAST UI Editor package is already used by flatnotes for viewer/editor rendering.
- Mermaid should be initialized manually with `startOnLoad: false` for dynamic Vue-rendered content.
- KaTeX auto-render supports custom delimiters, ignored tags, and ignored classes.

```
