import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const dialogPath = path.join(import.meta.dirname, "AccessibleDialog.tsx");

test("AccessibleDialog isolates focus setup from onClose callback churn", () => {
  const source = readFileSync(dialogPath, "utf8");

  assert.match(source, /const onCloseRef = useRef\(onClose\);/);
  assert.match(source, /onCloseRef\.current = onClose;/);
  assert.match(source, /onCloseRef\.current\(\);/);
  assert.match(source, /\}, \[isOpen\]\);/);
  assert.doesNotMatch(source, /\}, \[isOpen,\s*onClose\]\);/);
});
