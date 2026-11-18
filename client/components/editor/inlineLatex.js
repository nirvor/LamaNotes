const maxInlineLatexLength = 500;
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

export function parseInlineLatexSegments(text) {
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

export const latexRenderOptions = {
  displayMode: false,
  macros: latexMacros,
  strict: "ignore",
  throwOnError: true,
  trust: false,
};

let katexInstance;
export async function getKatexInstance() {
  if (!katexInstance) {
    const katexModule = await import("katex");
    katexInstance = katexModule.default;
  }
  return katexInstance;
}
