# Regras do demonstrador financeiro

As regras abaixo são implementadas para testar o fluxo. Não substituem as decisões pendentes da liderança. A política demonstrativa é proibida para gravações financeiras quando DEBUG=false. Sem política aprovada, operações reais ficam bloqueadas.

## Unidades e distribuição

Valores são Decimal/NUMERIC com duas casas, enviados na API como strings. Projetos podem ser mistos; cada fonte orçamentária tem categoria e exercício definidos. Uma parcela identifica alocação, projeto e centro de custo quando aplicáveis, e a carteira por meio do orçamento. Não existe carteira exclusiva em Contrato.

O rateio contratual nesta política é planejamento, sem reserva automática. Seus itens devem totalizar a base e respeitar o valor do contrato e os recursos disponíveis frente a compromissos já aprovados. Para torná-lo reserva orçamentária, a liderança deverá definir a semântica e aprovar a alteração antes do uso real.

Rateios por percentual somam 100%. Valores resultantes usam o método do maior resto para distribuir centavos; empates seguem o ID da alocação. Rateios por valor devem somar exatamente o documento. A API rejeita fontes repetidas e valores não positivos.

## Etapas e cálculos

- Orçamento vigente: orçamento aprovado mais revisões aprovadas.
- Alocação vigente: valor aprovado mais realocações recebidas menos realocações enviadas.
- Comprometido: parcelas de compromissos aprovados menos estornos aprovados.
- Realizado: parcelas de medições aprovadas menos estornos aprovados.
- Faturado: parcelas de notas fiscais aprovadas menos estornos aprovados.
- Pago: parcelas de pagamentos aprovados menos estornos aprovados.
- Saldo da carteira para distribuir: orçamento vigente menos alocações aprovadas.
- Saldo da alocação para comprometer: alocação vigente menos compromissos líquidos.
- Saldo do contrato: valor original mais aditivos aprovados menos compromissos líquidos.

Comprometido inclui a parcela já realizada. Nunca se soma comprometido + realizado + faturado + pago como consumo total. Cabeçalhos, rateios planejados e vínculos de conciliação também não são somados à execução.

Cada documento pode ter distribuição diferente do contrato, com justificativa e aprovação. Medições, notas e pagamentos devem consumir parcelas aprovadas da etapa anterior, nas mesmas fontes e com saldo suficiente. A relação admite várias origens e liquidações parciais. Trocar fonte entre etapas sem saldo compatível exige processo de reclassificação ainda pendente; não é liberado como exceção silenciosa.

## Aprovações e estornos

Fluxo: rascunho → em aprovação → aprovado ou rejeitado. Operações aprovadas não têm PATCH ou DELETE na API. Documentos são corrigidos por novo estorno, preservando original, parcelas e auditoria. Um pedido de estorno ainda não aprovado não reduz saldo nem libera recursos.

Estorne pagamentos antes de notas, notas antes de medições e medições antes de compromissos, quando houver consumo dependente. Um estorno rejeitado pode ser solicitado novamente com nova justificativa auditada.

Em demonstração e DEBUG=true, a mesma pessoa pode solicitar e aprovar para facilitar o teste. Fora disso, autor e aprovador devem ser distintos, além de possuir permissão de aprovação e acesso a todas as fontes. Alçadas por valor e aprovações em vários níveis ainda dependem de política formal.

Revisões não podem reduzir o orçamento abaixo das alocações vigentes. Realocações implementadas são entre alocações do mesmo orçamento e não podem consumir compromisso existente. Aditivos não criam compromisso automaticamente.

Encerramento e reabertura de competência são operações aprovadas, globais neste ambiente e limitadas ao administrador financeiro. Competência encerrada bloqueia aprovação de novos documentos e estornos naquela data.

## Filtros e indicadores

Orçamentos e saldos são posições por exercício. Mês e trimestre recortam os fluxos, mas não restauram o saldo consumido por compromissos de outros meses. O indicador de saldo anual explicita essa distinção.

Ao filtrar um contrato ou projeto, a base rotulada como “Alocações das fontes relacionadas” corresponde às alocações selecionadas, que podem financiar outros contratos. Não é uma nova autorização exclusiva para o contrato. O detalhamento do contrato e o rateio identificam seus limites próprios.

CAPEX/OPEX e classificação de risco usam dados do backend. O alerta de saldo reduzido, a nota insatisfatória e a antecedência do vencimento podem ser alterados em Administração, com justificativa e auditoria. Nenhum alerta determina renovação/rescisão.

A projeção é linear e ilustrativa: média do realizado pelo número de meses do período selecionado. Não cria orçamento ou obrigação financeira.

## Avaliações e dados pessoais

Convites definem o denominador da participação e fixam os critérios/versionamentos da avaliação. Uma resposta por convite; todos os critérios devem ser preenchidos, inclusive com Não sei avaliar (NULL). NULL fica fora das médias. Pesos são iguais nesta versão demonstrativa.

Autor vê suas próprias respostas; acesso individual de terceiros exige permissão específica, que não é concedida automaticamente ao grupo Administrador. Agregados exigem três respostas fora da demonstração; a demonstração permite uma resposta para testar as telas.

## Limites técnicos e corporativos

As gravações financeiras usam transações atômicas e bloqueio da política como mutex. Isso garante serialização nesta versão e evita aprovações concorrentes consumindo o mesmo saldo. É uma escolha conservadora para o piloto; alto volume exige particionar o bloqueio por fonte e revisar desempenho. O dashboard usa o mesmo bloqueio durante o snapshot financeiro.

Documentos possuem chave de idempotência e fingerprint do conteúdo; repetir a mesma chave com dados diferentes é rejeitado. Referências repetidas por contrato/tipo também são bloqueadas.

Ainda exigem definição/homologação: múltiplas empresas/moedas, reservas de rateio, regimes contábeis, impostos, retenções, adiantamentos, transferências entre carteiras/exercícios, alçadas, importação financeira, anonimato, retenção de dados, recuperação testada em infraestrutura corporativa e requisitos de disponibilidade.

Os testes automatizados verificam cenários relevantes, não constituem certificação contábil, legal ou de segurança.
