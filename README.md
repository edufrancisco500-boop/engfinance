# EngFinance

Plataforma local de demonstração para gestão financeira da Engenharia de Projetos, com Django/DRF, PostgreSQL e React/TypeScript. Use somente dados fictícios até validar as políticas corporativas.

## O que está disponível

- Dashboard inicial com filtros, evolução mensal, CAPEX/OPEX, carteiras, execução física/financeira e matriz de risco.
- Gerências, coordenações, centros de custo, carteiras, projetos, fornecedores e contratos.
- Orçamentos, revisões, alocações, realocações e aditivos.
- Rateios versionados de contratos financiados por múltiplas carteiras.
- Compromissos, medições, notas fiscais e pagamentos com rateio próprio e uma ou várias origens da etapa anterior.
- Rascunho, envio, aprovação, rejeição, estorno e fechamento/reabertura de competências.
- Avaliações trimestrais por convite, nove critérios, opção Não sei avaliar e planos de ação.
- Página individual de contrato com rateios, documentos, execução e desempenho.
- Anexos privados, exportação Excel/CSV e importação de cadastros com prévia.
- Resumos gerenciais locais por regras, sem envio de informações para IA externa.
- Perfis e acesso por gerência, sessões com CSRF, limitação de tentativas de login e auditoria.

## Abrir neste computador

Os serviços já foram configurados. Endereço: http://127.0.0.1:5173.

Se estiverem parados, na raiz do projeto:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/start-local.ps1
```

Para encerrar:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/stop-local.ps1
```

Após alterar o backend, reinicie somente ele:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/restart-backend.ps1
```

PostgreSQL local: `.local/pgsql`; dados: `.local/pgdata`; porta 5433, somente loopback. Segredos estão em `.env` e `.local`, fora do Git. A conta técnica inicial está em `.local/acesso-local.txt`. Contas pessoais usam as credenciais definidas pelo próprio usuário.

## Demonstração completa

Na pasta backend, com as variáveis locais carregadas:

```powershell
..\.venv\Scripts\python.exe manage.py seed_full_demo --user SEU_USUARIO
```

O comando usa os cadastros DEMO, cria 10 carteiras, projetos e contratos; orçamentos, revisões, alocações, aditivos e rateios; 40 documentos financeiros; 10 convites, 5 avaliações já respondidas e 10 planos de ação. Outros 5 convites ficam disponíveis para testar o formulário. Cada contrato é financiado por duas carteiras. Identificadores fiscais são sintéticos, sem validade fiscal. Só executa com DEBUG=true e política demonstrativa.

Operações financeiras não fazem parte de exclusão comum: valores aprovados são corrigidos por estorno ou novas operações com histórico.

## Instalar em outro ambiente local

Python 3.13, Node 24 e PostgreSQL 17 foram usados na validação. Instale as dependências:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.lock.txt
npm.cmd --prefix frontend ci
```

Crie `.env` a partir de `.env.example` somente se ele ainda não existir e substitua os exemplos de segredo e senha. Configure o banco PostgreSQL. A aplicação local não lê `.env` automaticamente; os scripts acima fazem a carga.

Carga manual no PowerShell, na raiz:

```powershell
Get-Content .env | ForEach-Object {
    if ($_ -match '^([A-Z_]+)=(.*)$') { [Environment]::SetEnvironmentVariable($matches[1], $matches[2], 'Process') }
}
```

Para usar o banco portátil deste computador, defina também POSTGRES_HOST=127.0.0.1 e POSTGRES_PORT=5433. Na pasta backend execute migrate, setup_roles e createsuperuser. Depois inicie `manage.py runserver` e `npm run dev` na pasta frontend, em terminais separados.

## Docker Compose

O Compose usa um banco diferente do banco portátil e não transfere seus dados automaticamente. O Docker deste computador foi instalado em D:; a ativação do WSL pode exigir reinicialização do Windows antes de usar o motor.

```powershell
docker compose up --build -d
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py setup_roles
docker compose exec backend python manage.py createsuperuser
docker compose exec backend python manage.py seed_full_demo --user SEU_USUARIO
```

Os volumes preservam banco e anexos. Os servidores do Compose são de desenvolvimento e só expõem portas no loopback. Não publique esse Compose na internet como produção.

## Verificação

Na pasta backend, com PostgreSQL e as variáveis configuradas:

```powershell
..\.venv\Scripts\python.exe -m pytest --ds=config.settings -p no:cacheprovider
..\.venv\Scripts\python.exe manage.py check
..\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
..\.venv\Scripts\python.exe manage.py spectacular --validate --fail-on-warn --file schema.yml
```

`pytest` sem `--ds` usa SQLite em memória e pula o teste específico de concorrência PostgreSQL. Na pasta frontend, `npm.cmd run build` verifica TypeScript e compila a interface. `npx.cmd --no-install prettier --check src` verifica a formatação. O workflow CI está preparado em `.github/workflows/ci.yml`, mas nenhum repositório remoto foi criado ou publicado.

## Arquivos e decisões

- [Arquitetura e diagrama](docs/architecture.md).
- [Regras financeiras e limites do demonstrador](docs/business-rules.md).
- [Guia de uso](docs/user-guide.md).
- [Verificações](docs/verification.md).
- API interativa, com sessão autenticada: http://127.0.0.1:8000/api/docs/.
- Admin técnico: http://127.0.0.1:8000/admin/.

Entra ID/MFA, provedor externo de IA, SAP, Forms, Power BI, SharePoint, regras contábeis oficiais e homologação de produção dependem de configurações e autorizações corporativas. Nenhum desses sistemas externos foi conectado. Esta entrega é uma versão funcional para testes e evolução, não uma homologação para dados reais.
