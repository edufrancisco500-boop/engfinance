# Correção dos filtros — 01/11/2026

- Ano passou de campo numérico com incremento decimal para lista suspensa de anos inteiros. Inclui anos encontrados nos dados e uma faixa em torno do exercício atual.
- Ao alterar um filtro, o dashboard limpa o resultado anterior enquanto consulta o novo recorte.
- Falhas de consulta não mantêm indicadores antigos na tela. A mensagem de conexão indisponível foi traduzida e orienta a iniciar o serviço.
- Requisições anteriores são canceladas; respostas atrasadas não substituem os dados do filtro mais recente.
- Consultas por contrato, fornecedor e status também consideram documentos com parcelas manuais, mesmo sem um rateio contratual cadastrado.
- Os serviços locais foram iniciados novamente após estarem parados.

Verificação: 38 testes PostgreSQL e 3 testes React aprovados; TypeScript/build e Ruff aprovados. Foram testados ano, mês, trimestre, gerência, carteira, projeto, coordenação, status, contrato, fornecedor, categoria e combinações sem resultados.

O orçamento e o saldo para comprometer são posições anuais, por definição do demonstrador. Mudar somente o mês pode manter esses indicadores. Comprometido, realizado e pago no período são recortados pelo mês/trimestre. Isso não deve ser confundido com exibição de resultado antigo após erro de consulta.
