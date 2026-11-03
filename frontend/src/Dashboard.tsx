import { useEffect, useState } from "react";
import {
  BarChart,
  Bar,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  AreaChart,
  Area,
  Legend,
  ScatterChart,
  Scatter,
  ZAxis,
} from "recharts";
import { api, money, number } from "./api";
import {
  ErrorBox,
  Filters,
  Loading,
  queryString,
  type Options,
} from "./components";

export function useDashboard(filters: Record<string, string>, refresh: number) {
  const query = queryString(filters);
  const requestKey = `${query}|${refresh}`;
  const [result, setResult] = useState<{
    key: string;
    data: any;
    error: string;
    loading: boolean;
  }>({ key: "", data: null, error: "", loading: true });
  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    setResult({ key: requestKey, data: null, error: "", loading: true });
    api(`/api/dashboard/?${query}`, { signal: controller.signal })
      .then((d) => {
        if (active)
          setResult({ key: requestKey, data: d, error: "", loading: false });
      })
      .catch((e) => {
        if (active && !controller.signal.aborted)
          setResult({
            key: requestKey,
            data: null,
            error: e.message,
            loading: false,
          });
      });
    return () => {
      active = false;
      controller.abort();
    };
  }, [query, requestKey]);
  return result.key === requestKey
    ? result
    : { data: null, error: "", loading: true };
}
const months = [
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
const axisMoney = (value: number) =>
  value >= 1000000
    ? `${number(value / 1000000)} mi`
    : value >= 1000
      ? `${number(value / 1000)} mil`
      : String(value);
const chartStyle = { fontSize: 11, fill: "#748590" };
export function Dashboard({
  filters,
  setFilters,
  options,
  refresh,
  categoryOnly = false,
}: {
  filters: Record<string, string>;
  setFilters: (v: Record<string, string>) => void;
  options: Options;
  refresh: number;
  categoryOnly?: boolean;
}) {
  const { data, error, loading } = useDashboard(filters, refresh);
  return (
    <>
      <div className="page-intro">
        <p>
          {categoryOnly
            ? "Acompanhe investimentos e despesas por categoria financeira."
            : "Visão integrada dos recursos, da execução financeira e do desempenho contratual."}
        </p>
        <span className="live-dot">Dados do sistema</span>
      </div>
      <Filters value={filters} onChange={setFilters} options={options} />
      <ErrorBox message={error} />
      {loading ? (
        <Loading />
      ) : (
        data && (
          <>
            <div className="kpi-grid">
              {[
                [data.budget_label, data.budget, "◎", "teal"],
                ["Comprometido no período", data.committed, "↗", "blue"],
                ["Realizado no período", data.realized, "▥", "violet"],
                ["Pago no período", data.paid, "✓", "amber"],
              ].map(([label, value, icon, color]) => (
                <article className="kpi" key={label}>
                  <span className={`kpi-icon ${color}`}>{icon}</span>
                  <p>{label}</p>
                  <strong>{money(value)}</strong>
                  <small>
                    {filters.year || "Todos os exercícios"} · recorte autorizado
                  </small>
                </article>
              ))}
            </div>
            <div className="metric-strip">
              <div>
                <span title={data.available_label}>
                  Saldo anual para comprometer
                </span>
                <strong>{money(data.available)}</strong>
              </div>
              <div>
                <span>Execução financeira</span>
                <strong>
                  {data.execution === null ? "—" : `${number(data.execution)}%`}
                </strong>
              </div>
              <div>
                <span>Projetos</span>
                <strong>{data.projects_count}</strong>
              </div>
              <div>
                <span>Contratos</span>
                <strong>{data.contracts_count}</strong>
              </div>
              <div>
                <span>Avaliação média</span>
                <strong>
                  {data.evaluations.average === null
                    ? "—"
                    : `${number(data.evaluations.average)} / 5`}
                </strong>
              </div>
            </div>
            <div className="chart-grid">
              <section>
                <div className="section-heading">
                  <h2>Evolução financeira mensal</h2>
                  <span className="muted">Competência</span>
                </div>
                <div className="chart">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart
                      data={data.monthly.map((r: any) => ({
                        ...r,
                        label: months[r.month - 1],
                        realized: Number(r.realized),
                        paid: Number(r.paid),
                      }))}
                    >
                      <defs>
                        <linearGradient
                          id="realizedGradient"
                          x1="0"
                          y1="0"
                          x2="0"
                          y2="1"
                        >
                          <stop
                            offset="0%"
                            stopColor="#0b9188"
                            stopOpacity={0.25}
                          />
                          <stop
                            offset="100%"
                            stopColor="#0b9188"
                            stopOpacity={0}
                          />
                        </linearGradient>
                      </defs>
                      <CartesianGrid vertical={false} stroke="#e9eef2" />
                      <XAxis
                        dataKey="label"
                        tick={chartStyle}
                        axisLine={false}
                        tickLine={false}
                      />
                      <YAxis
                        tickFormatter={axisMoney}
                        tick={chartStyle}
                        axisLine={false}
                        tickLine={false}
                      />
                      <Tooltip formatter={(v: any) => money(v)} />
                      <Legend />
                      <Area
                        name="Realizado"
                        dataKey="realized"
                        stroke="#0b9188"
                        fill="url(#realizedGradient)"
                        strokeWidth={2}
                      />
                      <Area
                        name="Pago"
                        dataKey="paid"
                        stroke="#6b7bd9"
                        fill="transparent"
                        strokeWidth={2}
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </section>
              <section>
                <h2>CAPEX e OPEX</h2>
                <div className="chart">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={data.categories.map((r: any) => ({
                        ...r,
                        budget: Number(r.budget),
                        realized: Number(r.realized),
                      }))}
                    >
                      <CartesianGrid vertical={false} stroke="#e9eef2" />
                      <XAxis
                        dataKey="name"
                        tick={chartStyle}
                        axisLine={false}
                        tickLine={false}
                      />
                      <YAxis
                        tickFormatter={axisMoney}
                        tick={chartStyle}
                        axisLine={false}
                        tickLine={false}
                      />
                      <Tooltip formatter={(v: any) => money(v)} />
                      <Legend />
                      <Bar
                        name="Orçamento"
                        dataKey="budget"
                        fill="#d8e7ed"
                        radius={[5, 5, 0, 0]}
                      />
                      <Bar
                        name="Realizado"
                        dataKey="realized"
                        fill="#0b9188"
                        radius={[5, 5, 0, 0]}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </section>
            </div>
            <div className="chart-grid">
              <section>
                <h2>Distribuição por carteira</h2>
                <div className="chart">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={data.portfolios.map((r: any) => ({
                        ...r,
                        budget: Number(r.budget),
                        realized: Number(r.realized),
                      }))}
                    >
                      <CartesianGrid vertical={false} stroke="#e9eef2" />
                      <XAxis
                        dataKey="code"
                        tick={{ ...chartStyle, fontSize: 9 }}
                        axisLine={false}
                        tickLine={false}
                      />
                      <YAxis
                        tickFormatter={axisMoney}
                        tick={chartStyle}
                        axisLine={false}
                        tickLine={false}
                      />
                      <Tooltip
                        labelFormatter={(_, payload) =>
                          payload?.[0]?.payload.name
                        }
                        formatter={(v: any) => money(v)}
                      />
                      <Legend />
                      <Bar
                        name="Orçamento"
                        dataKey="budget"
                        fill="#d8e7ed"
                        radius={[4, 4, 0, 0]}
                      />
                      <Bar
                        name="Realizado"
                        dataKey="realized"
                        fill="#137f85"
                        radius={[4, 4, 0, 0]}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </section>
              <section>
                <h2>Risco financeiro × desempenho</h2>
                <p className="muted">
                  Consumo do contrato e nota média. Classificação configurada no
                  backend.
                </p>
                <div className="chart">
                  <ResponsiveContainer width="100%" height="100%">
                    <ScatterChart>
                      <CartesianGrid stroke="#e9eef2" />
                      <XAxis
                        type="number"
                        dataKey="consumption"
                        name="Consumo"
                        unit="%"
                        domain={[0, 100]}
                        tick={chartStyle}
                      />
                      <YAxis
                        type="number"
                        dataKey="rating"
                        name="Avaliação"
                        domain={[0, 5]}
                        tick={chartStyle}
                      />
                      <ZAxis range={[100, 180]} />
                      <Tooltip
                        cursor={{ strokeDasharray: "3 3" }}
                        content={({ active, payload }) =>
                          active && payload?.length ? (
                            <div className="chart-tooltip">
                              <strong>{payload[0].payload.name}</strong>
                              <p>
                                Consumo:{" "}
                                {number(payload[0].payload.consumption)}%
                              </p>
                              <p>
                                Avaliação: {number(payload[0].payload.rating)}/5
                              </p>
                            </div>
                          ) : null
                        }
                      />
                      <Scatter
                        data={data.contracts
                          .filter((r: any) => r.rating !== null)
                          .map((r: any) => ({
                            ...r,
                            consumption: r.consumption_percent,
                          }))}
                        fill="#157f87"
                      />
                    </ScatterChart>
                  </ResponsiveContainer>
                </div>
              </section>
            </div>
            <div className="chart-grid">
              <section>
                <div className="section-heading">
                  <h2>Contratos que exigem atenção</h2>
                  <span className="badge">{data.alerts.length}</span>
                </div>
                {data.alerts.length ? (
                  data.alerts.map((a: any) => (
                    <div className="alert-row" key={a.contract}>
                      <span className={`alert-dot ${a.severity}`} />
                      <div>
                        <strong>{a.name}</strong>
                        <p>{a.reasons.join(" · ")}</p>
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="muted">Nenhum alerta no recorte selecionado.</p>
                )}
              </section>
              <section>
                <h2>Avanço físico e financeiro</h2>
                <div className="progress-list">
                  {data.projects.slice(0, 6).map((p: any) => (
                    <div key={p.id}>
                      <div className="progress-label">
                        <strong>{p.name}</strong>
                        <span>
                          {number(p.physical)}% físico ·{" "}
                          {p.financial === null
                            ? "—"
                            : number(p.financial) + "% financeiro"}
                        </span>
                      </div>
                      <div className="progress-track">
                        <i
                          style={{
                            width: `${Math.min(100, Number(p.physical))}%`,
                          }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            </div>
            <section>
              <h2>Posição por carteira</h2>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Carteira</th>
                      <th>Orçamento / base</th>
                      <th>Alocado</th>
                      <th>Comprometido</th>
                      <th>Realizado</th>
                      <th>Pago</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.portfolios.map((p: any) => (
                      <tr key={p.id}>
                        <td>{p.name}</td>
                        {[
                          "budget",
                          "allocated",
                          "committed",
                          "realized",
                          "paid",
                        ].map((k) => (
                          <td key={k} className="numeric">
                            {money(p[k])}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
            <p className="muted footnote">
              {data.policy.explanation} Projeção ilustrativa do próximo mês:{" "}
              {money(data.forecast.next_month)}. {data.forecast.method}.
            </p>
          </>
        )
      )}
    </>
  );
}
