import { useEffect, useState, type FormEvent } from "react";
import {
  api,
  post,
  money,
  dateLabel,
  stateLabel,
  kindLabel,
  type Row,
} from "./api";
import { catalog } from "./catalog";
import {
  DataTable,
  Empty,
  ErrorBox,
  FieldInput,
  Loading,
  Modal,
  Pill,
  labelRow,
  useRows,
  type Options,
} from "./components";

type Props = {
  resource: string;
  refresh: number;
  options: Options;
  permissions: string[];
  superuser: boolean;
  onChange: () => void;
};
export function Records({
  resource,
  refresh,
  options,
  permissions,
  superuser,
  onChange,
}: Props) {
  const config = catalog[resource];
  const { rows, error, loading } = useRows(resource, refresh);
  const [search, setSearch] = useState(""),
    [selected, setSelected] = useState<Row | null>(null),
    [editing, setEditing] = useState<Row | boolean | null>(null),
    [page, setPage] = useState(1);
  const can =
    superuser ||
    permissions.includes(`${config.app ?? "registry"}.add_${config.model}`);
  const filtered = rows.filter((r) =>
    [r.name, r.code, r.reference, r.reason, r.title].some((v) =>
      String(v ?? "")
        .toLowerCase()
        .includes(search.toLowerCase()),
    ),
  );
  return (
    <>
      <div className="page-intro">
        <div>
          <p>{config.subtitle}</p>
        </div>
        {can && (
          <button onClick={() => setEditing(true)}>＋ Novo registro</button>
        )}
      </div>
      <ErrorBox message={error} />
      <section className="table-section">
        <div className="section-heading">
          <h2>
            {config.title} <span className="badge">{filtered.length}</span>
          </h2>
          <input
            className="search"
            aria-label="Buscar registros"
            placeholder="Buscar por código, nome ou referência…"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
          />
        </div>
        {loading ? (
          <Loading />
        ) : (
          <DataTable
            resource={resource}
            rows={filtered.slice((page - 1) * 15, page * 15)}
            options={options}
            onSelect={setSelected}
          />
        )}
        <footer>
          <span>{filtered.length} registros no seu escopo</span>
          <div>
            <button
              className="secondary small"
              disabled={page <= 1}
              onClick={() => setPage((v) => v - 1)}
            >
              Anterior
            </button>
            <span>
              {" "}
              {page} / {Math.max(1, Math.ceil(filtered.length / 15))}{" "}
            </span>
            <button
              className="secondary small"
              disabled={page * 15 >= filtered.length}
              onClick={() => setPage((v) => v + 1)}
            >
              Próxima
            </button>
          </div>
        </footer>
      </section>
      {editing && (
        <RecordForm
          key={`${resource}-${typeof editing === "object" ? editing.id : "new"}`}
          resource={resource}
          record={typeof editing === "object" ? editing : undefined}
          options={options}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            setSelected(null);
            onChange();
          }}
        />
      )}
      {selected && (
        <RecordDetail
          resource={resource}
          record={selected}
          options={options}
          permissions={permissions}
          superuser={superuser}
          onClose={() => setSelected(null)}
          onChange={onChange}
          onEdit={() => {
            setEditing(selected);
            setSelected(null);
          }}
        />
      )}
    </>
  );
}

