import { renderHook, waitFor } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import apiClient from "../components/utils/axios";
import useOrgModules from "./useOrgModules";

vi.mock("../components/utils/axios", () => ({ default: { get: vi.fn() } }));
vi.mock("../components/auth/AuthContext", () => ({
  useAuth: () => ({ currentOrg: { id: 7, prefix: "ais" } }),
}));

const get = vi.mocked(apiClient.get);

test("hides only the modules the org switched off", async () => {
  get.mockResolvedValue({
    data: {
      modules: [
        { name: "points", enabled: false },
        { name: "storefront", enabled: true },
      ],
    },
  });
  const { result } = renderHook(() => useOrgModules());
  await waitFor(() => expect(result.current.isEnabled("points")).toBe(false));
  expect(get).toHaveBeenCalledWith("/api/organizations/7/modules");
  expect(result.current.isEnabled("storefront")).toBe(true);
  expect(result.current.isEnabled("calendar")).toBe(true);
  expect(result.current.isEnabled(undefined)).toBe(true);
});

test("shows every module when the request fails", async () => {
  get.mockRejectedValue(new Error("down"));
  const { result } = renderHook(() => useOrgModules());
  await waitFor(() => expect(get).toHaveBeenCalled());
  expect(result.current.isEnabled("points")).toBe(true);
});
