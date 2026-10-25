import argparse
from pathlib import Path

from . import search, storage


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="realestatefinder",
        description="Busca sites de imobiliárias e salva as URLs em um arquivo .properties.",
    )
    parser.add_argument("--cidade", help="Cidade para a busca de imobiliárias locais")
    parser.add_argument("--arquivo", default="imobiliarias.properties",
                        help="Arquivo de saída (padrão: imobiliarias.properties)")
    parser.add_argument("--pular-nacionais", action="store_true",
                        help="Não busca imobiliárias de atuação nacional")
    args = parser.parse_args()

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
