import argparse
from pathlib import Path
import sys

from . import classifier, search, storage
from .connectors.sites import (
    SITE_LABELS,
    available_sites,
    build_site_search_url,
    unsupported_filters,
)
from .models import SearchCriteria, TransactionType


def main() -> None:
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
    args = parser.parse_args()

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
        groups = {group: keep_search_sites(urls) for group, urls in groups.items()}
        storage.save(path, groups)
        print(f"URLs salvas em {path}")
        return

    if not args.pular_nacionais:
        print("Buscando imobiliárias nacionais...")
        found = keep_search_sites(search.search_national())
        groups["nacional"] = storage.merge(groups.get("nacional", []), found)
        print(f"  {len(found)} sites encontrados.")

    if args.cidade:
        print(f"Buscando imobiliárias em {args.cidade}...")
        found = keep_search_sites(search.search_local(args.cidade))
        key = f"local.{storage.city_key(args.cidade)}"
        groups[key] = storage.merge(groups.get(key, []), found)
        print(f"  {len(found)} sites encontrados.")

    storage.save(path, groups)
    print(f"URLs salvas em {path}")


if __name__ == "__main__":
    main()
