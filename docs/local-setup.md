# Configuração deste computador — 31/10/2026

## Concluído

- Python e ambiente virtual verificados; dependências sem conflitos.
- Node, npm e Git disponíveis; frontend compilado.
- PostgreSQL 17.11 instalado em `.local/pgsql`; dados em `.local/pgdata`, porta 5433, somente loopback.
- Migrations aplicadas e perfis criados. Credenciais locais em `.local/acesso-local.txt`, fora do versionamento.
- Seis testes aprovados com PostgreSQL real.
- Interface, sessão, login com CSRF e consultas da API verificados por HTTP.
- DISM RestoreHealth concluído com sucesso; SFC terminou com código 0 e reparos concluídos.
- WSL 3.0.3 instalado a partir de MSI assinado pela Microsoft.
- Docker Desktop 4.97 instalado em `D:\EngFinanceTools\DockerDesktop`, com armazenamento WSL configurado para `D:\EngFinanceTools\DockerData`.
- Docker CLI 29.9.2 e Compose 5.6.1 verificados; `docker compose config --quiet` aprovado.
- PATH do usuário atualizado para o Docker instalado em D:.

## Pendente

O instalador e o Windows indicam reinicialização necessária. Ela não foi executada automaticamente. Após reiniciar, abrir Docker Desktop e verificar o motor com `docker info`. O Compose ainda precisa de execução integrada; seus volumes não compartilham os dados do PostgreSQL local.

O ambiente local sem Docker pode ser iniciado por `scripts/start-local.ps1` e encerrado por `scripts/stop-local.ps1`. URL: http://127.0.0.1:5173.

## Espaço em disco e arquivos preservados

A unidade C: estava sem espaço e provocou erro 112 no primeiro reparo. O instalador Docker foi transferido para `.local/DockerDesktopInstaller.exe`. A instalação incompleta, sem dados de containers encontrados, foi preservada em `.local/docker-partial-backup`. Temporários de instalação/reparo foram direcionados para `.local/dism-scratch`. Documentos pessoais não foram removidos.

C: continua com pouco espaço livre; os programas e dados específicos deste projeto foram mantidos em D: quando possível. Logs de instalação e reparo estão em `.local` e `C:\ProgramData\DockerDesktop\install-log-admin.txt`.

A abertura automática do navegador foi negada pela política da ferramenta. Nenhuma tentativa alternativa foi feita após essa negativa; o acesso manual pelo usuário continua disponível.
