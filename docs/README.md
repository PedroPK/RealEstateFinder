# RealEstateFinder

Aplicação em Python (somente biblioteca padrão, Python 3.10+) para busca de imóveis.

## Funcionalidades

### Busca pública da RE/MAX
- Gera um link para os resultados de busca públicos da RE/MAX Brasil.
- Aceita localidade/termo de busca e finalidade de compra ou aluguel.
- Os parâmetros do site são mantidos em `config/imobiliarias/remax.json`, separados da lógica do conector.
- Imprime a URL para que a busca seja aberta no site; não coleta nem armazena anúncios.

### Descoberta de sites de imobiliárias
- Busca na web (DuckDuckGo HTML, sem chave de API) por imobiliárias com atuação nacional.
- Busca opcional por imobiliárias de uma cidade, parametrizável.
- Ignora redes sociais, portais genéricos e outros domínios que não são sites de imobiliárias.
- Salva as URLs raiz em um arquivo `.properties`, para reutilização sem novas buscas. Execuções seguintes mesclam sem duplicar.

Formato do arquivo:

```
nacional.1=https://exemplo.com.br/
local.sao_paulo.1=https://outra.com.br/
```

## Estrutura

- `realestatefinder/search.py`: consultas e extração das URLs.
- `realestatefinder/storage.py`: leitura/escrita do `.properties`.
- `realestatefinder/models.py`: critérios comuns de busca e tipos de transação.
- `realestatefinder/connectors/remax.py`: montagem e validação de buscas para a RE/MAX Brasil.
- `config/imobiliarias/remax.json`: mapeamento dos parâmetros públicos de busca da RE/MAX.
- `realestatefinder/__main__.py`: linha de comando.
- `tests/test_remax.py`: testes do modelo e do conector da RE/MAX.

## Como executar

```
python3 -m realestatefinder --cidade "Curitiba"
python3 -m realestatefinder --cidade "Recife" --pular-nacionais --arquivo meus_sites.properties
python3 -m realestatefinder --buscar-remax --localidade "Recife" --finalidade comprar
python3 -m realestatefinder --buscar-remax --localidade "Boa Viagem, Recife" --finalidade alugar
python3 -m unittest discover -s tests
```

Opções: `--cidade`, `--arquivo` (padrão `imobiliarias.properties`), `--pular-nacionais`.
Para a busca RE/MAX, `--localidade` é obrigatória e `--finalidade` aceita `comprar` ou `alugar` (padrão `comprar`).

## Limitações

Os resultados da descoberta de imobiliárias dependem do buscador e podem exigir revisão manual da lista. O conector RE/MAX gera o link para a busca pública, mas ainda não baixa nem normaliza os anúncios. A primeira versão mapeia somente localidade e finalidade; outros filtros serão adicionados após validação do contrato público correspondente.
