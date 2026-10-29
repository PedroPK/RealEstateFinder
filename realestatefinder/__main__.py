import argparse
import logging
import os
import time
from pathlib import Path

from . import classifier, search, storage
from .connectors.sites import (
    SITE_LABELS,
    available_sites,
    build_site_search_url,
    unsupported_filters,
)
from .models import SearchCriteria, TransactionType
from .observability import DEFAULT_LOG_FILE, metrics, setup_logging, timed

logger = logging.getLogger("realestatefinder.cli")


def main() -> None:
    start = time.perf_counter()
    status = "erro"
    try:
        _run()
        status = "sucesso"
    except SystemExit as exc:
        status = "sucesso" if exc.code in (None, 0) else f"saída {exc.code}"
        raise
    except BaseException:
        logger.exception("execução abortada por exceção não tratada")
        raise
    finally:
        logger.info("execução finalizada (%s) em %.3fs", status, time.perf_counter() - start)
        metrics.log_summary()


def _run() -> None:
    parser = argparse.ArgumentParser(
        prog="realestatefinder",
        description="Busca sites de imobiliárias ou monta buscas de imóveis.",
    )
    parser.add_argument("--cidade", help="Cidade para a busca de imobiliárias locais")
    parser.add_argument("--arquivo", default="imobiliarias.properties",
                        help="Arquivo de saída (padrão: imobiliarias.properties)")
    parser.add_argument("--pular-nacionais", action="store_true",
                        help="Não busca imobiliárias de atuação nacional")
    parser.add_argument("--manter-sem-busca", action="store_true",
                        help="Não descarta sites sem busca de imóveis na descoberta")
    parser.add_argument("--revisar-arquivo", action="store_true",
                        help="Reavalia o arquivo e remove sites sem busca de imóveis")
    parser.add_argument(
        "--buscar-site",
        action="append",
        choices=[*available_sites(), "todos"],
        help="Gera URL de busca para um site mapeado (inclusive 'remax'); pode ser repetido ou usar 'todos'",
    )
    parser.add_argument(
        "--inspecionar-site",
        help="Abre um site no Playwright para inspecionar filtros manualmente; aceita ID ou URL",
    )
    parser.add_argument(
        "--relatorio-inspecao",
        help="Caminho do relatório JSON de inspeção (padrão: inspecoes/<site>-<data>.json)",
    )
    parser.add_argument(
        "--esquema-resposta",
        action="store_true",
        help="Na inspeção, registra o esquema (nomes e tipos, sem valores) das respostas JSON",
    )
    parser.add_argument(
        "--analisar-inspecao",
        help="Analisa um relatório de inspeção e sugere parâmetros candidatos por filtro",
    )
    parser.add_argument(
        "--localidade",
        help="Cidade, bairro ou termo de busca",
    )
    parser.add_argument("--estado", help="Estado ou UF para busca de imóveis")
    parser.add_argument("--cidade-imovel", help="Cidade para busca de imóveis")
    parser.add_argument(
        "--finalidade",
        choices=[transaction.value for transaction in TransactionType],
        default=TransactionType.BUY.value,
        help="Finalidade para busca de imóveis (padrão: comprar)",
    )
    parser.add_argument("--preco-minimo", type=float, help="Preço mínimo")
    parser.add_argument("--preco-maximo", type=float, help="Preço máximo")
    parser.add_argument("--area-minima", type=float, help="Área mínima em m²")
    parser.add_argument("--area-maxima", type=float, help="Área máxima em m²")
    parser.add_argument("--quartos", type=int, help="Quantidade mínima de dormitórios")
    parser.add_argument("--suites", type=int, help="Quantidade de suítes")
    parser.add_argument("--banheiros", type=int, help="Quantidade mínima de banheiros")
    parser.add_argument("--vagas", type=int, help="Quantidade mínima de vagas")
    parser.add_argument(
        "--tipo-imovel",
        action="append",
        default=[],
        help="Tipo de imóvel; pode ser repetido quando o site suportar",
    )
    parser.add_argument(
        "--caracteristica",
        action="append",
        default=[],
        help="Característica mapeada para o site; pode ser repetida",
    )
    parser.add_argument(
        "--log-nivel",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default=os.environ.get("REALESTATEFINDER_LOG_LEVEL", "INFO").upper(),
        help="Nível de log no console (stderr); o arquivo sempre registra DEBUG (padrão: INFO)",
    )
    parser.add_argument(
        "--log-arquivo",
        default=os.environ.get("REALESTATEFINDER_LOG_FILE", str(DEFAULT_LOG_FILE)),
        help=f"Arquivo de log rotativo (padrão: {DEFAULT_LOG_FILE})",
    )
    parser.add_argument("--sem-log-arquivo", action="store_true",
                        help="Não grava o arquivo de log")
    args = parser.parse_args()
    setup_logging(args.log_nivel, None if args.sem_log_arquivo else args.log_arquivo)
    logged_args = vars(args).copy()
    if args.inspecionar_site:
        logged_args["inspecionar_site"] = "<informado>"
    logger.info("execução iniciada; argumentos: %s", logged_args)

    if args.analisar_inspecao:
        from .inspection_analysis import analyze_report_file

        if args.inspecionar_site or args.buscar_site:
            parser.error("--analisar-inspecao não pode ser combinado com outras ações")
        try:
            print(analyze_report_file(Path(args.analisar_inspecao)))
        except (OSError, ValueError, KeyError) as exc:
            parser.error(f"relatório inválido: {exc}")
        return

    if args.inspecionar_site:
        search_options = (
            args.buscar_site,
            args.cidade,
            args.localidade,
            args.estado,
            args.cidade_imovel,
            args.preco_minimo,
            args.preco_maximo,
            args.area_minima,
            args.area_maxima,
            args.quartos,
            args.suites,
            args.banheiros,
            args.vagas,
            args.tipo_imovel,
            args.caracteristica,
        )
        if any(search_options) or args.revisar_arquivo:
            parser.error("--inspecionar-site não pode ser combinado com opções de busca")
        from .site_inspector import inspect_site

        try:
            report_path = inspect_site(
                args.inspecionar_site,
                Path(args.relatorio_inspecao) if args.relatorio_inspecao else None,
                args.esquema_resposta,
            )
        except (RuntimeError, ValueError) as exc:
            parser.error(str(exc))
        print(f"Relatório salvo em {report_path}")
        return
    if args.relatorio_inspecao:
        parser.error("--relatorio-inspecao só pode ser usado com --inspecionar-site")
    if args.esquema_resposta:
        parser.error("--esquema-resposta só pode ser usado com --inspecionar-site")

    if args.buscar_site:
        if args.cidade:
            parser.error("--cidade não pode ser usada junto com busca de imóveis")
        try:
            criteria = SearchCriteria(
                location=args.localidade,
                transaction=TransactionType(args.finalidade),
                state=args.estado,
                city=args.cidade_imovel,
                min_price=args.preco_minimo,
                max_price=args.preco_maximo,
                min_area=args.area_minima,
                max_area=args.area_maxima,
                bedrooms=args.quartos,
                suites=args.suites,
                bathrooms=args.banheiros,
                parking_spaces=args.vagas,
                property_types=tuple(args.tipo_imovel),
                property_features=tuple(args.caracteristica),
            )
        except ValueError as exc:
            parser.error(str(exc))
        site_ids = list(dict.fromkeys(args.buscar_site))
        if "todos" in site_ids:
            if len(site_ids) != 1:
                parser.error("'todos' não pode ser combinado com sites específicos")
            site_ids = list(available_sites())
        for site in site_ids:
            try:
                url = build_site_search_url(criteria, site)
            except ValueError as exc:
                print(f"Indisponível [{SITE_LABELS[site]}]: {exc}")
                continue
            print(f"{SITE_LABELS[site]}: {url}")
            ignored = unsupported_filters(criteria, site)
            if ignored:
                print(
                    f"Aviso [{SITE_LABELS[site]}]: filtros ignorados: {', '.join(ignored)}."
                )
                logger.warning("filtros ignorados em %s: %s", site, ", ".join(ignored))
        return

    property_search_options = (
        args.localidade,
        args.estado,
        args.cidade_imovel,
        args.preco_minimo,
        args.preco_maximo,
        args.area_minima,
        args.area_maxima,
        args.quartos,
        args.suites,
        args.banheiros,
        args.vagas,
        args.tipo_imovel,
        args.caracteristica,
    )
    if any(property_search_options) or args.finalidade != TransactionType.BUY.value:
        parser.error("Os filtros de imóveis só podem ser usados com --buscar-site")

    path = Path(args.arquivo)
    groups = storage.load(path)

    def keep_search_sites(urls: list[str]) -> list[str]:
        if args.manter_sem_busca:
            return urls
        kept, removed, unverified = classifier.filter_search_sites(urls)
        if removed:
            print(f"  {len(removed)} descartados por não oferecerem busca de imóveis.")
        if unverified:
            print(f"  {len(unverified)} mantidos sem verificação (site fora do ar ou só JavaScript).")
        return kept

    if args.revisar_arquivo:
        print(f"Revisando {path}...")
        with timed("fluxo.revisar", logger):
            groups = {group: keep_search_sites(urls) for group, urls in groups.items()}
        storage.save(path, groups)
        print(f"URLs salvas em {path}")
        return

    if not args.pular_nacionais:
        print("Buscando imobiliárias nacionais...")
        with timed("fluxo.nacionais", logger):
            found = keep_search_sites(search.search_national())
        groups["nacional"] = storage.merge(groups.get("nacional", []), found)
        print(f"  {len(found)} sites encontrados.")

    if args.cidade:
        print(f"Buscando imobiliárias em {args.cidade}...")
        with timed("fluxo.locais", logger, cidade=args.cidade):
            found = keep_search_sites(search.search_local(args.cidade))
        key = f"local.{storage.city_key(args.cidade)}"
        groups[key] = storage.merge(groups.get(key, []), found)
        print(f"  {len(found)} sites encontrados.")

    storage.save(path, groups)
    print(f"URLs salvas em {path}")


if __name__ == "__main__":
    main()
