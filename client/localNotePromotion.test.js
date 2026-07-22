import assert from "node:assert/strict";
import test from "node:test";

import {
  buildLocalLibraryNote,
  localFileNoteTitle,
} from "./localNotePromotion.js";

test("local filenames become clean note titles", () => {
  assert.equal(localFileNoteTitle("STATUS-LOG.md"), "STATUS-LOG");
  assert.equal(localFileNoteTitle("bad:name?.txt"), "bad name");
});

test("markdown snapshots stay HTML notes with a work category", () => {
  const note = buildLocalLibraryNote({
    name: "project.md",
    extension: "md",
    draftContent: "# Project\n\nCurrent state.\n",
  });
  assert.equal(note.format, "html");
  assert.match(note.content, /lamanotes-note-kind" content="work"/);
  assert.match(note.content, /lamanotes-tags" content="work"/);
  assert.match(note.content, /#work/);
  assert.doesNotMatch(note.content, /Work Note/);
});

test("plain text snapshots use a collision-safe code fence", () => {
  const note = buildLocalLibraryNote({
    name: "sample.txt",
    extension: "txt",
    draftContent: "alpha\n```\nomega",
  });
  assert.match(note.content, /<pre><code class="language-txt">/);
  assert.match(note.content, /alpha/);
  assert.match(note.content, /```/);
});

test("structured config snapshots keep a useful language and clean title", () => {
  const note = buildLocalLibraryNote({
    name: "service-config.yml",
    extension: "yml",
    draftContent: "enabled: true\n",
  });

  assert.equal(localFileNoteTitle("service-config.yml"), "service-config");
  assert.match(note.content, /<pre><code class="language-yaml">/);
  assert.match(note.content, /enabled: true/);
});

test("CSV and TeX snapshots retain raw source and language", () => {
  const csv = buildLocalLibraryNote({
    name: "measurements.csv",
    extension: "csv",
    draftContent: 'name,value\n"alpha,beta",3.5\n',
  });
  const tex = buildLocalLibraryNote({
    name: "formula.tex",
    extension: "tex",
    draftContent: "\\\\section{Result}\n",
  });

  assert.match(csv.content, /<pre><code class="language-csv">/);
  assert.match(csv.content, /&quot;alpha,beta&quot;,3.5/);
  assert.match(tex.content, /<pre><code class="language-tex">/);
  assert.match(tex.content, /\\\\section\{Result\}/);
});
