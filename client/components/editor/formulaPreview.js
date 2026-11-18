import { syntaxTree } from "@codemirror/language";
import { showTooltip } from "@codemirror/view";
import {
  getKatexInstance,
  latexRenderOptions,
  parseInlineLatexSegments,
} from "./inlineLatex.js";

export function formulaAtCursor(state) {
  const { head, empty } = state.selection.main;
  if (!empty) return null;
  const line = state.doc.lineAt(head);
  if (!line.text.includes("$")) return null;
  let from = line.from;
  let to = line.to;
  syntaxTree(state).iterate({
    from,
    to,
    enter(node) {
      if (
        !["FencedCode", "CodeBlock", "InlineCode", "HTMLBlock", "URL"].includes(
          node.name,
        )
      )
        return;
      if (node.to <= head) from = Math.max(from, node.to);
      else if (node.from >= head) to = Math.min(to, node.from);
      else from = to;
      return false;
    },
  });
  if (from >= to) return null;
  const text = line.text.slice(from - line.from, to - line.from);
  const segment = parseInlineLatexSegments(text).find(
    ({ start, end }) =>
      from + start < head &&
      head < from + end &&
      text[start - 1] !== "$" &&
      text[end] !== "$",
  );
  return segment
    ? { pos: from + segment.start, source: segment.latexSource }
    : null;
}

export const formulaPreview = showTooltip.compute(
  ["selection", "doc"],
  (state) => {
    const formula = formulaAtCursor(state);
    if (!formula) return null;
    return {
      pos: formula.pos,
      above: false,
      strictSide: true,
      create(view) {
        const dom = document.createElement("div");
        dom.className = "lamanotes-formula-preview";
        dom.hidden = true;
        let active = true;
        async function render() {
          const [katex] = await Promise.all([
            getKatexInstance(),
            import("katex/dist/katex.min.css"),
          ]);
          if (!active) return;
          try {
            katex.render(formula.source, dom, {
              ...latexRenderOptions,
              macros: { ...latexRenderOptions.macros },
            });
            dom.hidden = false;
            view.requestMeasure();
          } catch {
            dom.hidden = true;
          }
        }
        void render().catch(() => {});
        return {
          dom,
          destroy() {
            active = false;
          },
        };
      },
    };
  },
);
