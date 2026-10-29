# RealEstateFinder

Aplicação em Python (somente biblioteca padrão, Python 3.10+) para busca de imóveis.

## Funcionalidades

### Busca pública da RE/MAX
- Gera um link para os resultados de busca públicos da RE/MAX Brasil.
- Aceita localidade/termo de busca, estado, cidade e finalidade de compra ou aluguel.
- Mapeia os filtros que existem na pesquisa avançada pública: faixa de preço, área mínima/máxima, tipo de imóvel, dormitórios, banheiros, vagas e características do imóvel.
- Os parâmetros do site são mantidos em `config/imobiliarias/sites.json` (entrada `remax`), separados da lógica do motor.
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

### Inspeção site por site com Playwright
- O modo `--inspecionar-site` abre um único site por execução em um Chromium visível. Informe um ID já mapeado ou uma URL pública, inclusive de um domínio ainda não mapeado.
- A dependência é opcional. No macOS/Linux, crie um ambiente virtual e instale Playwright/Chromium com:

  ```
  python3 -m venv .venv
  .venv/bin/python -m pip install -r requirements-inspecao.txt
  .venv/bin/python -m playwright install chromium
  ```

  No Windows, use `.venv\Scripts\python.exe` no lugar de `.venv/bin/python`.
- Durante a sessão, informe o nome do filtro que vai testar (por exemplo, `quartos=2`), altere esse filtro no navegador e pressione Enter depois que os resultados atualizarem. Repita para cada filtro; Enter sem texto encerra e grava o relatório.
- O JSON registra método, host, caminho sanitizado, nomes/valores dos parâmetros não sensíveis, campos simples de corpos JSON/form, etapa marcada, status e tipo de conteúdo da resposta. Não captura cabeçalhos completos, cookies, tokens nem corpos de resposta; apenas o `content-type` é mantido. Relatórios padrão ficam em `inspecoes/`, ignorada pelo Git; `--relatorio-inspecao` permite escolher outro caminho.
- Com `--esquema-resposta`, respostas JSON de XHR/fetch (até 2 MB) também têm o esquema gravado (`response_schema`: nomes e tipos de campos, sem valores) e os tamanhos das listas (`response_list_sizes`), o que ajuda a identificar o endpoint da lista de anúncios, a paginação e se um filtro reduziu os resultados.
- `--analisar-inspecao RELATORIO.json` compara cada etapa com as anteriores (mesmo endpoint) e lista, por filtro, os parâmetros de query/corpo novos ou alterados e mudanças de caminho, ordenados por probabilidade (valor igual ao informado na etapa e nome parecido). São apenas sugestões.
- A inspeção é observacional e manual: não seleciona controles automaticamente, não confirma por si só que o filtro afetou os resultados e não contorna autenticação, CAPTCHA, bloqueios ou limites. Compare a carga inicial com cada etapa, valide os resultados visíveis e só então atualize o mapeamento em `sites.json`.
- Use apenas buscas públicas, não entre em contas e não digite dados pessoais. Respeite os termos e limites de cada site; prefira HTTPS.

### Descoberta de sites de imobiliárias
- Busca na web (DuckDuckGo HTML, sem chave de API) por imobiliárias com atuação nacional.
- Busca opcional por imobiliárias de uma cidade, parametrizável.
- Ignora redes sociais, portais genéricos, subdomínios `blog.` e outros domínios que não são sites de imobiliárias.
- Consultas voltadas a portais e anúncios (por exemplo, "imóveis à venda em {cidade}"), além das consultas por imobiliárias.
- Verifica se cada site encontrado permite buscar imóveis (`realestatefinder/classifier.py`) e descarta diretórios, blogs, associações, software, franquias e notícias. A análise da página inicial procura opção de compra/aluguel junto de filtros, anúncios com preço, links de navegação de venda e aluguel ou chamadas como "Pesquise o seu imóvel". Sites já mapeados em `sites.json` são aceitos sem acesso à rede; sites fora do ar ou que só carregam JavaScript ficam como "não verificáveis" e são mantidos, pois não há evidência de que não tenham busca.
- `--manter-sem-busca` desativa o descarte; `--revisar-arquivo` reavalia um `.properties` existente e remove os sites sem busca. A heurística é uma aproximação: pode errar em sites atípicos, e nesses casos o domínio pode ser ajustado manualmente.
- Salva as URLs raiz em um arquivo `.properties`, para reutilização sem novas buscas. Execuções seguintes mesclam sem duplicar.

Formato do arquivo:

```
nacional.1=https://exemplo.com.br/
local.sao_paulo.1=https://outra.com.br/
```

## Logs e métricas

Cada execução gera logs para depuração e diagnóstico:

