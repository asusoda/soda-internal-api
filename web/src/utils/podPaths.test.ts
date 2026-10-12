import { expect, test } from "vitest";
import { crumbs, formatSize, joinPath, parentPath } from "./podPaths";

test("joins and climbs paths", () => {
  expect(joinPath("/", "workspace")).toBe("/workspace");
  expect(joinPath("/workspace", "a.py")).toBe("/workspace/a.py");
  expect(parentPath("/workspace/data")).toBe("/workspace");
  expect(parentPath("/workspace")).toBe("/");
  expect(parentPath("/")).toBe("/");
});

test("builds breadcrumbs and sizes", () => {
  expect(crumbs("/workspace/data").map((c) => c.path)).toEqual(["/", "/workspace", "/workspace/data"]);
  expect(formatSize(512)).toBe("512 B");
  expect(formatSize(1536)).toBe("1.5 KB");
  expect(formatSize(3 * 1024 * 1024)).toBe("3.0 MB");
});
