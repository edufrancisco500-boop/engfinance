import {
  StrictMode,
  useCallback,
  useEffect,
  useState,
  type FormEvent,
} from "react";
import { createRoot } from "react-dom/client";
import { all, api } from "./api";
import { catalog } from "./catalog";
import { ErrorBox, Loading, type Options } from "./components";
import { Records } from "./Records";
import { ContractDashboard, CategoryDashboard } from "./ContractDashboard";
import { Administration, Evaluations, Insights, Reports } from "./OtherPages";
import "./style.css";
import "./app.css";

const nav = [
  ["dashboard", "◫", "Dashboard"],
  ["portfolios", "▣", "Carteiras"],
  ["projects", "◇", "Projetos"],
  ["capex", "▥", "CAPEX e OPEX"],
  ["contracts", "▤", "Contratos"],
  ["contract-usage", "♙", "Utilização de contratos"],
  ["finance", "⇄", "Movimentações"],
  ["evaluations", "☆", "Avaliações"],
  ["action-plans", "☑", "Planos de ação"],
  ["reports", "▧", "Relatórios"],
  ["ai", "✧", "Inteligência artificial"],
  ["administration", "⚙", "Administração"],
];
const financeTabs = [
  "documents",
  "budgets",
  "budget-revisions",
  "allocations",
  "fundings",
  "transfers",
  "amendments",
  "periods",
];
function App() {
  const [user, setUser] = useState<string | null>(null),
    [ready, setReady] = useState(false),
    [metadata, setMetadata] = useState<any>(null),
    [options, setOptions] = useState<Options>({});
  const [page, setPage] = useState("dashboard"),
    [subpage, setSubpage] = useState("documents"),
    [refresh, setRefresh] = useState(0),
    [error, setError] = useState(""),
    [loginBusy, setLoginBusy] = useState(false),
    [menu, setMenu] = useState(false);
  const [filters, setFilters] = useState<Record<string, string>>({
    year: String(new Date().getFullYear()),
  });
  const changed = useCallback(() => setRefresh((v) => v + 1), []);
  useEffect(() => {
    api("/api/session/")
      .then((s) => setUser(s.username))
      .catch((e) => setError(e.message))
      .finally(() => setReady(true));
  }, []);
  useEffect(() => {
    if (!user) {
      setMetadata(null);
      setOptions({});
      return;
    }
    let active = true;
    api("/api/metadata/")
      .then((m) => {
        if (active) {
          setMetadata(m);
          if (!m.superuser && !m.permissions.includes("finance.view_analytics"))
            setPage("evaluations");
        }
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [user, refresh]);
  useEffect(() => {
    if (!user || !metadata) return;
    let active = true;
    const resources = [
      "departments",
      "portfolios",
      "projects",
      "suppliers",
      "contracts",
      "cost-centers",
      "coordinations",
      "budgets",
      "allocations",
      "fundings",
      "documents",
      "amendments",
      "action-plans",
      "attachments",
    ];
    Promise.all(
      resources.map(async (resource) => {
        try {
          return [resource, await all(resource)] as const;
        } catch {
          return [resource, []] as const;
        }
      }),
    ).then((entries) => {
      if (active) setOptions(Object.fromEntries(entries));
    });
    return () => {
      active = false;
    };
  }, [user, metadata]);
  async function login(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError("");
    setLoginBusy(true);
    try {
      const result = await api("/api/login/", {
        method: "POST",
        body: new FormData(e.currentTarget),
      });
      setUser(result.username);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoginBusy(false);
    }
  }
  async function logout() {
    try {
      await api("/api/logout/", { method: "POST" });
      setUser(null);
      setError("");
    } catch (e) {
      setError((e as Error).message);
    }
  }
  if (!ready) return <Loading />;
  if (!user)
    return (
      <div className="login-shell">
        <div className="login-story">
          <div className="brand">EF</div>
          <span className="eyebrow">ENGENHARIA DE PROJETOS</span>
          <h1>
            Recursos conectados.
            <br />
            Decisões mais claras.
          </h1>
          <p>
            Carteiras, projetos, contratos e desempenho em uma visão integrada.
          </p>
          <div className="login-art">
            <i />
            <i />
            <i />
            <i />
            <i />
            <i />
          </div>
          <small>EngFinance · Plataforma de gestão financeira</small>
        </div>
        <main className="login">
          <span className="eyebrow">BEM-VINDO AO ENGFINANCE</span>
          <h1>Acesse sua conta</h1>
          <p>Entre para acompanhar seus projetos.</p>
          <ErrorBox message={error} />
          <form onSubmit={login}>
            <label>
              Usuário ou e-mail
              <input name="username" autoComplete="username" required />
            </label>
            <label>
              Senha
              <input
                name="password"
                type="password"
                autoComplete="current-password"
                required
              />
            </label>
            <button disabled={loginBusy}>
              {loginBusy ? "Entrando…" : "Entrar →"}
            </button>
          </form>
          <small>Ambiente local · Dados fictícios de demonstração</small>
        </main>
      </div>
    );
  if (!metadata)
    return (
      <>
        <ErrorBox message={error} />
        <Loading />
      </>
    );
  const title = nav.find((n) => n[0] === page)?.[2] ?? "EngFinance";
  const resource = page === "finance" ? subpage : page;
  const referencePage = [
    "departments",
    "suppliers",
    "cost-centers",
    "coordinations",
  ].includes(page);
  const props = {
    options,
    refresh,
    permissions: metadata.permissions,
    superuser: metadata.superuser,
    onChange: changed,
  };
  const canAnalytics =
    metadata.superuser ||
    metadata.permissions.includes("finance.view_analytics");
  return (
    <div className={`layout ${menu ? "menu-open" : ""}`}>
      <aside>
        <div className="sidebar-brand">
          <div className="brand">EF</div>
          <div>
            <h2>EngFinance</h2>
            <small>Engenharia de Projetos</small>
          </div>
        </div>
        <p className="nav-caption">WORKSPACE</p>
        <nav aria-label="Navegação principal">
          {nav
            .filter(
              (n) =>
                canAnalytics ||
                !["dashboard", "capex", "reports", "ai"].includes(n[0]),
            )
            .map(([key, icon, label]) => (
              <button
                key={key}
                aria-current={page === key ? "page" : undefined}
                onClick={() => {
                  setPage(key);
                  setMenu(false);
                  setError("");
                }}
              >
                <span>{icon}</span>
                {label}
              </button>
            ))}
        </nav>
        <p className="nav-caption">CADASTROS DE APOIO</p>
        <nav aria-label="Cadastros de apoio">
          {["departments", "suppliers", "cost-centers", "coordinations"].map(
            (key) => (
              <button
                key={key}
                aria-current={page === key ? "page" : undefined}
                onClick={() => {
                  setPage(key);
                  setMenu(false);
                }}
              >
                <span>⌑</span>
                {catalog[key].title}
              </button>
            ),
          )}
        </nav>
        <div className="sidebar-footer">
          <div className="avatar">{user.slice(0, 2).toUpperCase()}</div>
          <div>
            <strong>{user.split("@")[0]}</strong>
            <small>{metadata.groups[0] ?? "Colaborador"}</small>
          </div>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <button
            className="icon-button mobile-menu"
            aria-label="Abrir menu"
            onClick={() => setMenu(!menu)}
          >
            ☰
          </button>
          <span>
            Engenharia <b>/</b> {referencePage ? catalog[page].title : title}
          </span>
          <div>
            <span className="environment">
              <i /> Ambiente de teste
            </span>
            <button className="secondary small" onClick={changed}>
              ↻ Atualizar
            </button>
            <button className="secondary small" onClick={logout}>
              Sair
            </button>
          </div>
        </header>
        <main>
          <div className="page-heading">
            <div>
              <p className="eyebrow">ENGFINANCE · GESTÃO INTEGRADA</p>
              <h1>{referencePage ? catalog[page].title : title}</h1>
            </div>
            <span className="today">
              {new Date().toLocaleDateString("pt-BR", {
                day: "numeric",
                month: "long",
                year: "numeric",
              })}
            </span>
          </div>
          {metadata.policy?.demo && (
            <div className="demo-banner">
              <span>◈</span>
              <div>
                <strong>Dados fictícios · Modo demonstração</strong>
                <p>
                  Política financeira provisória. Valide as regras corporativas
                  antes de usar dados reais.
                </p>
              </div>
            </div>
          )}
          <ErrorBox message={error} />
          {page === "dashboard" ? (
            <ContractDashboard
              {...props}
              filters={filters}
              setFilters={setFilters}
              onUsage={() => setPage("contract-usage")}
            />
          ) : page === "capex" ? (
            <CategoryDashboard
              {...props}
              filters={filters}
              setFilters={setFilters}
            />
          ) : page === "evaluations" ? (
            <Evaluations
              {...props}
              metadata={metadata}
              filters={filters}
              setFilters={setFilters}
            />
          ) : page === "reports" ? (
            <Reports
              options={options}
              metadata={metadata}
              filters={filters}
              setFilters={setFilters}
            />
          ) : page === "ai" ? (
            <Insights
              options={options}
              filters={filters}
              setFilters={setFilters}
            />
          ) : page === "administration" ? (
            <Administration metadata={metadata} refresh={refresh} />
          ) : (
            <>
              {page === "finance" && (
                <div className="tabs finance-tabs">
                  {financeTabs.map((key) => (
                    <button
                      className={subpage === key ? "active" : ""}
                      key={key}
                      onClick={() => setSubpage(key)}
                    >
                      {catalog[key].title}
                    </button>
                  ))}
                </div>
              )}
              <Records key={resource} resource={resource} {...props} />
            </>
          )}
        </main>
        <div className="workspace-footer">
          <span>EngFinance · Engenharia de Projetos</span>
          <span>Dados por escopo · Aprovações auditadas</span>
        </div>
      </div>
    </div>
  );
}
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
