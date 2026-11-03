import { useEffect, useRef, useState, type ReactNode } from "react";
import { all, money, dateLabel, stateLabel, kindLabel, type Row } from "./api";
import { catalog, columnLabels, type Field } from "./catalog";

export type Options = Record<string, Row[]>;
export function labelRow(row: Row, resource: string, options: Options): string {
  if (row.name) return `${row.code ? row.code + " · " : ""}${row.name}`;
  if (resource === "budgets")
    return `#${row.id} · ${options.portfolios?.find((p) => p.id === row.portfolio)?.code ?? row.portfolio} · ${row.year} · ${row.category}`;
  if (resource === "allocations")
    return `#${row.id} · ${options.projects?.find((p) => p.id === row.project)?.name ?? "Sem projeto"} · orçamento #${row.budget}`;
  if (resource === "fundings")
    return `#${row.id} · ${options.contracts?.find((p) => p.id === row.contract)?.code ?? row.contract} · versão ${row.version} · ${stateLabel[row.status]}`;
  return row.reference ?? row.title ?? `#${row.id}`;
}
export function FieldInput({
  field,
  value,
  onChange,
  options,
}: {
  field: Field;
  value: any;
  onChange: (v: string) => void;
  options: Options;
}) {
  return (
    <label>
      {field.label}
      {field.optional && <span className="optional"> opcional</span>}
      {field.source ? (
        <select
          value={value ?? ""}
          onChange={(e) => onChange(e.target.value)}
          required={!field.optional}
        >
          <option value="">Selecione</option>
          {(options[field.source] ?? []).map((row) => (
            <option key={row.id} value={row.id}>
              {labelRow(row, field.source!, options)}
            </option>
          ))}
        </select>
      ) : field.options ? (
        <select
          value={value ?? ""}
          onChange={(e) => onChange(e.target.value)}
          required={!field.optional}
        >
          <option value="">Selecione</option>
          {Object.entries(field.options).map(([key, label]) => (
            <option key={key} value={key}>
              {label}
            </option>
          ))}
        </select>
      ) : field.type === "textarea" ? (
        <textarea
          rows={3}
          value={value ?? ""}
          onChange={(e) => onChange(e.target.value)}
          required={!field.optional}
        />
      ) : (
        <input
          type={field.type === "money" ? "number" : (field.type ?? "text")}
          step={
            field.type === "money" || field.type === "number"
              ? "0.01"
              : undefined
          }
          value={value ?? ""}
          onChange={(e) => onChange(e.target.value)}
          required={!field.optional}
          maxLength={field.type ? undefined : 180}
        />
      )}
    </label>
  );
}
export function Modal({
  title,
  children,
  onClose,
  wide = false,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
  wide?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    ref.current?.showModal();
    return () => ref.current?.close();
  }, []);
  return (
    <dialog ref={ref} className={wide ? "wide" : ""} onCancel={onClose}>
      <div className="modal-head">
        <h2>{title}</h2>
        <button className="icon-button" aria-label="Fechar" onClick={onClose}>
          ✕
        </button>
      </div>
      {children}
    </dialog>
  );
}
export function Pill({ value }: { value: string }) {
  return (
    <span className={`pill ${value.toLowerCase()}`}>
      {stateLabel[value] ?? value}
    </span>
  );
}
export function ErrorBox({ message }: { message: string }) {
  return message ? (
    <div className="error" role="alert">
      {message}
    </div>
  ) : null;
}
export function Loading() {
  return (
    <div className="loading" role="status">
      <span className="spinner" />
      Carregando dados…
    </div>
  );
}
export function Empty({
  text = "Nenhum registro encontrado.",
}: {
  text?: string;
}) {
  return (
    <div className="empty">
      <span>◫</span>
      <p>{text}</p>
    </div>
  );
}
export function DataTable({
  resource,
  rows,
  options,
  onSelect,
  columns,
}: {
  resource: string;
  rows: Row[];
  options: Options;
  onSelect?: (r: Row) => void;
  columns?: string[];
}) {
  const keys = columns ?? catalog[resource]?.columns ?? ["id", "name"];
  function value(row: Row, key: string): ReactNode {
    const v = row[key];
    if (v === null || v === undefined || v === "") return "—";
    if (key === "active") return <Pill value={v ? "Ativo" : "Inativo"} />;
    if (
      key === "status" &&
      catalog[resource]?.fields.find((f) => f.key === "status")?.options
    )
      return (
        <Pill
          value={
            catalog[resource].fields.find((f) => f.key === "status")!.options![
              v
            ] ?? v
          }
        />
      );
    if (key === "status")
      return (
        <>
          <Pill value={v} />
          {row.reversal_of && <span className="pill rejected">Estorno</span>}
          {row.reversed && <span className="pill rejected">Estornado</span>}
        </>
      );
    if (key === "kind") return kindLabel[v] ?? v;
    if (["amount", "balance", "original_value"].includes(key))
      return <span className="numeric">{money(v)}</span>;
    if (key.includes("date")) return dateLabel(v);
    if (key === "physical_progress") return `${v}%`;
    const field = catalog[resource]?.fields.find((f) => f.key === key);
    if (field?.source) {
      const row = options[field.source]?.find((r) => r.id === Number(v));
      return row ? labelRow(row, field.source, options) : `#${v}`;
    }
    return String(v);
  }
  return rows.length ? (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {keys.map((k) => (
              <th key={k}>{columnLabels[k] ?? k}</th>
            ))}
            {onSelect && <th>Detalhes</th>}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              {keys.map((key) => (
                <td key={key}>{value(row, key)}</td>
              ))}
              {onSelect && (
                <td>
                  <button
                    className="table-action"
                    onClick={() => onSelect(row)}
                  >
                    Abrir ↗
                  </button>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  ) : (
    <Empty />
  );
}
export function useRows(resource: string, refresh: number) {
  const [rows, setRows] = useState<Row[]>([]),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(true);
  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    all(resource)
      .then((r) => {
        if (active) setRows(r);
      })
      .catch((e) => {
        if (active) setError(e.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [resource, refresh]);
  return { rows, error, loading };
}
export function Filters({
  value,
  onChange,
  options,
}: {
  value: Record<string, string>;
  onChange: (v: Record<string, string>) => void;
  options: Options;
}) {
  const currentYear = new Date().getFullYear();
  const years = Array.from(
    new Set([
      ...Array.from({ length: 11 }, (_, index) => currentYear - 5 + index),
      ...(options.budgets ?? []).map((row) => Number(row.year)),
      ...(options.documents ?? []).map((row) =>
        Number(String(row.date).slice(0, 4)),
      ),
    ]),
  )
    .filter((year) => Number.isInteger(year) && year >= 1900 && year <= 9999)
    .sort((a, b) => b - a);
  const fields: Field[] = [
    {
      key: "year",
      label: "Ano",
      options: Object.fromEntries(
        years.map((year) => [String(year), String(year)]),
      ),
      optional: true,
    },
    {
      key: "month",
      label: "Mês",
      options: Object.fromEntries(
        [
          "Janeiro",
          "Fevereiro",
          "Março",
          "Abril",
          "Maio",
          "Junho",
          "Julho",
          "Agosto",
          "Setembro",
          "Outubro",
          "Novembro",
          "Dezembro",
        ].map((v, i) => [String(i + 1), v]),
      ),
      optional: true,
    },
    {
      key: "quarter",
      label: "Trimestre",
      options: {
        "1": "1º trimestre",
        "2": "2º trimestre",
        "3": "3º trimestre",
        "4": "4º trimestre",
      },
      optional: true,
    },
    {
      key: "department",
      label: "Gerência",
      source: "departments",
      optional: true,
    },
    {
      key: "portfolio",
      label: "Carteira",
      source: "portfolios",
      optional: true,
    },
    { key: "project", label: "Projeto", source: "projects", optional: true },
    {
      key: "coordination",
      label: "Coordenação",
      source: "coordinations",
      optional: true,
    },
    {
      key: "contract_status",
      label: "Status do contrato",
      options: {
        DRAFT: "Em preparação",
        ACTIVE: "Vigente",
        SUSPENDED: "Suspenso",
        CLOSED: "Encerrado",
        CANCELLED: "Cancelado",
      },
      optional: true,
    },
    { key: "contract", label: "Contrato", source: "contracts", optional: true },
    {
      key: "supplier",
      label: "Fornecedor",
      source: "suppliers",
      optional: true,
    },
    {
      key: "category",
      label: "Categoria",
      options: { CAPEX: "CAPEX", OPEX: "OPEX" },
      optional: true,
    },
  ];
  return (
    <details className="filters" open>
      <summary>Filtros do período e da estrutura</summary>
      <div className="filter-grid">
        {fields.map((f) => (
          <FieldInput
            key={f.key}
            field={f}
            options={options}
            value={value[f.key] ?? ""}
            onChange={(v) =>
              onChange({
                ...value,
                ...(f.key === "month"
                  ? { quarter: "" }
                  : f.key === "quarter"
                    ? { month: "" }
                    : {}),
                [f.key]: v,
              })
            }
          />
        ))}
        <button
          className="secondary"
          onClick={() => onChange({ year: String(new Date().getFullYear()) })}
        >
          Limpar filtros
        </button>
      </div>
    </details>
  );
}
export function queryString(filters: Record<string, string>) {
  return new URLSearchParams(
    Object.entries(filters).filter(([, v]) => v),
  ).toString();
}
