# Verificação do primeiro marco

**Verificação atual da versão 0.2:** veja [release-0.2.md](release-0.2.md). São 21 testes aprovados no PostgreSQL e módulos adicionais disponíveis. O conteúdo abaixo registra o histórico do primeiro marco.

Executado em 31/10/2026:

- Python 3.13 e ambiente virtual local.
- Cinco testes de acesso/auditoria aprovados com SQLite em memória.
- Django system check sem problemas.
- Migrations iniciais geradas; nenhuma alteração pendente de modelagem.
- OpenAPI gerado e validado em `backend/schema.yml`.
- Compilação TypeScript e build Vite aprovados.
- Instalação npm reportou zero vulnerabilidades conhecidas naquele momento.

## Configuração local posterior

- PostgreSQL 17.11 instalado em `.local/pgsql`, banco isolado na porta 5433.
- Migrations aplicadas no PostgreSQL real e perfis iniciais criados.
- Seis testes aprovados no PostgreSQL, incluindo regressão do login com origem confiável e token CSRF obrigatório.
- Interface, sessão, login com CSRF e consultas dos cinco cadastros verificados por HTTP pelo proxy Vite.
- Ajustada a lista de origens CSRF permitidas em desenvolvimento, mantendo verificação de token.
- Criados scripts para iniciar e encerrar os servidores locais.

Docker/WSL foram instalados após reparo Windows bem-sucedido. CLI e configuração Compose foram verificados; execução dos containers aguarda reinicialização exigida pelo Windows. Detalhes em `local-setup.md`.

Limitações: Compose ainda não foi executado de ponta a ponta. Não foram executados testes visuais no navegador ou testes de concorrência financeira (módulo ainda não implementado). Autenticação corporativa e segurança de produção permanecem pendentes.
