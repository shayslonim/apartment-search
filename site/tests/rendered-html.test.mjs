import assert from "node:assert/strict";
import { access, readFile } from "node:fs/promises";
import test from "node:test";

const root = new URL("../", import.meta.url);

test("build contains the Apartment Search worker", async () => {
  await access(new URL("dist/server/index.js", root));
  const page = await readFile(new URL("app/page.tsx", root), "utf8");
  const layout = await readFile(new URL("app/layout.tsx", root), "utf8");
  const hosting = JSON.parse(
    await readFile(new URL(".openai/hosting.json", root), "utf8"),
  );

  assert.match(page, /Match inbox/);
  assert.match(page, /listApartments/);
  assert.match(page, /listing-title-link/);
  assert.doesNotMatch(page, /SkeletonPreview|codex-preview/);
  assert.match(layout, /title: "Apartment Search"/);
  assert.equal(hosting.d1, "DB");
});
