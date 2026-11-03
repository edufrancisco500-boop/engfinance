import { useState } from "react";
import {
  BarChart,
  Bar,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Legend,
  AreaChart,
  Area,
} from "recharts";
import { money, number, dateLabel, type Row } from "./api";
import {
  ErrorBox,
  Filters,
  Loading,
  Modal,
  Empty,
  type Options,
} from "./components";
import { useDashboard } from "./Dashboard";

type Props = {
  filters: Record<string, string>;
  setFilters: (value: Record<string, string>) => void;
  options: Options;
  refresh: number;
};
const monthNames = [
  "Jan",
  "Fev",
  "Mar",
  "Abr",
  "Mai",
  "Jun",
  "Jul",
  "Ago",
  "Set",
  "Out",
  "Nov",
  "Dez",
];
const shortMoney = (value: number) =>
  value >= 1000000
    ? `${number(value / 1000000)} mi`
    : value >= 1000
      ? `${number(value / 1000)} mil`
      : number(value);
const statusLabels: Record<string, string> = {
  DRAFT: "Em preparação",
  ACTIVE: "Vigente",
  SUSPENDED: "Suspenso",
  CLOSED: "Encerrado",
  CANCELLED: "Cancelado",
};
const percent = (value: any) =>
  value === null || value === undefined ? "—" : `${number(value)}%`;
function remaining(row: Row) {
  return row.days_remaining === null
    ? "Término não informado"
    : row.days_remaining < 0
      ? `Vencido há ${Math.abs(row.days_remaining)} dias`
      : row.days_remaining === 0
        ? "Termina hoje"
        : `${row.days_remaining} dias restantes`;
}
function Balance({ row }: { row: Row }) {
  return (
    <div className="balance-indicator">
      <strong className={Number(row.balance) < 0 ? "negative" : ""}>
        {percent(row.balance_percent)}
      </strong>
      <div className="progress-track">
        <i
          style={{
            width: `${Math.max(0, Math.min(100, row.balance_percent ?? 0))}%`,
            background:
              Number(row.balance_percent) < 15 ? "#ce8960" : "#299a8d",
          }}
        />
      </div>
      <small>{money(row.balance)} para comprometer</small>
    </div>
  );
}

