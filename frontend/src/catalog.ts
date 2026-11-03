export type Field = {
  key: string;
  label: string;
  type?: string;
  source?: string;
  options?: Record<string, string>;
  optional?: boolean;
  default?: string;
};
export type Config = {
  title: string;
  subtitle: string;
  fields: Field[];
  columns: string[];
  app?: string;
  model?: string;
  financial?: boolean;
};
const basic: Field[] = [
  { key: "code", label: "Código" },
  { key: "name", label: "Nome" },
  { key: "description", label: "Descrição", type: "textarea", optional: true },
];
const department: Field = {
  key: "department",
  label: "Gerência",
  source: "departments",
};
const reason: Field = {
  key: "reason",
  label: "Justificativa",
  type: "textarea",
};
const amount: Field = { key: "amount", label: "Valor (R$)", type: "money" };
const contract: Field = {
  key: "contract",
  label: "Contrato",
  source: "contracts",
};
export const catalog: Record<string, Config> = {
  "contract-usage": {
    title: "Utilização de contratos",
    subtitle:
      "Registre quem utilizou o contrato, quando e para qual atividade. Esses registros alimentam o ranking de utilização.",
    fields: [
      contract,
      { key: "person_name", label: "Pessoa / colaborador" },
      { key: "team", label: "Equipe / área", optional: true },
      { key: "project", label: "Projeto", source: "projects", optional: true },
      {
        key: "date",
        label: "Data de utilização",
        type: "date",
        default: new Date().toISOString().slice(0, 10),
      },
      {
        key: "purpose",
        label: "Atividade / serviço utilizado",
        type: "textarea",
      },
    ],
    columns: ["contract", "person_name", "team", "date", "purpose"],
    app: "finance",
    model: "contractusage",
  },
  coordinations: {
    title: "Coordenações",
    subtitle: "Organização dos projetos dentro de cada gerência.",
    fields: [...basic, department],
    columns: ["code", "name", "department", "active"],
    model: "coordination",
  },
  periods: {
    title: "Competências",
    subtitle:
      "Encerramento e reabertura formal de períodos financeiros. A regra é global neste ambiente.",
    fields: [
      {
        key: "year",
        label: "Ano",
        type: "number",
        default: String(new Date().getFullYear()),
      },
      { key: "month", label: "Mês", type: "number" },
      {
        key: "closed",
        label: "Operação",
        options: { true: "Encerrar competência", false: "Reabrir competência" },
      },
      reason,
    ],
    columns: ["year", "month", "closed", "reason", "status"],
    app: "finance",
    model: "periodchange",
    financial: true,
  },
  departments: {
    title: "Gerências",
    subtitle: "Estrutura organizacional e escopos de acesso.",
    fields: basic,
    columns: ["code", "name", "active"],
    model: "department",
  },
  portfolios: {
    title: "Carteiras de investimentos",
    subtitle: "Fontes de financiamento para os projetos de engenharia.",
    fields: [
      ...basic,
      department,
      {
        key: "responsible",
        label: "Responsável pela carteira",
        optional: true,
      },
    ],
    columns: ["code", "name", "department", "active"],
    model: "portfolio",
  },
  projects: {
    title: "Projetos de engenharia",
    subtitle: "Acompanhe responsáveis, cronograma e avanço físico.",
    fields: [
      ...basic,
      department,
      {
        key: "coordination",
        label: "Coordenação",
        source: "coordinations",
        optional: true,
      },
      { key: "internal_order", label: "Ordem interna", optional: true },
      { key: "pep_element", label: "Elemento PEP", optional: true },
      {
        key: "category",
        label: "Classificação",
        options: { CAPEX: "CAPEX", OPEX: "OPEX", MIXED: "Misto" },
        default: "MIXED",
      },
      {
        key: "status",
        label: "Status do projeto",
        options: {
          PLANNED: "Planejado",
          ACTIVE: "Em execução",
          PAUSED: "Pausado",
          COMPLETED: "Concluído",
          CANCELLED: "Cancelado",
        },
        default: "PLANNED",
      },
      { key: "responsible", label: "Responsável", optional: true },
      { key: "start_date", label: "Início", type: "date", optional: true },
      {
        key: "end_date",
        label: "Conclusão prevista",
        type: "date",
        optional: true,
      },
      {
        key: "physical_progress",
        label: "Avanço físico (%)",
        type: "number",
        default: "0",
      },
    ],
    columns: ["code", "name", "responsible", "physical_progress", "status"],
    model: "project",
  },
  suppliers: {
    title: "Fornecedores",
    subtitle: "Cadastro compartilhado de fornecedores.",
    fields: [...basic, { key: "tax_id", label: "CNPJ (14 dígitos)" }],
    columns: ["code", "name", "tax_id", "active"],
    model: "supplier",
  },
  "cost-centers": {
    title: "Centros de custo",
    subtitle: "Identificação organizacional das parcelas financeiras.",
    fields: [...basic, department],
    columns: ["code", "name", "department", "active"],
    model: "costcenter",
  },
  contracts: {
    title: "Contratos",
    subtitle: "Escopo, vigência, financiamento e histórico contratual.",
    fields: [
      ...basic,
      department,
      {
        key: "status",
        label: "Status contratual",
        options: {
          DRAFT: "Em preparação",
          ACTIVE: "Vigente",
          SUSPENDED: "Suspenso",
          CLOSED: "Encerrado",
          CANCELLED: "Cancelado",
        },
        default: "DRAFT",
      },
      { key: "supplier", label: "Fornecedor", source: "suppliers" },
      {
        key: "original_value",
        label: "Valor original (R$)",
        type: "money",
        default: "0",
      },
      { key: "manager", label: "Gestor", optional: true },
      { key: "inspector", label: "Fiscal", optional: true },
      { key: "start_date", label: "Início", type: "date", optional: true },
      { key: "end_date", label: "Término", type: "date", optional: true },
    ],
    columns: [
      "code",
      "name",
      "supplier",
      "original_value",
      "end_date",
      "active",
    ],
    model: "contract",
  },
  budgets: {
    title: "Orçamentos",
    subtitle: "Autorização de gasto por carteira, exercício e categoria.",
    fields: [
      { key: "portfolio", label: "Carteira", source: "portfolios" },
      {
        key: "year",
        label: "Exercício",
        type: "number",
        default: String(new Date().getFullYear()),
      },
      {
        key: "category",
        label: "Categoria",
        options: { CAPEX: "CAPEX", OPEX: "OPEX" },
      },
      amount,
      reason,
    ],
    columns: ["portfolio", "year", "category", "amount", "balance", "status"],
    app: "finance",
    model: "budget",
    financial: true,
  },
  "budget-revisions": {
    title: "Revisões orçamentárias",
    subtitle: "Aumentos e reduções preservam o histórico aprovado.",
    fields: [
      { key: "budget", label: "Orçamento", source: "budgets" },
      amount,
      reason,
    ],
    columns: ["budget", "amount", "reason", "status"],
    app: "finance",
    model: "budgetrevision",
    financial: true,
  },
  allocations: {
    title: "Alocações",
    subtitle: "Distribua os recursos aos projetos sem ultrapassar o orçamento.",
    fields: [
      { key: "budget", label: "Orçamento", source: "budgets" },
      { key: "project", label: "Projeto", source: "projects", optional: true },
      {
        key: "cost_center",
        label: "Centro de custo",
        source: "cost-centers",
        optional: true,
      },
      amount,
      reason,
    ],
    columns: ["budget", "project", "amount", "balance", "status"],
    app: "finance",
    model: "allocation",
    financial: true,
  },
  transfers: {
    title: "Realocações",
    subtitle:
      "Transferências entre alocações do mesmo orçamento, com aprovação.",
    fields: [
      { key: "source", label: "Alocação de origem", source: "allocations" },
      { key: "target", label: "Alocação de destino", source: "allocations" },
      amount,
      reason,
    ],
    columns: ["source", "target", "amount", "reason", "status"],
    app: "finance",
    model: "transfer",
    financial: true,
  },
  fundings: {
    title: "Rateios de contratos",
    subtitle:
      "Versões de financiamento por várias carteiras. O rateio não cria compromisso automaticamente.",
    fields: [contract, amount, reason],
    columns: ["contract", "version", "amount", "status"],
    app: "finance",
    model: "funding",
    financial: true,
  },
  amendments: {
    title: "Aditivos contratuais",
    subtitle: "Alterações de valor e prazo sujeitas à aprovação.",
    fields: [
      contract,
      amount,
      { key: "end_date", label: "Novo término", type: "date", optional: true },
      reason,
    ],
    columns: ["contract", "amount", "end_date", "reason", "status"],
    app: "finance",
    model: "amendment",
    financial: true,
  },
  documents: {
    title: "Movimentações financeiras",
    subtitle:
      "Compromissos, medições, notas fiscais, pagamentos e estornos rastreáveis.",
    fields: [
      contract,
      {
        key: "kind",
        label: "Tipo",
        options: {
          COMMITMENT: "Compromisso",
          MEASUREMENT: "Medição",
          INVOICE: "Nota fiscal",
          PAYMENT: "Pagamento",
        },
      },
      { key: "reference", label: "Documento de referência" },
      {
        key: "date",
        label: "Data de competência",
        type: "date",
        default: new Date().toISOString().slice(0, 10),
      },
      amount,
      {
        key: "funding",
        label: "Rateio contratual sugerido",
        source: "fundings",
        optional: true,
      },
      reason,
    ],
    columns: ["reference", "kind", "contract", "date", "amount", "status"],
    app: "finance",
    model: "document",
    financial: true,
  },
  "action-plans": {
    title: "Planos de ação",
    subtitle:
      "Acompanhe ações de melhoria sem automatizar decisões contratuais.",
    fields: [
      contract,
      { key: "title", label: "Ação" },
      {
        key: "description",
        label: "Descrição",
        type: "textarea",
        optional: true,
      },
      { key: "responsible", label: "Responsável" },
      { key: "due_date", label: "Prazo", type: "date" },
      {
        key: "status",
        label: "Situação",
        options: {
          OPEN: "Aberto",
          PROGRESS: "Em andamento",
          DONE: "Concluído",
        },
      },
    ],
    columns: ["title", "contract", "responsible", "due_date", "status"],
    app: "evaluations",
    model: "actionplan",
  },
};
export const columnLabels: Record<string, string> = {
  person_name: "Pessoa / colaborador",
  team: "Equipe / área",
  purpose: "Atividade / serviço",
  code: "Código",
  name: "Nome",
  active: "Situação",
  department: "Gerência",
  supplier: "Fornecedor",
  tax_id: "CNPJ",
  original_value: "Valor original",
  end_date: "Término",
  start_date: "Início",
  physical_progress: "Avanço físico",
  responsible: "Responsável",
  portfolio: "Carteira",
  year: "Exercício",
  category: "Categoria",
  amount: "Valor",
  balance: "Saldo disponível",
  status: "Situação",
  budget: "Orçamento",
  project: "Projeto",
  reason: "Justificativa",
  contract: "Contrato",
  version: "Versão",
  kind: "Tipo",
  reference: "Referência",
  date: "Data",
  source: "Origem",
  target: "Destino",
  title: "Ação",
  due_date: "Prazo",
};
