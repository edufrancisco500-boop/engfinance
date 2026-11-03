import { useEffect, useState, type FormEvent } from "react";
import { api, post, dateLabel, number, type Row } from "./api";
import {
  Empty,
  ErrorBox,
  FieldInput,
  Filters,
  Loading,
  Modal,
  Pill,
  queryString,
  useRows,
  type Options,
} from "./components";
import { useDashboard } from "./Dashboard";
import { catalog } from "./catalog";

export function Evaluations({
  refresh,
  onChange,
  options,
  metadata,
  filters,
  setFilters,
}: {
  refresh: number;
  onChange: () => void;
  options: Options;
  metadata: any;
  filters: Record<string, string>;
  setFilters: (v: Record<string, string>) => void;
}) {
  const { rows, error, loading } = useRows("invitations", refresh);
  const [selected, setSelected] = useState<Row | null>(null),
    [tab, setTab] = useState("mine"),
    [campaign, setCampaign] = useState(false);
  const { data } = useDashboard(filters, refresh);
  return (
    <>
      <div className="page-intro">
        <p>
          Feedback trimestral e acompanhamento do desempenho dos fornecedores.
        </p>
        {metadata.permissions.includes("evaluations.add_invitation") && (
          <button onClick={() => setCampaign(true)}>＋ Ciclo e convites</button>
        )}
      </div>
      <div className="tabs">
        <button
          className={tab === "mine" ? "active" : ""}
          onClick={() => setTab("mine")}
        >
          Minhas avaliações
        </button>
        <button
          className={tab === "results" ? "active" : ""}
          onClick={() => setTab("results")}
        >
          Resultados agregados
        </button>
      </div>
      <ErrorBox message={error} />
      {tab === "mine" ? (
        loading ? (
          <Loading />
        ) : (
          <div className="invitation-grid">
            {rows.map((r) => (
              <section className="invitation-card" key={r.id}>
                <span className="eyebrow">{r.cycle_label}</span>
                <h2>{r.contract_name}</h2>
                <p>{r.criteria_detail.length} critérios · notas de 1 a 5</p>
                <div className="section-heading">
                  <Pill value={r.completed ? "DONE" : "OPEN"} />
                  <button
                    className={r.completed ? "secondary" : ""}
                    disabled={r.completed}
                    onClick={() => setSelected(r)}
                  >
                    {r.completed ? "Enviada" : "Avaliar contrato →"}
                  </button>
                </div>
              </section>
            ))}
            {!rows.length && (
              <Empty text="Você ainda não recebeu convites para avaliação." />
            )}
          </div>
        )
      ) : (
        <>
          <Filters value={filters} onChange={setFilters} options={options} />
          {data ? (
            <>
              <div className="kpi-grid">
                <section>
                  <p>Nota média</p>
                  <h1>
                    {data.evaluations.average === null
                      ? "—"
                      : number(data.evaluations.average)}{" "}
                    <small>/5</small>
                  </h1>
                </section>
                <section>
                  <p>Avaliações recebidas</p>
                  <h1>{data.evaluations.responses}</h1>
                </section>
                <section>
                  <p>Convites</p>
                  <h1>{data.evaluations.invited}</h1>
                </section>
                <section>
                  <p>Participação</p>
                  <h1>
                    {data.evaluations.participation === null
                      ? "—"
                      : number(data.evaluations.participation) + "%"}
                  </h1>
                </section>
              </div>
              <section>
                <h2>Notas por critério</h2>
                {data.evaluations.criteria.length ? (
                  data.evaluations.criteria.map((c: any) => (
                    <div className="criterion-result" key={c.criterion__name}>
                      <span>{c.criterion__name}</span>
                      <div className="progress-track">
                        <i
                          style={{
                            width: `${(Number(c.average ?? 0) / 5) * 100}%`,
                          }}
                        />
                      </div>
                      <strong>
                        {c.average === null ? "—" : number(c.average)}
                      </strong>
                    </div>
                  ))
                ) : (
                  <Empty text="Amostra insuficiente ou sem notas neste recorte." />
                )}
                <p className="muted">
                  “Não sei avaliar” não entra na média. Mínimo de respostas para
                  agregados: {data.evaluations.minimum_responses ?? "—"}.
                </p>
              </section>
              <section>
                <h2>Comparação entre contratos</h2>
                <table>
                  <thead>
                    <tr>
                      <th>Contrato</th>
                      <th>Média</th>
                      <th>Respostas</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.evaluations.contracts.map((r: any) => (
                      <tr key={r.evaluation__invitation__contract_id}>
                        <td>{r.evaluation__invitation__contract__name}</td>
                        <td>{r.average === null ? "—" : number(r.average)}</td>
                        <td>{r.responses}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </section>
            </>
          ) : (
            <Empty text="Resultados dependem de permissão e avaliações no período." />
          )}
        </>
      )}
      {selected && (
        <EvaluationForm
          invitation={selected}
          onClose={() => setSelected(null)}
          onSaved={() => {
            setSelected(null);
            onChange();
          }}
        />
      )}
      {campaign && (
        <Campaign
          options={options}
          metadata={metadata}
          onClose={() => setCampaign(false)}
          onSaved={() => {
            setCampaign(false);
            onChange();
          }}
        />
      )}
    </>
  );
}

function EvaluationForm({
  invitation,
  onClose,
  onSaved,
}: {
  invitation: Row;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [scores, setScores] = useState<Record<string, string>>({}),
    [comments, setComments] = useState<Record<string, string>>({}),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const labels: Record<string, string> = {
    positives: "Pontos positivos",
    negatives: "Pontos negativos",
    problems: "Problemas encontrados",
    suggestions: "Sugestões de melhoria",
    continuity: "Justificativa sobre continuidade",
  };
  async function send(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await post("/api/v1/evaluations/", {
        invitation: invitation.id,
        ...comments,
        answers: invitation.criteria_detail.map((c: Row) => ({
          criterion: c.id,
          score: scores[c.id] === "NA" ? null : Number(scores[c.id]),
        })),
      });
      onSaved();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal
      title={`Avaliar · ${invitation.contract_name}`}
      onClose={onClose}
      wide
    >
      <p className="notice">
        As respostas individuais têm acesso restrito. A continuidade do contrato
        será decidida por pessoas autorizadas.
      </p>
      <ErrorBox message={error} />
      <form onSubmit={send}>
        <div className="evaluation-scores">
          {invitation.criteria_detail.map((c: Row) => (
            <label key={c.id}>
              {c.name}
              <select
                required
                value={scores[c.id] ?? ""}
                onChange={(e) =>
                  setScores({ ...scores, [c.id]: e.target.value })
                }
              >
                <option value="">Selecione uma resposta</option>
                {[1, 2, 3, 4, 5].map((v) => (
                  <option key={v} value={v}>
                    {v} —{" "}
                    {
                      [
                        "Muito insatisfatório",
                        "Insatisfatório",
                        "Regular",
                        "Bom",
                        "Excelente",
                      ][v - 1]
                    }
                  </option>
                ))}
                <option value="NA">Não sei avaliar</option>
              </select>
            </label>
          ))}
        </div>
        <div className="record-form">
          {Object.entries(labels).map(([key, label]) => (
            <label key={key}>
              {label}
              <textarea
                rows={3}
                value={comments[key] ?? ""}
                onChange={(e) =>
                  setComments({ ...comments, [key]: e.target.value })
                }
              />
            </label>
          ))}
        </div>
        <div className="form-actions">
          <button className="secondary" type="button" onClick={onClose}>
            Cancelar
          </button>
          <button disabled={busy}>Enviar avaliação</button>
        </div>
      </form>
    </Modal>
  );
}

function Campaign({
  options,
  metadata,
  onClose,
  onSaved,
}: {
  options: Options;
  metadata: any;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [step, setStep] = useState("invite"),
    [values, setValues] = useState<Record<string, string>>({}),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const { rows: cycles } = useRows("cycles", 0);
  async function save(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      if (step === "cycle") await post("/api/v1/cycles/", values);
      else
        await post("/api/v1/invitations/", {
          ...values,
          criteria: metadata.criteria.map((c: Row) => c.id),
        });
      onSaved();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal title="Organizar avaliações" onClose={onClose}>
      <div className="tabs">
        <button
          className={step === "invite" ? "active" : ""}
          onClick={() => {
            setStep("invite");
            setValues({});
          }}
        >
          Convidar
        </button>
        <button
          className={step === "cycle" ? "active" : ""}
          onClick={() => {
            setStep("cycle");
            setValues({});
          }}
        >
          Novo ciclo
        </button>
      </div>
      <ErrorBox message={error} />
      <form onSubmit={save} className="stack">
        {step === "cycle" ? (
          ["year", "quarter", "opens", "closes"].map((key) => (
            <FieldInput
              key={key}
              field={{
                key,
                label: (
                  {
                    year: "Ano",
                    quarter: "Trimestre (1–4)",
                    opens: "Abertura",
                    closes: "Encerramento",
                  } as Record<string, string>
                )[key],
                type: key === "year" || key === "quarter" ? "number" : "date",
              }}
              value={values[key]}
              onChange={(v) => setValues({ ...values, [key]: v })}
              options={options}
            />
          ))
        ) : (
          <>
            <label>
              Ciclo
              <select
                required
                value={values.cycle ?? ""}
                onChange={(e) =>
                  setValues({ ...values, cycle: e.target.value })
                }
              >
                <option value="">Selecione</option>
                {cycles.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.year} · {c.quarter}º trimestre
                  </option>
                ))}
              </select>
            </label>
            <FieldInput
              field={{
                key: "contract",
                label: "Contrato",
                source: "contracts",
              }}
              value={values.contract}
              onChange={(v) => setValues({ ...values, contract: v })}
              options={options}
            />
            <label>
              Colaborador
              <select
                required
                value={values.user ?? ""}
                onChange={(e) => setValues({ ...values, user: e.target.value })}
              >
                <option value="">Selecione</option>
                {(metadata.eligible_users ?? []).map((u: Row) => (
                  <option key={u.id} value={u.id}>
                    {u.username}
                  </option>
                ))}
              </select>
            </label>
            <p className="muted">
              Serão usados os {metadata.criteria.length} critérios ativos. O
              colaborador precisa de acesso à gerência do contrato.
            </p>
          </>
        )}
        <button disabled={busy}>Salvar</button>
      </form>
    </Modal>
  );
}

export function Reports({
  filters,
  setFilters,
  options,
  metadata,
}: {
  filters: Record<string, string>;
  setFilters: (v: Record<string, string>) => void;
  options: Options;
  metadata: any;
}) {
  const [section, setSection] = useState("portfolios"),
    [resource, setResource] = useState("projects"),
    [file, setFile] = useState<File | null>(null),
    [preview, setPreview] = useState<any>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const query = queryString(filters);
  async function importFile(commit = false) {
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      const form = new FormData();
      form.set("file", file);
      form.set("resource", resource);
      form.set("commit", String(commit));
      setPreview(await api("/api/import/", { method: "POST", body: form }));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="page-intro">
        <p>
          Exporte o recorte autorizado e valide cadastros antes de importar.
        </p>
      </div>
      <Filters value={filters} onChange={setFilters} options={options} />
      <section>
        <h2>Exportar relatório</h2>
        <div className="report-export">
          <label>
            Conteúdo
            <select
              value={section}
              onChange={(e) => setSection(e.target.value)}
            >
              {Object.entries({
                portfolios: "Carteiras",
                contracts: "Contratos e risco",
                projects: "Projetos e avanço",
                categories: "CAPEX/OPEX",
                monthly: "Evolução mensal",
              }).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
          </label>
          <a
            className="button-link"
            href={`/api/reports/?${query}&section=${section}&format_file=xlsx`}
            download
          >
            Baixar Excel ↓
          </a>
          <a
            className="button-link secondary"
            href={`/api/reports/?${query}&section=${section}&format_file=csv`}
            download
          >
            Baixar CSV ↓
          </a>
        </div>
        <p className="muted">
          Os arquivos respeitam os filtros e as permissões da sessão. A
          exportação é auditada.
        </p>
      </section>
      <section>
        <h2>Importação controlada de cadastros</h2>
        <ErrorBox message={error} />
        <div className="record-form">
          <label>
            Cadastro
            <select
              value={resource}
              onChange={(e) => {
                setResource(e.target.value);
                setPreview(null);
              }}
            >
              {[
                "departments",
                "portfolios",
                "projects",
                "suppliers",
                "contracts",
                "cost-centers",
              ]
                .filter(
                  (r) =>
                    metadata.permissions.includes(
                      `registry.add_${catalog[r].model}`,
                    ) || metadata.superuser,
                )
                .map((r) => (
                  <option key={r} value={r}>
                    {catalog[r].title}
                  </option>
                ))}
            </select>
          </label>
          <label>
            Arquivo CSV ou XLSX
            <input
              type="file"
              accept=".csv,.xlsx"
              onChange={(e) => {
                setFile(e.target.files?.[0] ?? null);
                setPreview(null);
              }}
            />
          </label>
        </div>
        <p className="muted">
          Até 500 registros, arquivo de até 2 MB. Cabeçalhos:{" "}
          {catalog[resource].fields.map((f) => f.key).join(", ")}. Referências
          como department e supplier usam IDs. Fórmulas não são aceitas.
        </p>
        <button disabled={!file || busy} onClick={() => importFile(false)}>
          Validar e visualizar
        </button>
        {preview && (
          <div className="import-preview">
            <p className="notice">
              {preview.committed
                ? `${preview.count} registros importados.`
                : `Arquivo válido: ${preview.count} registros. Confira antes de confirmar.`}
            </p>
            <pre>{JSON.stringify(preview.preview, null, 2)}</pre>
            {!preview.committed && (
              <button disabled={busy} onClick={() => importFile(true)}>
                Confirmar importação dos {preview.count} registros
              </button>
            )}
          </div>
        )}
      </section>
    </>
  );
}

export function Insights({
  filters,
  setFilters,
  options,
}: {
  filters: Record<string, string>;
  setFilters: (v: Record<string, string>) => void;
  options: Options;
}) {
  const [question, setQuestion] = useState(
      "Quais contratos apresentam os maiores riscos financeiros?",
    ),
    [result, setResult] = useState<any>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  async function generate(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      setResult(
        await api(
          `/api/ai-summary/?${queryString(filters)}&question=${encodeURIComponent(question)}`,
        ),
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => setResult(null), [queryString(filters)]);
  return (
    <>
      <div className="page-intro">
        <p>
          Análises de apoio com cálculos rastreáveis e acesso restrito ao seu
          escopo.
        </p>
        <span className="pill">Provedor local</span>
      </div>
      <Filters value={filters} onChange={setFilters} options={options} />
      <section className="insight-form">
        <h2>Resumo executivo</h2>
        <p className="muted">
          Nesta versão, os textos são gerados por regras locais. Nenhuma
          informação é enviada a um provedor externo de IA.
        </p>
        <form onSubmit={generate}>
          <label>
            O que deseja analisar?
            <textarea
              maxLength={500}
              rows={3}
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              required
            />
          </label>
          <div className="suggestions">
            {[
              "Quais contratos têm as piores avaliações?",
              "Qual carteira possui maior saldo disponível?",
              "Quais contratos apresentam os maiores riscos financeiros?",
            ].map((q) => (
              <button
                className="secondary small"
                type="button"
                key={q}
                onClick={() => setQuestion(q)}
              >
                {q}
              </button>
            ))}
          </div>
          <button disabled={busy}>
            {busy ? "Preparando análise…" : "Gerar análise →"}
          </button>
        </form>
      </section>
      <ErrorBox message={error} />
      {result && (
        <section className="insight-result">
          <span className="eyebrow">
            ANÁLISE GERENCIAL · {dateLabel(result.source.generated_at)}
          </span>
          <h2>{result.question}</h2>
          {result.paragraphs.map((p: string, i: number) => (
            <p key={i}>{p}</p>
          ))}
          {result.themes?.length > 0 && (
            <>
              <h3>Temas recorrentes nas avaliações</h3>
              {result.themes.map((t: any) => (
                <p key={t.name}>
                  {t.name}: {t.count} menções.
                </p>
              ))}
            </>
          )}
          <div className="notice">{result.limitations}</div>
          <small>
            Fonte: dados autorizados do backend · {result.source.policy.name}
          </small>
        </section>
      )}
    </>
  );
}

export function Administration({
  metadata,
  refresh,
}: {
  metadata: any;
  refresh: number;
}) {
  const [events, setEvents] = useState<Row[]>([]),
    [error, setError] = useState("");
  useEffect(() => {
    api("/api/audit/")
      .then(setEvents)
      .catch((e) => setError(e.message));
  }, [refresh]);
  return (
    <>
      <div className="page-intro">
        <p>
          Configuração, políticas, permissões e rastreabilidade do ambiente.
        </p>
      </div>
      <div className="chart-grid">
        <section>
          <h2>Sua conta</h2>
          <p>
            <strong>{metadata.username}</strong>
          </p>
          <p>Perfis: {metadata.groups.join(", ") || "Sem perfil"}</p>
          <p>Permissões: {metadata.permissions.length} ações concedidas</p>
          <p className="muted">
            As concessões por gerência limitam listagens, detalhes, relatórios e
            operações.
          </p>
        </section>
        <section>
          <h2>Política financeira</h2>
          <p>
            <strong>{metadata.policy?.name ?? "Não configurada"}</strong>
          </p>
          <p>{metadata.policy?.explanation}</p>
          <span className="pill">
            {metadata.policy?.demo ? "Demonstração" : "Política corporativa"}
          </span>
        </section>
      </div>
      {metadata.policy &&
        (metadata.superuser ||
          metadata.permissions.includes("finance.change_policy")) && (
          <PolicyForm metadata={metadata} />
        )}
      <section>
        <h2>Definições que exigem validação corporativa</h2>
        <ul className="decision-list">
          {metadata.pending_decisions.map((d: string) => (
            <li key={d}>{d}</li>
          ))}
        </ul>
        <p className="muted">
          Os parâmetros empresariais devem ser formalizados antes de utilizar
          dados reais. Identidade corporativa e integrações externas permanecem
          desconectadas.
        </p>
      </section>
      <section>
        <h2>Histórico de auditoria</h2>
        <p className="muted">
          Até 200 ações recentes da sua conta. A consulta transversal é restrita
          à conta técnica.
        </p>
        <ErrorBox message={error} />
        {events.length ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Data</th>
                  <th>Ação</th>
                  <th>Recurso</th>
                  <th>Identificador</th>
                </tr>
              </thead>
              <tbody>
                {events.map((e) => (
                  <tr key={e.id}>
                    <td>{dateLabel(e.created_at)}</td>
                    <td>{e.action}</td>
                    <td>{e.resource}</td>
                    <td>#{e.object_id}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty />
        )}
      </section>
    </>
  );
}

function PolicyForm({ metadata }: { metadata: any }) {
  const [values, setValues] = useState<Record<string, string>>({
      low_balance_percent: String(metadata.policy.low_balance_percent),
      poor_rating: String(metadata.policy.poor_rating),
      expiry_days: String(metadata.policy.expiry_days),
      reason: "",
    }),
    [error, setError] = useState(""),
    [success, setSuccess] = useState(""),
    [busy, setBusy] = useState(false);
  async function save(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setSuccess("");
    try {
      await api("/api/policy/", {
        method: "PATCH",
        body: JSON.stringify(values),
        headers: { "Content-Type": "application/json" },
      });
      setSuccess(
        "Alertas atualizados com auditoria. Os próximos dashboards usarão os novos limites.",
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section>
      <h2>Parâmetros de alerta</h2>
      <ErrorBox message={error} />
      {success && <p className="notice">{success}</p>}
      <form onSubmit={save}>
        <div className="record-form">
          {[
            {
              key: "low_balance_percent",
              label: "Saldo reduzido abaixo de (%)",
              type: "number",
            },
            {
              key: "poor_rating",
              label: "Avaliação insatisfatória abaixo de",
              type: "number",
            },
            {
              key: "expiry_days",
              label: "Antecedência do vencimento (dias)",
              type: "number",
            },
            { key: "reason", label: "Justificativa", type: "textarea" },
          ].map((field) => (
            <FieldInput
              key={field.key}
              field={field}
              value={values[field.key]}
              onChange={(v) => setValues({ ...values, [field.key]: v })}
              options={{}}
            />
          ))}
        </div>
        <div className="form-actions">
          <button disabled={busy}>Salvar parâmetros</button>
        </div>
      </form>
    </section>
  );
}
