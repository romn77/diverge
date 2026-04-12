import assert from "node:assert/strict";
import test from "node:test";

import { getLocalDateInputValue } from "./localDate.js";

test("getLocalDateInputValue uses local date parts instead of UTC ISO slicing", () => {
  const fakeLocalDate = {
    getFullYear: () => 2026,
    getMonth: () => 3,
    getDate: () => 8,
    toISOString: () => "2026-04-09T03:30:00.000Z",
  };

  assert.equal(getLocalDateInputValue(fakeLocalDate), "2026-04-08");
});
