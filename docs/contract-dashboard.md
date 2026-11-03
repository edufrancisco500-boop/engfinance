# Dashboard de contratos e página CAPEX/OPEX — 01/11/2026

As páginas têm funções distintas:

- Dashboard: contratos, gasto por contrato, vigência, pessoas, saldo e cenários de execução.
- CAPEX/OPEX: orçamento, comprometido, realizado, pago e saldo das categorias e fontes orçamentárias.

## Dashboard

Apresenta número/código, nome, fornecedor, status, início/ano de início, término com aditivos aprovados e dias restantes. Os indicadores acumulados do contrato não são reiniciados ao mudar o exercício; as colunas do período e os rankings respeitam os filtros de ano/mês/trimestre.

Top 5 de gastos usa realizado por medições aprovadas, líquido de estornos. A seleção permite comparar também pago e comprometido. Esses valores não são somados como se fossem gastos diferentes.

Os 5 menos utilizados são ordenados pela quantidade de registros explícitos de utilização. Em empate, usa-se o realizado e o número do contrato. Zero registros significa ausência de informação registrada, não comprovação de ausência de uso.

Saldo para comprometer = valor contratual atualizado − comprometido acumulado até hoje. Percentual = saldo / valor atualizado × 100. O cálculo agregado é ponderado pelos valores dos contratos, não uma média simples dos percentuais. Nos detalhes, também há valor e percentual ainda a realizar, calculados em relação às medições.

## Pessoas e utilização

O menu Utilização de contratos registra pessoa, equipe, projeto opcional, data e atividade. Não cria usuários nem concede acesso ao sistema. Data futura é rejeitada; criação e alteração são auditadas. Os registros são limitados ao escopo de gerências e os nomes exigem permissão específica de consulta ao cadastro.

Lançadores de notas e respondentes de avaliações não são inferidos como usuários do contrato. As avaliações individuais continuam restritas.

Foram acrescentados 60 usos fictícios aos contratos DEMO, com pessoas fictícias e frequências diferentes. Os valores financeiros existentes não foram alterados.

## Projeções

Usa-se o realizado acumulado dividido pelos dias desde o início até hoje, incluindo dias sem execução. O ritmo é projetado até o término aprovado; a tela mostra ritmo mensal equivalente a 30 dias, possível data de esgotamento do valor e excesso projetado, quando calculáveis.

A projeção é linear e de baixa confiança. Não considera sazonalidade, mudanças de escopo, interrupções ou aditivos futuros. Contratos vencidos são identificados, contratos suspensos/encerrados/cancelados não recebem projeção futura e contratos sem histórico suficiente não recebem previsão numérica. Nenhuma decisão de renovação ou rescisão é automatizada.

## Verificação

43 testes PostgreSQL e 3 testes React aprovados. Cobertura adicional: top 5 por métricas distintas, deduplicação de pessoas, extensão de prazo aprovada, falta de histórico, vencimento, saldo entre exercícios, permissões dos nomes, criação de utilização e relatório Excel com detalhes estruturados. TypeScript/build e verificações Django/OpenAPI também fazem parte da checagem da entrega.
