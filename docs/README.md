# RealEstateFinder

Aplicação em Python (somente biblioteca padrão, Python 3.10+) para busca de imóveis.

## Funcionalidades

### Busca pública da RE/MAX
- Gera um link para os resultados de busca públicos da RE/MAX Brasil.
- Aceita localidade/termo de busca, estado, cidade e finalidade de compra ou aluguel.
- Mapeia os filtros que existem na pesquisa avançada pública: faixa de preço, área mínima/máxima, tipo de imóvel, dormitórios, banheiros, vagas e características do imóvel.
- Os parâmetros do site são mantidos em `config/imobiliarias/remax.json`, separados da lógica do conector.
- Imprime a URL para que a busca seja aberta no site; não coleta nem armazena anúncios.
- A aplicação não possui interface gráfica própria; os filtros são configurados pela linha de comando.

Na RE/MAX, os tipos de imóvel e as características são convertidos para os identificadores utilizados pela interface/API pública. Entre as características solicitadas, foram encontrados acessibilidade para cadeira de rodas, jardim, piscina, água individualizada, gás individualizado e varanda gourmet. Suítes, mobiliado, dependência de serviço, despensa, área pet (o site oferece “Permite Animais”, que não é equivalente), playground, brinquedoteca, academia, salão de festas, churrasqueira, área gourmet e quadra não estão disponíveis como filtros correspondentes nessa interface e não são enviados. O item “Área de brasil” não tem correspondência identificável e também não é mapeado.

### Busca em outros sites
- `--buscar-site` gera URLs públicas para os sites mapeados; pode ser repetido ou receber `todos`.
- Os sites registrados são ZAP Imóveis, Imóvel Guide, Imovelweb, Wimóveis, Lopes, CTI, Luiza Parizi, Âncora, Newville, DJM, GVI, BCI e as imobiliárias Bellolar, True, Morada Sol, Rede Imóveis PE e Fleischman (plataforma Kenlo).
- ZAP mapeia localização, tipo, preço, área, quartos, suítes, banheiros e vagas. Imóvel Guide mapeia localização, tipo, preço, área, quartos, banheiros e vagas.
- Imovelweb mapeia transação, localização, tipo, dormitórios, banheiros e vagas pela URL. Wimóveis mapeia transação, localização e tipo; os demais filtros não têm sintaxe de URL confirmada.
- Os sites Kenlo compartilham a rota de transação/tipo/cidade; o parâmetro `quartos` foi confirmado em Bellolar e usado nos demais sites desse mesmo sistema. Lopes, CTI, Luiza Parizi e Âncora mapeiam somente os segmentos de URL observados.
- Newville mapeia finalidade (`negociacao=venda|locacao`), cidade (`cidade=<cidade>--<uf>`), preço mínimo/máximo, suítes, vagas e os tipos com valor confirmado no formulário. A busca pública com `tipo=casa` mudou os resultados, mas a amostra apresentou dois anúncios que não pareciam casas; os filtros de tipo podem herdar essa imprecisão do próprio site. DJM e GVI têm apenas a rota pública de compra/aluguel. BCI oferece rotas de compra/aluguel, mas seus filtros são controlados por JavaScript e parâmetros GET tentados foram ignorados.
- Os filtros ausentes ou sem comportamento de URL confirmado são omitidos, e a CLI avisa quais foram ignorados. Outros sites da lista permanecem sem conector quando são diretórios/conteúdo, não têm anúncios disponíveis ou expõem filtros somente por interfaces cuja API/semântica não foi confirmada.

### Arquivo de parâmetros do mapeamento (`config/imobiliarias/sites.json`)
- Define, por site, quais filtros (`supported_filters`) são enviados e como: segmentos de caminho, parâmetros GET (`query`), tipos de imóvel aceitos e valores de transação. O bloco `_ajuda` do arquivo descreve os marcadores e opções.
- Para ajustar um filtro ou incluir um site, edite o JSON (sem alterar código) e rode os testes. Filtros sem evidência pública devem ficar fora de `supported_filters`.
- Um arquivo alternativo pode ser usado com a variável de ambiente `REALESTATEFINDER_SITES_CONFIG`. O arquivo é validado ao carregar (campos obrigatórios e nomes de filtros conhecidos).
- Não há script que descubra os campos automaticamente: o mapeamento atual foi levantado manualmente (inspeção das interfaces/URLs públicas) e registrado neste arquivo; mudanças nos sites exigem nova verificação e edição manual.

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
- `config/imobiliarias/sites.json`: arquivo de parâmetros com o mapeamento de cada site (URL base, rotas, parâmetros GET, tipos e filtros suportados).
- `realestatefinder/connectors/sites.py`: motor genérico que lê o arquivo acima e gera as URLs; não contém regras específicas de sites.
- `config/imobiliarias/remax.json`: mapeamento dos parâmetros públicos de busca da RE/MAX.
- `realestatefinder/__main__.py`: linha de comando.
- `tests/test_remax.py` e `tests/test_sites.py`: testes dos conectores e critérios.

## Como executar

```
python3 -m realestatefinder --cidade "Curitiba"
python3 -m realestatefinder --cidade "Recife" --pular-nacionais --arquivo meus_sites.properties
python3 -m realestatefinder --buscar-remax --localidade "Recife" --finalidade comprar
python3 -m realestatefinder --buscar-remax --localidade "Boa Viagem, Recife" --finalidade alugar
python3 -m realestatefinder --buscar-remax --estado Pernambuco --cidade-imovel Recife --preco-minimo 300000 --preco-maximo 700000 --area-minima 60 --quartos 2 --tipo-imovel Apartamento --caracteristica Piscina
python3 -m realestatefinder --buscar-site zap --estado PE --cidade-imovel Recife --tipo-imovel Apartamento --quartos 3 --suites 1 --preco-minimo 300000 --preco-maximo 700000
python3 -m realestatefinder --buscar-site zap --buscar-site imovelguide --estado PE --cidade-imovel Recife --tipo-imovel Apartamento --banheiros 2
python3 -m realestatefinder --buscar-site todos --estado PE --cidade-imovel Recife --tipo-imovel Apartamento
python3 -m unittest discover -s tests
```

Opções: `--cidade`, `--arquivo` (padrão `imobiliarias.properties`), `--pular-nacionais`.
Para a busca RE/MAX, informe pelo menos um entre `--localidade`, `--estado` e `--cidade-imovel`; `--finalidade` aceita `comprar` ou `alugar` (padrão `comprar`). Os filtros numéricos são `--preco-minimo`, `--preco-maximo`, `--area-minima`, `--area-maxima`, `--quartos`, `--suites`, `--banheiros` e `--vagas`. `--tipo-imovel` e `--caracteristica` podem ser repetidos; os valores aceitos são as chaves correspondentes em `config/imobiliarias/remax.json`. Nos outros sites, os filtros efetivamente incluídos dependem do mapeamento de cada portal.
Para outros sites, use `--buscar-site` uma ou mais vezes (ou `todos`), `--estado` e `--cidade-imovel`, além dos filtros comuns. A aplicação gera as URLs para cada site e apresenta avisos sobre filtros omitidos por falta de um mapeamento confirmado.

## Limitações

Os resultados da descoberta de imobiliárias dependem do buscador e podem exigir revisão manual da lista. Os conectores geram links públicos, mas ainda não baixam nem normalizam os anúncios. A cobertura de filtros varia por site; campos sem mapeamento confirmado são ignorados e informados.