export function ContractDashboard({
  filters,
  setFilters,
  options,
  refresh,
  onUsage,
}: Props & { onUsage: () => void }) {
  const { data, error, loading } = useDashboard(filters, refresh);
  const [metric, setMetric] = useState("most_spent"),
    [selected, setSelected] = useState<Row | null>(null),
    [search, setSearch] = useState("");
  const metricField: Record<string, string> = {
    most_spent: "period_realized",
    most_paid: "period_paid",
    most_committed: "period_committed",
  };
  const metricName: Record<string, string> = {
    most_spent: "Realizado por medições",
    most_paid: "Pago",
    most_committed: "Comprometido",
  };
  const rows = (data?.contracts ?? []).filter((row: Row) =>
    `${row.code} ${row.name} ${row.supplier}`
      .toLowerCase()
      .includes(search.toLowerCase()),
  );
  const top = data?.contract_rankings?.[metric] ?? [];
  return (
    <>
      <div className="page-intro">
        <p>
          Contratos em foco: consumo, vigência, saldo, pessoas e cenários de
          execução.
        </p>
        <button onClick={onUsage}>＋ Registrar utilização</button>
      </div>
      <Filters value={filters} onChange={setFilters} options={options} />
      <ErrorBox message={error} />
      {loading ? (
        <Loading />
      ) : (
        data && (
          <>
            <div className="kpi-grid">
              <article className="kpi">
                <span className="kpi-icon blue">▤</span>
                <p>Contratos no recorte</p>
                <strong>{data.contracts_count}</strong>
                <small>
                  {data.contract_summary.usage_events} registros de utilização
                  no período
                </small>
              </article>
              <article className="kpi">
                <span className="kpi-icon teal">↗</span>
                <p>Gastos realizados no período</p>
                <strong>{money(data.contract_summary.period_realized)}</strong>
                <small>Medições aprovadas, descontados os estornos</small>
              </article>
              <article className="kpi">
                <span className="kpi-icon violet">◉</span>
                <p>Percentual de saldo contratual</p>
                <strong>
                  {percent(data.contract_summary.balance_percent)}
                </strong>
                <small>
                  {money(data.contract_summary.balance)} para comprometer
                </small>
              </article>
              <article className="kpi">
                <span className="kpi-icon amber">◷</span>
                <p>Próximos do término</p>
                <strong>{data.contract_summary.expiring}</strong>
                <small>
                  Até {data.policy.expiry_days} dias ·{" "}
                  {data.contract_summary.expired} vencidos
                </small>
              </article>
            </div>
            <div className="metric-strip">
              <div>
                <span>Valor contratual atualizado</span>
                <strong>{money(data.contract_summary.value)}</strong>
              </div>
              <div>
                <span>Comprometido acumulado</span>
                <strong>
                  {money(data.contract_summary.lifetime_committed)}
                </strong>
              </div>
              <div>
                <span>Pago no período</span>
                <strong>{money(data.contract_summary.period_paid)}</strong>
              </div>
              <div>
                <span>Cenários de atenção</span>
                <strong>{data.contract_summary.forecast_risks}</strong>
              </div>
            </div>
            <div className="chart-grid contract-rankings">
              <section>
                <div className="section-heading">
                  <h2>Top 5 contratos com maiores gastos</h2>
                  <select
                    aria-label="Critério do ranking de gastos"
                    value={metric}
                    onChange={(e) => setMetric(e.target.value)}
                  >
                    <option value="most_spent">Realizado</option>
                    <option value="most_paid">Pago</option>
                    <option value="most_committed">Comprometido</option>
                  </select>
                </div>
                <p className="muted">
                  {metricName[metric]} no período selecionado. Clique no
                  contrato para abrir os detalhes.
                </p>
                {top.length ? (
                  <>
                    <div className="chart ranking-chart">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart
                          layout="vertical"
                          data={top.map((r: Row) => ({
                            ...r,
                            spend: Number(r[metricField[metric]]),
                          }))}
                          margin={{ left: 20, right: 20 }}
                        >
                          <CartesianGrid horizontal={false} stroke="#e9eef2" />
                          <XAxis
                            type="number"
                            tickFormatter={shortMoney}
                            tick={{ fontSize: 10 }}
                          />
                          <YAxis
                            type="category"
                            dataKey="code"
                            width={115}
                            tick={{ fontSize: 10 }}
                          />
                          <Tooltip
                            formatter={(v: any) => money(v)}
                            labelFormatter={(_, payload) =>
                              payload?.[0]?.payload.name
                            }
                          />
                          <Bar
                            dataKey="spend"
                            name={metricName[metric]}
                            fill="#168b83"
                            radius={[0, 5, 5, 0]}
                          />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                    <div className="rank-list">
                      {top.map((row: Row, index: number) => (
                        <button
                          className="rank-item"
                          key={row.id}
                          onClick={() => setSelected(row)}
                        >
                          <span className="rank-number">{index + 1}</span>
                          <span>
                            <strong>{row.name}</strong>
                            <small>
                              {row.code} · {row.supplier}
                            </small>
                          </span>
                          <b>{money(row[metricField[metric]])}</b>
                        </button>
                      ))}
                    </div>
                  </>
                ) : (
                  <Empty />
                )}
              </section>
              <section>
                <h2>5 contratos menos utilizados</h2>
                <p className="muted">
                  Por registros explícitos de utilização. Sem registro não
                  significa, necessariamente, ausência de serviço.
                </p>
                <div className="rank-list least-used">
                  {data.contract_rankings.least_used.map(
                    (row: Row, index: number) => (
                      <button
                        className="rank-item"
                        key={row.id}
                        onClick={() => setSelected(row)}
                      >
                        <span className="rank-number amber">{index + 1}</span>
                        <span>
                          <strong>{row.name}</strong>
                          <small>
                            {row.code} · {row.people_count} pessoas registradas
                          </small>
                        </span>
                        <b>
                          {row.usage_count}
                          <small>utilizações</small>
                        </b>
                      </button>
                    ),
                  )}
                  {!data.contract_rankings.least_used.length && <Empty />}
                </div>
                <div className="notice">
                  Lançamentos financeiros e respostas de avaliação não são
                  contados como utilizações. Registre pessoas e atividades no
                  menu Utilização de contratos.
                </div>
              </section>
            </div>
            <section>
              <div className="section-heading">
                <h2>Previsões e possíveis cenários</h2>
                <span className="pill">Projeção linear · baixa confiança</span>
              </div>
              <p className="muted">
                Tendência baseada no realizado acumulado e no tempo observado.
                Não considera mudanças de escopo, sazonalidade ou novos
                aditivos.
              </p>
              <div className="forecast-grid">
                {data.contracts
                  .filter((r: Row) =>
                    [
                      "exhaustion_before_expiry",
                      "limit_reached",
                      "expired",
                    ].includes(r.forecast.scenario),
                  )
                  .slice(0, 6)
                  .map((row: Row) => (
                    <button
                      className="forecast-card"
                      key={row.id}
                      onClick={() => setSelected(row)}
                    >
                      <span className="eyebrow">{row.code}</span>
                      <strong>{row.name}</strong>
                      <p>{row.forecast.message}</p>
                      <small>
                        {remaining(row)} · saldo {percent(row.balance_percent)}
                      </small>
                    </button>
                  ))}
              </div>
              {!data.contracts.some((r: Row) =>
                [
                  "exhaustion_before_expiry",
                  "limit_reached",
                  "expired",
                ].includes(r.forecast.scenario),
              ) && (
                <p className="notice">
                  Nenhum esgotamento antecipado projetado ou contrato vencido no
                  recorte. Veja a previsão individual nos detalhes de cada
                  contrato.
                </p>
              )}
            </section>
            <section className="table-section">
              <div className="section-heading">
                <h2>Visão detalhada dos contratos</h2>
                <input
                  className="search"
                  aria-label="Buscar contratos no dashboard"
                  placeholder="Número, nome ou fornecedor…"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Número / nome</th>
                      <th>Início / ano</th>
                      <th>Final / tempo restante</th>
                      <th>Realizado no período</th>
                      <th>Saldo contratual</th>
                      <th>Pessoas / uso</th>
                      <th>Detalhes</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row: Row) => (
                      <tr key={row.id}>
                        <td>
                          <strong>{row.code}</strong>
                          <span className="cell-secondary">{row.name}</span>
                          <small>
                            {row.supplier} ·{" "}
                            {statusLabels[row.status] ?? row.status}
                          </small>
                        </td>
                        <td>
                          {dateLabel(row.start_date)}
                          <span className="cell-secondary">
                            Ano {row.start_year ?? "não informado"}
                          </span>
                        </td>
                        <td>
                          {dateLabel(row.end_date)}
                          <span
                            className={`cell-secondary ${row.days_remaining !== null && row.days_remaining < 0 ? "negative" : ""}`}
                          >
                            {remaining(row)}
                          </span>
                        </td>
                        <td className="numeric">
                          {money(row.period_realized)}
                        </td>
                        <td>
                          <Balance row={row} />
                        </td>
                        <td>
                          <button
                            className="table-action"
                            onClick={() => setSelected(row)}
                          >
                            {row.people_count} pessoas ↗
                          </button>
                          <span className="cell-secondary">
                            {row.usage_count} utilizações
                          </span>
                        </td>
                        <td>
                          <button
                            className="table-action"
                            onClick={() => setSelected(row)}
                          >
                            Abrir ↗
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {!rows.length && <Empty />}
              </div>
            </section>
            <p className="muted footnote">
              Saldo contratual = valor atualizado menos comprometido acumulado
              até hoje, sem limitar ao ano escolhido. Gastos e utilização seguem
              o período selecionado. Em recortes por fonte, os limites seguem o
              financiamento visível; uso é operacional por contrato/projeto, sem
              rateio monetário.
            </p>
            {selected && (
              <ContractInsight
                row={selected}
                onClose={() => setSelected(null)}
              />
            )}
          </>
        )
      )}
    </>
  );
}

