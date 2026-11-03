# Usar e evoluir o EngFinance

O [Dashboard de contratos](contract-dashboard.md) agora contém rankings, vigência, percentual de saldo, pessoas registradas e projeções. CAPEX/OPEX tem uma visão própria de categorias. Use o menu Utilização de contratos para registrar pessoas e atividades.

## Explorar a demonstração

1. Entre com sua conta e abra Dashboard. Use o ano atual para visualizar os cenários fictícios.
2. Consulte Carteiras, Projetos e Contratos. Em Contratos, use Abrir para ver aditivos, rateios, movimentações, desempenho e anexos.
3. Em Movimentações, alterne as abas Orçamentos, Revisões, Alocações, Rateios, Realocações, Aditivos e Competências.
4. Crie um rascunho, abra seus detalhes, envie para aprovação e aprove. Na demonstração, sua conta administrativa pode executar as duas etapas.
5. Para corrigir um documento aprovado, informe o motivo e solicite estorno. O pedido precisa ser enviado e aprovado como outra operação.
6. Em Avaliações, responda os convites ainda abertos. Cinco dos dez cenários já têm resposta para demonstrar os indicadores.
7. Em Relatórios, exporte Excel/CSV. Para importar cadastros, valide o arquivo, confira a prévia e depois confirme.
8. Em Inteligência artificial, gere um resumo local. A tela informa que ainda não usa modelo externo.
9. Em Administração, consulte permissões, auditoria e ajuste os limites dos alertas.

## Ordem de criação financeira

Carteira → orçamento aprovado → alocação aprovada → contrato/aditivos → rateio aprovado → compromisso → medição → nota fiscal → pagamento.

Medição, nota e pagamento precisam selecionar uma ou mais origens da etapa anterior. O rateio pode ser manual ou sugerido pelo contrato. A mesma fonte precisa existir com saldo suficiente nas origens escolhidas.

## Arquivos principais

- `backend/apps/registry`: estrutura organizacional e cadastros. API usa filtros de gerência; services registra histórico.
- `backend/apps/finance/models.py`: orçamento, rateio, documentos, parcelas, vínculos e períodos.
- `backend/apps/finance/services.py`: dinheiro decimal, validações, aprovações, rateio e estorno.
- `backend/apps/finance/selectors.py`: indicadores, filtros, saldo, séries e matriz de risco.
- `backend/apps/finance/api.py`: entrada e saída dos módulos financeiros e anexos privados.
- `backend/apps/finance/views.py`: metadados, relatórios, importação e resumos.
- `backend/apps/evaluations`: convites, critérios, avaliação, confidencialidade e planos de ação.
- `backend/apps/ai/providers.py`: interface de provedor e adaptador local, sem ferramentas de alteração.
- `frontend/src/App.tsx`: sessão, menu e navegação.
- `frontend/src/catalog.ts`: definição dos formulários e colunas.
- `frontend/src/Records.tsx`: listagem, criação, edição e detalhes.
- `frontend/src/Dashboard.tsx`: indicadores e gráficos; recebe cálculos prontos do backend.
- `frontend/src/OtherPages.tsx`: avaliações, relatórios, resumos e administração.

## Alterar o sistema

Mudança de campo exige atualizar modelo, gerar migration, aplicar migrate e ajustar catalog/types/UI. Mudança de regra financeira deve ocorrer em services/selectors, com teste do efeito sobre saldo, rateio, histórico e permissão. Serializers e views não devem incorporar cálculos complexos.

Nunca altere migrations já aplicadas para editar dados. Crie nova migration. Nunca edite valores aprovados diretamente no banco para corrigir um lançamento; use operações formais.

Uma política corporativa nova precisa de decisões registradas antes de habilitar uso real. Aprovação pela interface demonstra o fluxo e não substitui alçada empresarial.

## Operação e produção

Os scripts start-local/stop-local gerenciam somente os processos do projeto. O banco portátil e o Compose são ambientes independentes. Faça backup antes de migrations e mantenha cópias fora do computador antes de usar dados importantes.

Antes de produção: identidade corporativa, MFA, proxy HTTPS, servidor WSGI adequado, segredos gerenciados, banco com privilégio mínimo, backups/restauração, armazenamento/varredura de anexos, monitoramento, revisão ASVS/API Security, testes de carga e aprovação de TI. O servidor de desenvolvimento não é implantação de produção.
