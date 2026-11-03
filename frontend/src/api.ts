export type Row = { id: number; [key: string]: any };
export const csrf = () =>
  document.cookie
    .split("; ")
    .find((v) => v.startsWith("csrftoken="))
    ?.split("=")[1] ?? "";
export async function api(path: string, options: RequestInit = {}) {
  let response: Response;
  try {
    response = await fetch(path, {
      credentials: "same-origin",
      ...options,
      headers: { "X-CSRFToken": csrf(), ...options.headers },
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError")
      throw error;
    throw new Error(
      "Não foi possível conectar ao servidor. Verifique se o EngFinance está iniciado e tente Atualizar.",
    );
  }
  const body = await response
    .json()
    .catch(() => ({ detail: "O servidor retornou uma resposta inesperada." }));
  if (!response.ok) {
    const detail = body.detail ?? body;
    throw new Error(
      typeof detail === "string" ? detail : JSON.stringify(detail),
    );
  }
  return body;
}
export const post = (path: string, body: unknown) =>
  api(path, {
    method: "POST",
    body: JSON.stringify(body),
    headers: { "Content-Type": "application/json" },
  });
export async function all(resource: string): Promise<Row[]> {
  let path: string | null = `/api/v1/${resource}/`;
  const rows: Row[] = [];
  while (path) {
    const data = await api(path);
    rows.push(...data.results);
    const next = data.next ? new URL(data.next, window.location.origin) : null;
    path = next ? next.pathname + next.search : null;
  }
  return rows;
}
export const money = (value: unknown) =>
  new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
    maximumFractionDigits: 2,
  }).format(Number(value ?? 0));
export const number = (value: unknown) =>
  new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 }).format(
    Number(value ?? 0),
  );
export const dateLabel = (value: string) =>
  value
    ? new Date(
        value.length === 10 ? value + "T12:00:00" : value,
      ).toLocaleDateString("pt-BR")
    : "—";
export const stateLabel: Record<string, string> = {
  DRAFT: "Rascunho",
  SUBMITTED: "Em aprovação",
  APPROVED: "Aprovado",
  REJECTED: "Rejeitado",
  OPEN: "Aberto",
  PROGRESS: "Em andamento",
  DONE: "Concluído",
};
export const kindLabel: Record<string, string> = {
  COMMITMENT: "Compromisso",
  MEASUREMENT: "Medição",
  INVOICE: "Nota fiscal",
  PAYMENT: "Pagamento",
};
