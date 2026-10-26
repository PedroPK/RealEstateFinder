# Changelog

Todas as mudanças relevantes deste projeto são documentadas aqui.
Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).

## [Não lançado]

### Alterado
- `realestatefinder/connectors/sites.py` deixou de conter regras fixas por site e passou a interpretar o arquivo de parâmetros, mantendo as mesmas URLs geradas.

### Adicionado
- Arquivo de parâmetros `config/imobiliarias/sites.json` com o mapeamento de filtros por site, validado ao carregar e substituível via `REALESTATEFINDER_SITES_CONFIG`; testes cobrem o arquivo e a inclusão de sites sem alterar código.
- Geração de links de busca para portais e imobiliárias mapeados em `imobiliarias.properties`, com filtros específicos por site e avisos sobre parâmetros omitidos.
- Mapeamento dos filtros disponíveis na busca pública RE/MAX: localização, preço, área, tipo de imóvel, dormitórios, banheiros, vagas e características selecionadas.
- Geração de links de busca pública da RE/MAX Brasil, com filtros de localidade e finalidade (compra ou aluguel), parâmetros configuráveis em JSON e testes automatizados.
- Busca de sites de imobiliárias nacionais e de uma cidade parametrizável (`--cidade`), com URLs salvas em arquivo `.properties` para reutilização.
- Repositório Git inicializado com `.gitignore` apropriado para projetos Python.
- Documentação inicial da aplicação em `docs/README.md`.
- Instruções do projeto para manter documentação e ChangeLog atualizados a cada implementação.