function RecordForm({
  resource,
  record,
  options,
  onClose,
  onSaved,
}: {
  resource: string;
  record?: Row;
  options: Options;
  onClose: () => void;
  onSaved: () => void;
}) {
  const config = catalog[resource];
  const [values, setValues] = useState<Record<string, any>>(() =>
    Object.fromEntries(
      config.fields.map((f) => [f.key, record?.[f.key] ?? f.default ?? ""]),
    ),
  );
  const [active, setActive] = useState(record?.active ?? true),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const [mode, setMode] = useState("percent"),
    [split, setSplit] = useState<{ allocation: string; value: string }[]>([]),
    [sources, setSources] = useState<string[]>([]);
  const splitResource = resource === "fundings" || resource === "documents";
  async function save(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const data: Record<string, any> = {};
      for (const field of config.fields) {
        const v = values[field.key];
        if (v !== "" && v !== undefined) data[field.key] = v;
        else if (field.optional)
          data[field.key] = field.source || field.type === "date" ? null : "";
      }
      if (!config.app || config.app === "registry") data.active = active;
      if (splitResource)
        data.split = split.map((s) => ({
          allocation: Number(s.allocation),
          [mode]: s.value,
        }));
      if (resource === "documents") {
        data.source_documents = sources.map(Number);
        data.idempotency_key = crypto.randomUUID();
      }
      if (record)
        await api(`/api/v1/${resource}/${record.id}/`, {
          method: "PATCH",
          body: JSON.stringify(data),
          headers: { "Content-Type": "application/json" },
        });
      else await post(`/api/v1/${resource}/`, data);
      onSaved();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const expected: Record<string, string> = {
    MEASUREMENT: "COMMITMENT",
    INVOICE: "MEASUREMENT",
    PAYMENT: "INVOICE",
  };
  const possibleSources = (options.documents ?? []).filter(
    (d) =>
      d.status === "APPROVED" &&
      !d.reversal_of &&
      !d.reversed &&
      d.contract === Number(values.contract) &&
      d.kind === expected[values.kind],
  );
  return (
    <Modal
      title={`${record ? "Editar" : "Novo"} · ${config.title}`}
      onClose={onClose}
      wide
    >
      <ErrorBox message={error} />
      <form onSubmit={save}>
        <div className="record-form">
          {config.fields.map((field) => (
            <FieldInput
              key={field.key}
              field={field}
              value={values[field.key]}
              onChange={(v) => setValues({ ...values, [field.key]: v })}
              options={options}
            />
          ))}
          {(!config.app || config.app === "registry") && (
            <label className="check">
              <input
                type="checkbox"
                checked={active}
                onChange={(e) => setActive(e.target.checked)}
              />
              Registro ativo
            </label>
          )}
        </div>
        {splitResource && (
          <div className="split-editor">
            <div className="section-heading">
              <div>
                <h3>Distribuição entre fontes</h3>
                <p className="muted">
                  Cada alocação identifica carteira, projeto, centro de custo e
                  CAPEX/OPEX.
                </p>
              </div>
              <select
                aria-label="Modo de rateio"
                value={mode}
                onChange={(e) => {
                  setMode(e.target.value);
                  setSplit([]);
                }}
              >
                <option value="percent">Por percentual</option>
                <option value="amount">Por valor</option>
              </select>
            </div>
            {split.map((part, index) => (
              <div className="split-row" key={index}>
                <select
                  aria-label={`Fonte ${index + 1}`}
                  required
                  value={part.allocation}
                  onChange={(e) =>
                    setSplit(
                      split.map((p, i) =>
                        i === index ? { ...p, allocation: e.target.value } : p,
                      ),
                    )
                  }
                >
                  <option value="">Selecione uma alocação aprovada</option>
                  {(options.allocations ?? [])
                    .filter((a) => a.status === "APPROVED")
                    .map((a) => (
                      <option key={a.id} value={a.id}>
                        {labelRow(a, "allocations", options)} · saldo{" "}
                        {money(a.balance)}
                      </option>
                    ))}
                </select>
                <input
                  type="number"
                  step={mode === "percent" ? "0.0001" : "0.01"}
                  min="0.01"
                  aria-label={mode === "percent" ? "Percentual" : "Valor"}
                  placeholder={mode === "percent" ? "%" : "R$"}
                  required
                  value={part.value}
                  onChange={(e) =>
                    setSplit(
                      split.map((p, i) =>
                        i === index ? { ...p, value: e.target.value } : p,
                      ),
                    )
                  }
                />
                <button
                  type="button"
                  className="secondary"
                  aria-label="Remover parcela do rascunho"
                  onClick={() => setSplit(split.filter((_, i) => i !== index))}
                >
                  ✕
                </button>
              </div>
            ))}
            <button
              className="secondary small"
              type="button"
              onClick={() =>
                setSplit([...split, { allocation: "", value: "" }])
              }
            >
              ＋ Adicionar fonte
            </button>
            <span className="muted">
              {" "}
              Total informado:{" "}
              {split
                .reduce((s, p) => s + Number(p.value || 0), 0)
                .toLocaleString("pt-BR")}{" "}
              {mode === "percent" ? "%" : "reais"}
            </span>
            {resource === "documents" && !split.length && (
              <p className="muted">
                Sem parcelas manuais, o sistema usa o rateio contratual
                selecionado. Sem rateio selecionado, informe as parcelas.
              </p>
            )}
          </div>
        )}
        {resource === "documents" &&
          values.kind &&
          values.kind !== "COMMITMENT" && (
            <label>
              Documentos de origem — {kindLabel[expected[values.kind]]}
              <select
                multiple
                size={4}
                required
                value={sources}
                onChange={(e) =>
                  setSources(
                    Array.from(e.target.selectedOptions, (o) => o.value),
                  )
                }
              >
                {possibleSources.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.reference} · {money(d.amount)}
                  </option>
                ))}
              </select>
              <small>
                Selecione uma ou mais origens da etapa anterior. As parcelas
                precisam ter saldo nas mesmas fontes.
              </small>
            </label>
          )}
        {config.financial && (
          <p className="notice">
            O registro será salvo como rascunho. Envie para aprovação na tela de
            detalhes. Em demonstração, a mesma pessoa pode aprovar; no uso real
            haverá segregação.
          </p>
        )}
        <div className="form-actions">
          <button type="button" className="secondary" onClick={onClose}>
            Cancelar
          </button>
          <button disabled={busy}>
            {busy ? "Salvando…" : "Salvar registro"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

function RecordDetail({
  resource,
  record,
  options,
  permissions,
  superuser,
  onClose,
  onChange,
  onEdit,
}: {
  resource: string;
  record: Row;
  options: Options;
  permissions: string[];
  superuser: boolean;
  onClose: () => void;
  onChange: () => void;
  onEdit: () => void;
}) {
  const [current, setCurrent] = useState(record),
    [error, setError] = useState(""),
    [reason, setReason] = useState(""),
    [busy, setBusy] = useState(false);
  const config = catalog[resource];
  async function action(name: string) {
    setBusy(true);
    setError("");
    try {
      const result = await post(`/api/v1/${resource}/${current.id}/${name}/`, {
        reason,
      });
      if (name === "reverse") {
        onChange();
        onClose();
      } else {
        setCurrent(result);
        onChange();
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal
      title={
        current.name ??
        current.reference ??
        current.title ??
        `${config.title} #${current.id}`
      }
      onClose={onClose}
      wide
    >
      <ErrorBox message={error} />
      <div className="detail-grid">
        {config.fields.map((field) => (
          <div key={field.key}>
            <span className="detail-label">{field.label}</span>
            <strong>
              {field.source
                ? labelRow(
                    options[field.source]?.find(
                      (r) => r.id === Number(current[field.key]),
                    ) ?? { id: current[field.key] },
                    field.source,
                    options,
                  )
                : field.type === "money"
                  ? money(current[field.key])
                  : field.type === "date"
                    ? dateLabel(current[field.key])
                    : field.options
                      ? field.options[current[field.key]]
                      : current[field.key] || "—"}
            </strong>
          </div>
        ))}
      </div>
      {current.status && (
        <p>
          <Pill value={current.status} />
        </p>
      )}
      {current.distribution && (
        <>
          <h3>Parcelas financeiras</h3>
          <table>
            <thead>
              <tr>
                <th>Carteira</th>
                <th>Projeto</th>
                <th>Categoria</th>
                <th>Percentual</th>
                <th>Valor</th>
              </tr>
            </thead>
            <tbody>
              {current.distribution.map((p: any) => (
                <tr key={p.allocation}>
                  <td>{p.portfolio}</td>
                  <td>{p.project ?? "—"}</td>
                  <td>{p.category}</td>
                  <td>{p.percent}%</td>
                  <td>{money(p.amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
      {config.financial && (
        <div className="approval-box">
          <h3>Fluxo de aprovação</h3>
          {current.status === "DRAFT" && (
            <button disabled={busy} onClick={() => action("submit")}>
              Enviar para aprovação
            </button>
          )}
          {current.status === "SUBMITTED" &&
            (superuser || permissions.includes("finance.approve_finance")) && (
              <>
                <label>
                  Justificativa da rejeição, se aplicável
                  <textarea
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                  />
                </label>
                <div className="button-row">
                  <button disabled={busy} onClick={() => action("approve")}>
                    Aprovar operação
                  </button>
                  <button
                    className="danger"
                    disabled={busy || !reason.trim()}
                    onClick={() => action("reject")}
                  >
                    Rejeitar
                  </button>
                </div>
              </>
            )}
          {resource === "documents" &&
            current.status === "APPROVED" &&
            !current.reversal_of &&
            !current.reversed && (
              <>
                <label>
                  Motivo do estorno
                  <textarea
                    required
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                  />
                </label>
                <button
                  className="danger"
                  disabled={busy || !reason.trim()}
                  onClick={() => action("reverse")}
                >
                  Solicitar estorno auditado
                </button>
                <p className="muted">
                  O estorno será um novo rascunho e precisará de aprovação. O
                  original permanece no histórico.
                </p>
              </>
            )}
        </div>
      )}
      {!config.financial &&
        (superuser ||
          permissions.includes(
            `${config.app ?? "registry"}.change_${config.model}`,
          )) && (
          <button className="secondary" onClick={onEdit}>
            Editar cadastro
          </button>
        )}
      {resource === "contracts" && (
        <ContractSections
          record={current}
          options={options}
          permissions={permissions}
          onChange={onChange}
        />
      )}
    </Modal>
  );
}

function ContractSections({
  record,
  options,
  permissions,
  onChange,
}: {
  record: Row;
  options: Options;
  permissions: string[];
  onChange: () => void;
}) {
  const [tab, setTab] = useState("documents");
  const [performance, setPerformance] = useState<any>(null);
  useEffect(() => {
    api(`/api/dashboard/?contract=${record.id}`)
      .then(setPerformance)
      .catch(() => setPerformance(null));
  }, [record.id, options.documents]);
  const labels: Record<string, string> = {
    documents: "Movimentações",
    fundings: "Rateios",
    amendments: "Aditivos",
    "action-plans": "Planos de ação",
    attachments: "Documentos anexos",
    performance: "Desempenho e avaliações",
  };
  return (
    <div className="contract-sections">
      <h3>Valor atualizado: {money(record.current_value)}</h3>
      <div className="tabs">
        {Object.entries(labels).map(([key, label]) => (
          <button
            className={tab === key ? "active" : ""}
            key={key}
            onClick={() => setTab(key)}
          >
            {label}
          </button>
        ))}
      </div>
      {tab === "performance" ? (
        performance ? (
          <>
            <div className="metric-strip">
              <div>
                <span>Comprometido</span>
                <strong>{money(performance.committed)}</strong>
              </div>
              <div>
                <span>Realizado</span>
                <strong>{money(performance.realized)}</strong>
              </div>
              <div>
                <span>Pago</span>
                <strong>{money(performance.paid)}</strong>
              </div>
            </div>
            <h3>
              Avaliação média:{" "}
              {performance.evaluations.average === null
                ? "Sem notas"
                : performance.evaluations.average.toFixed(2) + " / 5"}
            </h3>
            <p className="muted">
              {performance.evaluations.responses} avaliações recebidas.
              Informações individuais permanecem restritas.
            </p>
            {performance.alerts.map((a: any) => (
              <p className="notice" key={a.contract}>
                {a.reasons.join(" · ")}
              </p>
            ))}
          </>
        ) : (
          <Empty text="Desempenho indisponível neste escopo." />
        )
      ) : tab === "attachments" ? (
        <Attachments
          contract={record.id}
          options={options}
          permissions={permissions}
          onChange={onChange}
        />
      ) : (
        <DataTable
          resource={tab}
          rows={(options[tab] ?? []).filter((r) => r.contract === record.id)}
          options={options}
        />
      )}
    </div>
  );
}

function Attachments({
  contract,
  options,
  permissions,
  onChange,
}: {
  contract: number;
  options: Options;
  permissions: string[];
  onChange: () => void;
}) {
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  async function upload(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    const form = e.currentTarget;
    const data = new FormData(form);
    data.set("contract", String(contract));
    try {
      await api("/api/v1/attachments/", { method: "POST", body: data });
      form.reset();
      onChange();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const rows = (options.attachments ?? []).filter(
    (r) => r.contract === contract,
  );
  return (
    <>
      <ErrorBox message={error} />
      {permissions.includes("finance.add_attachment") && (
        <form className="upload-form" onSubmit={upload}>
          <label>
            Nome do documento
            <input name="name" required />
          </label>
          <label>
            Arquivo (PDF, PNG, JPG ou TXT, até 5 MB)
            <input
              type="file"
              name="file"
              accept=".pdf,.png,.jpg,.jpeg,.txt"
              required
            />
          </label>
          <button disabled={busy}>Anexar</button>
        </form>
      )}
      {rows.length ? (
        rows.map((r) => (
          <div className="download-row" key={r.id}>
            <span>{r.name}</span>
            <a href={`/api/v1/attachments/${r.id}/download/`} download>
              Baixar documento ↓
            </a>
          </div>
        ))
      ) : (
        <Empty text="Nenhum anexo neste contrato." />
      )}
    </>
  );
}
