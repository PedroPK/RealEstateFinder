# RealEstateFinder

Aplicação em Python (somente biblioteca padrão, Python 3.10+) para busca de imóveis.

## Funcionalidades

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
- `realestatefinder/__main__.py`: linha de comando.

## Como executar

```
python3 -m realestatefinder --cidade "Curitiba"
python3 -m realestatefinder --cidade "Recife" --pular-nacionais --arquivo meus_sites.properties
```

Opções: `--cidade`, `--arquivo` (padrão `imobiliarias.properties`), `--pular-nacionais`.

## Limitações

Os resultados dependem do buscador e podem exigir revisão manual da lista.
