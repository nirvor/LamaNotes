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
  assert.match(note.content, /flatnotes-note-kind" content="work"/);
  assert.match(note.content, /flatnotes-tags" content="work"/);
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
