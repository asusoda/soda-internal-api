import { expect, test } from "vitest";
import { changedMemberFields } from "./pointsTypes";

const loaded = { name: "Alice", asu_id: "1234", academic_standing: "Junior", major: "CS" };

test("sends only the fields that changed", () => {
  expect(changedMemberFields(loaded, { ...loaded, name: "Alice B" })).toEqual({ name: "Alice B" });
  expect(changedMemberFields(loaded, loaded)).toEqual({});
});

test("sends a cleared field as an empty string, and a cleared ASU ID as null", () => {
  expect(changedMemberFields(loaded, { ...loaded, major: "", asu_id: " " })).toEqual({ major: "", asu_id: null });
});
