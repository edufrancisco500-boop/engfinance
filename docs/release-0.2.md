# Entrega local 0.2 — 31/10/2026

## Disponível

Dashboard com filtros e gráficos; carteiras, projetos, contratos, gerências, coordenações e centros de custo; orçamento e revisão; alocações e realocações; aditivos; rateios versionados entre carteiras; compromissos, medições, notas e pagamentos; estornos; competências; avaliações e planos de ação; anexos privados; exportação e importação controlada; resumo gerencial local; permissões, auditoria e configuração de alertas.

A demonstração usa 10 carteiras, 10 projetos, 10 contratos, 10 fornecedores, 10 gerências, 10 coordenações e 10 centros de custo; 10 orçamentos, revisões, alocações, aditivos e rateios; 40 documentos financeiros; 10 convites com 5 avaliações já submetidas; 10 planos e 10 anexos TXT fictícios.

As contas e os dados anteriores foram preservados. Um backup PostgreSQL em formato custom foi gerado em `.local/backup-before-modules-*.dump` antes das migrations.

## Verificado

- 21 testes aprovados no PostgreSQL real, incluindo concorrência.
- Isolamento por gerência e por fontes do rateio, idempotência, imutabilidade da API, estorno, limites de orçamento, versões de rateio, fechamento/reabertura, confidencialidade das avaliações, Não sei avaliar, importação e limitação de login.
- TypeScript e build Vite/Recharts aprovados; assets dos gráficos separados.
- Ruff e formatação Prettier aprovados.
- Django check sem problemas e nenhuma migration pendente.
- OpenAPI gerado e validado com fail-on-warn, sem avisos.
- Dependências Python sem conflitos; configuração Compose válida.
- Listagens de todos os módulos, metadados, dashboard, filtros, resumo e relatório XLSX exercitados com a conta local via cliente de integração Django.

## Limites

Não houve validação visual por automação de navegador; a autorização de abertura automática do endereço local havia sido negada e não foi contornada. Não houve implantação de produção, teste de carga, conexão com sistemas corporativos ou teste completo dos containers após o reinício exigido pelo Windows.

Entra ID/MFA, IA externa e integrações corporativas precisam de credenciais/provedor/autorização. Retenções, adiantamentos, impostos, transferências entre carteiras/exercícios e alçadas oficiais dependem da política empresarial. O resumo atual é determinístico por regras e não usa um modelo de linguagem.

Esta é uma entrega funcional para teste e evolução. A conclusão da homologação corporativa depende dessas definições e da revisão da TI. Consulte architecture.md, business-rules.md e user-guide.md.
