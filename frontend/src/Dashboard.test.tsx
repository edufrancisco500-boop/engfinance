// @vitest-environment jsdom
import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { api } from "./api";
import { useDashboard } from "./Dashboard";

vi.mock("./api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./api")>()),
  api: vi.fn(),
}));

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

test("a mudança de filtro consulta o recorte novo e substitui os valores", async () => {
  const request = vi.mocked(api);
  request
    .mockResolvedValueOnce({ committed: "100.00" })
    .mockResolvedValueOnce({ committed: "200.00" });
  const { result, rerender } = renderHook(
    ({ portfolio }) => useDashboard({ year: "2026", portfolio }, 0),
    { initialProps: { portfolio: "1" } },
  );
  await waitFor(() => expect(result.current.data?.committed).toBe("100.00"));
  rerender({ portfolio: "2" });
  await waitFor(() => expect(result.current.data?.committed).toBe("200.00"));
  expect(request.mock.calls[1][0]).toContain("portfolio=2");
});

test("uma falha de consulta não mantém os valores do filtro anterior", async () => {
  const request = vi.mocked(api);
  request
    .mockResolvedValueOnce({ committed: "100.00" })
    .mockRejectedValueOnce(new Error("Servidor indisponível"));
  const { result, rerender } = renderHook(
    ({ month }) => useDashboard({ year: "2026", month }, 0),
    { initialProps: { month: "1" } },
  );
  await waitFor(() => expect(result.current.data?.committed).toBe("100.00"));
  rerender({ month: "2" });
  expect(result.current.data).toBeNull();
  await waitFor(() =>
    expect(result.current.error).toBe("Servidor indisponível"),
  );
  expect(result.current.data).toBeNull();
});

test("uma resposta antiga atrasada não sobrescreve o filtro mais recente", async () => {
  let resolveOld!: (value: unknown) => void;
  const oldResponse = new Promise((resolve) => {
    resolveOld = resolve;
  });
  vi.mocked(api)
    .mockReturnValueOnce(oldResponse)
    .mockResolvedValueOnce({ committed: "200.00" });
  const { result, rerender } = renderHook(
    ({ month }) => useDashboard({ year: "2026", month }, 0),
    { initialProps: { month: "1" } },
  );
  rerender({ month: "2" });
  await waitFor(() => expect(result.current.data?.committed).toBe("200.00"));
  await act(async () => {
    resolveOld({ committed: "999.00" });
    await oldResponse;
  });
  expect(result.current.data.committed).toBe("200.00");
});
