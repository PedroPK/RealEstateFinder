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
    parser.add_argument(
        "--finalidade",
        choices=[transaction.value for transaction in TransactionType],
        default=TransactionType.BUY.value,
        help="Finalidade para --buscar-remax (padrão: comprar)",
    )
    args = parser.parse_args()

    if args.buscar_remax:
        if not args.localidade:
            parser.error("--buscar-remax exige --localidade")
        if args.cidade:
            parser.error("--cidade não pode ser usada junto com --buscar-remax")
        try:
            criteria = SearchCriteria(
                location=args.localidade,
                transaction=TransactionType(args.finalidade),
            )
        except ValueError as exc:
            parser.error(str(exc))
        print(build_search_url(criteria))
        return

    if args.localidade:
        parser.error("--localidade só pode ser usada com --buscar-remax")
    if args.finalidade != TransactionType.BUY.value:
        parser.error("--finalidade só pode ser usada com --buscar-remax")

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