function ContractInsight({ row, onClose }: { row: Row; onClose: () => void }) {
  return (
    <Modal title={`${row.code} · ${row.name}`} onClose={onClose} wide>
      <div className="detail-grid">
        <div>
          <span className="detail-label">Fornecedor</span>
          <strong>{row.supplier}</strong>
        </div>
        <div>
          <span className="detail-label">Situação</span>
          <strong>{statusLabels[row.status] ?? row.status}</strong>
        </div>
        <div>
          <span className="detail-label">Início / ano</span>
          <strong>
            {dateLabel(row.start_date)} · {row.start_year ?? "—"}
          </strong>
        </div>
        <div>
          <span className="detail-label">Final com aditivos aprovados</span>
          <strong>
            {dateLabel(row.end_date)} · {remaining(row)}
          </strong>
        </div>
        <div>
          <span className="detail-label">Valor atualizado</span>
          <strong>{money(row.value)}</strong>
        </div>
        <div>
          <span className="detail-label">
            Saldo para comprometer / percentual
          </span>
          <strong>
            {money(row.balance)} · {percent(row.balance_percent)}
          </strong>
        </div>
        <div>
          <span className="detail-label">Realizado acumulado</span>
          <strong>{money(row.lifetime_realized)}</strong>
        </div>
        <div>
          <span className="detail-label">
            Valor ainda a realizar / percentual
          </span>
          <strong>
            {money(row.remaining_to_realize)} ·{" "}
            {percent(row.remaining_to_realize_percent)}
          </strong>
        </div>
      </div>
      <div className="approval-box">
        <h3>Previsão de consumo</h3>
        <p>{row.forecast.message}</p>
        <div className="detail-grid">
          <div>
            <span className="detail-label">
              Ritmo mensal estimado (30 dias)
            </span>
            <strong>
              {row.forecast.monthly_rate === null
                ? "Sem base suficiente"
                : money(row.forecast.monthly_rate)}
            </strong>
          </div>
          <div>
            <span className="detail-label">
              Possível esgotamento do valor contratual
            </span>
            <strong>{dateLabel(row.forecast.exhaustion_date)}</strong>
          </div>
          <div>
            <span className="detail-label">Realizado projetado no término</span>
            <strong>
              {row.forecast.projected_end_spend === null
                ? "—"
                : money(row.forecast.projected_end_spend)}
            </strong>
          </div>
          <div>
            <span className="detail-label">Excesso projetado no término</span>
            <strong>
              {row.forecast.projected_overrun === null
                ? "—"
                : money(row.forecast.projected_overrun)}
            </strong>
          </div>
        </div>
        <small>
          {row.forecast.method} Confiança baixa. Posição:{" "}
          {dateLabel(row.position_date)}. Não é recomendação automática de
          renovação ou rescisão.
        </small>
      </div>
      <h3>Pessoas que utilizaram o contrato no período</h3>
      {row.people_visible ? (
        row.people.length ? (
          <table>
            <thead>
              <tr>
                <th>Pessoa</th>
                <th>Equipe</th>
                <th>Utilizações</th>
                <th>Último uso</th>
              </tr>
            </thead>
            <tbody>
              {row.people.map((person: any) => (
                <tr key={person.name}>
                  <td>{person.name}</td>
                  <td>{person.team || "—"}</td>
                  <td>{person.uses}</td>
                  <td>{dateLabel(person.last_used)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <Empty text="Sem utilização registrada neste período." />
        )
      ) : (
        <p className="notice">
          Você não tem permissão para consultar nomes dos registros de
          utilização.
        </p>
      )}
    </Modal>
  );
}

export function CategoryDashboard({
  filters,
  setFilters,
  options,
  refresh,
}: Props) {
  const { data, error, loading } = useDashboard(filters, refresh);
  return (
    <>
      <div className="page-intro">
        <p>
          Investimentos e despesas: orçamento, execução e saldo por categoria
          financeira.
        </p>
        <span className="pill">Visão CAPEX / OPEX</span>
      </div>
      <Filters value={filters} onChange={setFilters} options={options} />
      <ErrorBox message={error} />
      {loading ? (
        <Loading />
      ) : (
        data && (
          <>
            <div className="category-grid">
              {data.categories.map((row: any) => (
                <section
                  className={`category-panel ${row.name.toLowerCase()}`}
                  key={row.name}
                >
                  <span className="eyebrow">
                    {row.name === "CAPEX"
                      ? "INVESTIMENTOS"
                      : "DESPESAS OPERACIONAIS"}
                  </span>
                  <h2>{row.name}</h2>
                  <strong className="category-total">
                    {money(row.budget)}
                  </strong>
                  <p className="muted">
                    Orçamento / base autorizada no recorte
                  </p>
                  <div className="category-metrics">
                    <div>
                      <span>Comprometido no período</span>
                      <strong>{money(row.committed)}</strong>
                    </div>
                    <div>
                      <span>Realizado no período</span>
                      <strong>{money(row.realized)}</strong>
                    </div>
                    <div>
                      <span>Pago no período</span>
                      <strong>{money(row.paid)}</strong>
                    </div>
                    <div>
                      <span>Disponível no exercício</span>
                      <strong>{money(row.available)}</strong>
                    </div>
                  </div>
                  <div className="progress-label">
                    <span>Execução financeira no período</span>
                    <strong>{percent(row.execution_percent)}</strong>
                  </div>
                  <div className="progress-track">
                    <i
                      style={{
                        width: `${Math.max(0, Math.min(100, row.execution_percent ?? 0))}%`,
                      }}
                    />
                  </div>
                </section>
              ))}
            </div>
            <div className="chart-grid">
              <section>
                <h2>Orçamento versus realizado por categoria</h2>
                <div className="chart">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={data.categories.map((row: any) => ({
                        ...row,
                        budget: Number(row.budget),
                        realized: Number(row.realized),
                        paid: Number(row.paid),
                      }))}
                    >
                      <CartesianGrid vertical={false} stroke="#e9eef2" />
                      <XAxis dataKey="name" />
                      <YAxis
                        tickFormatter={shortMoney}
                        tick={{ fontSize: 10 }}
                      />
                      <Tooltip formatter={(v: any) => money(v)} />
                      <Legend />
                      <Bar
                        dataKey="budget"
                        name="Orçamento"
                        fill="#c9dce7"
                        radius={[4, 4, 0, 0]}
                      />
                      <Bar
                        dataKey="realized"
                        name="Realizado"
                        fill="#138f83"
                        radius={[4, 4, 0, 0]}
                      />
                      <Bar
                        dataKey="paid"
                        name="Pago"
                        fill="#7e80c8"
                        radius={[4, 4, 0, 0]}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </section>
              <section>
                <h2>Evolução mensal CAPEX × OPEX</h2>
                <div className="chart">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart
                      data={data.category_monthly.map((row: any) => ({
                        ...row,
                        label: monthNames[row.month - 1],
                        CAPEX: Number(row.CAPEX),
                        OPEX: Number(row.OPEX),
                      }))}
                    >
                      <CartesianGrid vertical={false} stroke="#e9eef2" />
                      <XAxis dataKey="label" tick={{ fontSize: 10 }} />
                      <YAxis
                        tickFormatter={shortMoney}
                        tick={{ fontSize: 10 }}
                      />
                      <Tooltip formatter={(v: any) => money(v)} />
                      <Legend />
                      <Area
                        type="monotone"
                        dataKey="CAPEX"
                        stroke="#138f83"
                        fill="#d8eee8"
                      />
                      <Area
                        type="monotone"
                        dataKey="OPEX"
                        stroke="#7e80c8"
                        fill="#efedf9"
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </section>
            </div>
            <section>
              <h2>Distribuição financeira por carteira</h2>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Carteira</th>
                      <th>Orçamento / base</th>
                      <th>Comprometido</th>
                      <th>Realizado</th>
                      <th>Pago</th>
                      <th>Disponível no exercício</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.portfolios.map((row: any) => (
                      <tr key={row.id}>
                        <td>{row.name}</td>
                        {[
                          "budget",
                          "committed",
                          "realized",
                          "paid",
                          "available",
                        ].map((key) => (
                          <td className="numeric" key={key}>
                            {money(row[key])}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
            <p className="muted footnote">
              Esta página acompanha categorias e fontes orçamentárias. Rankings,
              pessoas, vigência e projeções de contratos ficam no Dashboard.{" "}
              {data.policy.explanation}
            </p>
          </>
        )
      )}
    </>
  );
}
