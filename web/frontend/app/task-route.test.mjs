import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const routePath = path.join(
  import.meta.dirname,
  "(workbench)",
  "tasks",
  "[taskId]",
  "page.tsx"
);
const source = readFileSync(routePath, "utf8");

test("task route keeps progress callbacks stable", () => {
  assert.match(source, /import \{ useCallback \} from "react"/);
  assert.match(source, /const handleTaskComplete = useCallback/);
  assert.match(source, /const handleViewReport = useCallback/);
  assert.match(source, /onTaskComplete=\{handleTaskComplete\}/);
  assert.match(source, /onViewReport=\{handleViewReport\}/);
});
