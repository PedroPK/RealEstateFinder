import argparse
from pathlib import Path

from . import search, storage
from .connectors.remax import build_search_url
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
    parser.add_argument(
        "--buscar-remax",
        action="store_true",
        help="Gera uma URL de busca pública de imóveis da RE/MAX",
    )
    parser.add_argument(
        "--localidade",
        help="Cidade, bairro ou termo de busca para --buscar-remax",
    )
    parser.add_argument("--estado", help="Estado para --buscar-remax")
    parser.add_argument("--cidade-imovel", help="Cidade para --buscar-remax")
    parser.add_argument(
        "--finalidade",
        choices=[transaction.value for transaction in TransactionType],
        default=TransactionType.BUY.value,
        help="Finalidade para --buscar-remax (padrão: comprar)",
    )
    parser.add_argument("--preco-minimo", type=float, help="Preço mínimo para --buscar-remax")
    parser.add_argument("--preco-maximo", type=float, help="Preço máximo para --buscar-remax")
    parser.add_argument("--area-minima", type=float, help="Área mínima em m² para --buscar-remax")
    parser.add_argument("--area-maxima", type=float, help="Área máxima em m² para --buscar-remax")
    parser.add_argument("--quartos", type=int, help="Quantidade mínima de dormitórios")
    parser.add_argument("--banheiros", type=int, help="Quantidade mínima de banheiros")
    parser.add_argument("--vagas", type=int, help="Quantidade mínima de vagas")
    parser.add_argument(
        "--tipo-imovel",
        action="append",
        default=[],
        help="Tipo de imóvel mapeado na RE/MAX; pode ser repetido",
    )
    parser.add_argument(
        "--caracteristica",
        action="append",
        default=[],
        help="Característica mapeada na RE/MAX; pode ser repetida",
    )
    args = parser.parse_args()

    if args.buscar_remax:
        if args.cidade:
            parser.error("--cidade não pode ser usada junto com --buscar-remax")
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
                bathrooms=args.banheiros,
                parking_spaces=args.vagas,
                property_types=tuple(args.tipo_imovel),
                property_features=tuple(args.caracteristica),
            )
            url = build_search_url(criteria)
        except ValueError as exc:
            parser.error(str(exc))
        print(url)
        return

    remax_only_options = (
        args.localidade,
        args.estado,
        args.cidade_imovel,
        args.preco_minimo,
        args.preco_maximo,
        args.area_minima,
        args.area_maxima,
        args.quartos,
        args.banheiros,
        args.vagas,
        args.tipo_imovel,
        args.caracteristica,
    )
    if any(remax_only_options) or args.finalidade != TransactionType.BUY.value:
        parser.error("Os filtros de imóveis só podem ser usados com --buscar-remax")

    path = Path(args.arquivo)
    groups = storage.load(path)

    if not args.pular_nacionais:
        print("Buscando imobiliárias nacionais...")
        found = search.search_national()
        groups["nacional"] = storage.merge(groups.get("nacional", []), found)
        print(f"  {len(found)} sites encontrados.")

    if args.cidade:
        print(f"Buscando imobiliárias em {args.cidade}...")
        found = search.search_local(args.cidade)
        key = f"local.{storage.city_key(args.cidade)}"
        groups[key] = storage.merge(groups.get(key, []), found)
        print(f"  {len(found)} sites encontrados.")

    storage.save(path, groups)
    print(f"URLs salvas em {path}")


if __name__ == "__main__":
    main()