- **Console (stderr)**: nível `INFO` por padrão; altere com `--log-nivel DEBUG|INFO|WARNING|ERROR` ou `REALESTATEFINDER_LOG_LEVEL`. A saída normal (stdout) não muda.
- **Arquivo**: `logs/realestatefinder.log` (rotativo, 1 MB × 3 backups), sempre em `DEBUG`. Use `--log-arquivo CAMINHO` (ou `REALESTATEFINDER_LOG_FILE`) para mudar o local e `--sem-log-arquivo` para desativar.
- **Conteúdo**: argumentos da execução, início/fim e duração de cada consulta, download de página, classificação de sites (mantidos/descartados/não verificáveis), geração de URLs, leitura/gravação do arquivo, avisos, falhas (com stack trace em exceções não tratadas) e a duração total.
- **Métricas**: ao final, o log traz um resumo (`métrica contador ...` e `métrica tempo ...` com n, total, média e máximo por operação, como `search.consulta`, `classifier.download`, `classifier.filtro`, `sites.gerar_url`, `storage.salvar`, `fluxo.*`).

## Estrutura

- `realestatefinder/observability.py`: configuração de logs, cronometragem (`timed`) e métricas.

- `realestatefinder/search.py`: consultas e extração das URLs.
- `realestatefinder/classifier.py`: verificação de que o site oferece busca de imóveis.
- `realestatefinder/storage.py`: leitura/escrita do `.properties`.
- `realestatefinder/models.py`: critérios comuns de busca e tipos de transação.
- `config/imobiliarias/sites.json`: arquivo de parâmetros com o mapeamento de cada site (URL base, rotas, parâmetros GET, tipos e filtros suportados).
- `realestatefinder/connectors/sites.py`: motor genérico que lê o arquivo acima e gera as URLs; não contém regras específicas de sites.
- `realestatefinder/site_inspector.py`: inspeção manual do tráfego de rede com Playwright, com relatórios sanitizados e esquema opcional das respostas.
- `realestatefinder/inspection_analysis.py`: análise dos relatórios, com parâmetros candidatos por filtro.
- `realestatefinder/__main__.py`: linha de comando.
- `tests/test_remax.py` (critérios e RE/MAX via motor unificado), `tests/test_sites.py`, `tests/test_classifier.py` e `tests/test_observability.py`: testes dos conectores, critérios, classificador e logs/métricas.

## Como executar

```
python3 -m realestatefinder --cidade "Curitiba"
python3 -m realestatefinder --cidade "Recife" --pular-nacionais --arquivo meus_sites.properties
python3 -m realestatefinder --buscar-site remax --localidade "Recife" --finalidade comprar
python3 -m realestatefinder --buscar-site remax --localidade "Boa Viagem, Recife" --finalidade alugar
python3 -m realestatefinder --buscar-site remax --estado Pernambuco --cidade-imovel Recife --preco-minimo 300000 --preco-maximo 700000 --area-minima 60 --quartos 2 --tipo-imovel Apartamento --caracteristica Piscina
python3 -m realestatefinder --buscar-site zap --estado PE --cidade-imovel Recife --tipo-imovel Apartamento --quartos 3 --suites 1 --preco-minimo 300000 --preco-maximo 700000
python3 -m realestatefinder --buscar-site zap --buscar-site imovelguide --estado PE --cidade-imovel Recife --tipo-imovel Apartamento --banheiros 2
python3 -m realestatefinder --buscar-site todos --estado PE --cidade-imovel Recife --tipo-imovel Apartamento
python3 -m realestatefinder --inspecionar-site remax
python3 -m realestatefinder --inspecionar-site https://exemplo.com.br/busca --relatorio-inspecao inspecoes/exemplo.json
python3 -m realestatefinder --inspecionar-site remax --esquema-resposta --relatorio-inspecao inspecoes/remax.json
python3 -m realestatefinder --analisar-inspecao inspecoes/remax.json
python3 -m realestatefinder --revisar-arquivo
python3 -m unittest discover -s tests
```

Opções: `--cidade`, `--arquivo` (padrão `imobiliarias.properties`), `--pular-nacionais`.
Para a busca (`--buscar-site`), informe pelo menos um entre `--localidade`, `--estado` e `--cidade-imovel`; `--finalidade` aceita `comprar` ou `alugar` (padrão `comprar`). Os filtros numéricos são `--preco-minimo`, `--preco-maximo`, `--area-minima`, `--area-maxima`, `--quartos`, `--suites`, `--banheiros` e `--vagas`. `--tipo-imovel` e `--caracteristica` podem ser repetidos; os valores aceitos são as chaves de `type_sets`/`feature_sets` em `config/imobiliarias/sites.json` (a RE/MAX aceita vários tipos e características; valores sem mapeamento são omitidos com aviso). Nos outros sites, os filtros efetivamente incluídos dependem do mapeamento de cada portal.
Para outros sites, use `--buscar-site` uma ou mais vezes (ou `todos`), `--estado` e `--cidade-imovel`, além dos filtros comuns. A aplicação gera as URLs para cada site e apresenta avisos sobre filtros omitidos por falta de um mapeamento confirmado.
Para investigar um novo site, use `--inspecionar-site` uma vez por domínio; as etapas marcadas no navegador ajudam a comparar a carga inicial com cada filtro. A instalação do Playwright é opcional e necessária somente para esse modo.

## Limitações

Os resultados da descoberta de imobiliárias dependem do buscador e podem exigir revisão manual da lista. Os conectores geram links públicos, mas ainda não baixam nem normalizam os anúncios. A cobertura de filtros varia por site; campos sem mapeamento confirmado são ignorados e informados.
