#!/usr/bin/env python3
"""
Extrator de dados OLX a partir do HTML renderizado pelo Crawl4AI.
Extrai dados do __NEXT_DATA__ (Next.js SSR) ou do Schema.org JSON-LD.
"""
import sys
import json
import re
import os


def extract_next_data(html: str) -> dict | None:
    """Extrai o JSON do __NEXT_DATA__ do HTML."""
    match = re.search(
        r'<script id="__NEXT_DATA__"[^>]*type="application/json"[^>]*>(.*?)</script>',
        html, re.DOTALL
    )
    if match:
        return json.loads(match.group(1))
    return None


def extract_schema_org(html: str) -> list[dict]:
    """Extrai dados Schema.org JSON-LD."""
    schemas = []
    for match in re.finditer(
        r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
        html, re.DOTALL
    ):
        try:
            data = json.loads(match.group(1))
            schemas.append(data)
        except json.JSONDecodeError:
            pass
    return schemas


def parse_listings(raw: dict) -> dict:
    """
    Processa o resultado de uma busca OLX.
    Extrai do __NEXT_DATA__ os anúncios e metadados.
    """
    result = raw.get("results", [{}])[0]
    html = result.get("html", "")

    if not html:
        return {"error": "No HTML returned from Crawl4AI", "raw": raw}

    next_data = extract_next_data(html)

    if not next_data:
        return {"error": "No __NEXT_DATA__ found in HTML", "raw": raw}

    page_props = next_data.get("props", {}).get("pageProps", {})

    ads = page_props.get("ads", [])
    total = page_props.get("totalOfAds", 0)
    page_index = page_props.get("pageIndex", 1)
    page_size = page_props.get("pageSize", 50)
    filters = page_props.get("filters", {})
    categories = page_props.get("categoriesList", [])
    locations = page_props.get("locations", [])

    # Normalizar anúncios
    normalized_ads = []
    for ad in ads:
        # Extrair propriedades como dict chave->valor
        props_dict = {}
        for prop in ad.get("properties", []):
            props_dict[prop.get("name", "")] = {
                "value": prop.get("value", ""),
                "label": prop.get("label", "")
            }

        # Extrair imagens
        images = [img.get("original", "") for img in ad.get("images", [])]

        # Badges OLX Pay
        badges = [b.get("text", "") for b in
                   ad.get("olxPay", {}).get("transactionalBadges", [])]

        normalized_ads.append({
            "id": ad.get("listId"),
            "titulo": ad.get("subject"),
            "preco": ad.get("priceValue"),
            "preco_antigo": ad.get("oldPrice"),
            "localizacao": ad.get("location"),
            "categoria": ad.get("categoryName"),
            "anunciante_profissional": ad.get("professionalAd", False),
            "imagens": images,
            "badges": badges,
            "propriedades": props_dict,
            "url_view_360": ad.get("view360", {}).get("url"),
            "video_count": ad.get("videoCount", 0),
            "fixado_topo": ad.get("fixedOnTop", False),
            "favoritado": ad.get("isFavorited", False),
            "ultimo_bump": ad.get("lastBumpAgeSecs"),
        })

    # Normalizar categorias
    normalized_cats = []
    for cat in categories:
        extra = cat.get("extraData", {})
        normalized_cats.append({
            "id": cat.get("value"),
            "nome": cat.get("label"),
            "path": extra.get("friendlyPath", "") if extra else "",
            "url": cat.get("href", ""),
        })

    return {
        "total": total if total is not None else 0,
        "pagina": page_index if page_index is not None else 1,
        "total_paginas": page_size if page_size is not None else 50,
        "anuncios": normalized_ads,
        "filtros": filters,
        "categorias": normalized_cats,
        "localizacoes": locations,
    }


def parse_detail(raw: dict) -> dict:
    """
    Processa o resultado de uma página de detalhes OLX.
    Extrai do Schema.org JSON-LD e do markdown.
    """
    result = raw.get("results", [{}])[0]
    html = result.get("html", "")
    md = result.get("markdown", {}).get("raw_markdown", "")

    if not html and not md:
        return {"error": "No content returned", "raw": raw}

    # Tentar Schema.org
    schemas = extract_schema_org(html)
    product = None
    for s in schemas:
        if s.get("@type") == "Product":
            product = s
            break

    if product:
        offers = product.get("offers", {})
        return {
            "id": product.get("identifier"),
            "titulo": product.get("name"),
            "descricao": product.get("description", "").replace("<br>", "\n"),
            "preco": offers.get("price"),
            "moeda": offers.get("priceCurrency"),
            "url": product.get("url"),
            "imagens": [
                img.get("contentUrl", "")
                for img in product.get("image", [])
                if isinstance(img, dict)
            ],
        }

    # Fallback: tentar extrair do markdown
    return {
        "error": "Could not extract structured data",
        "markdown_preview": md[:1000],
    }


def unwrap_cli_envelope(data: dict) -> dict:
    """
    Se os dados vieram do envelope do CLI Printing Press (com 'data' -> 'results'),
    extrai o resultado do Crawl4AI. Se vieram direto do Crawl4AI, retorna como está.
    """
    # Se tem 'data' com 'results' dentro, é envelope do CLI
    inner = data.get("data")
    if isinstance(inner, dict) and "results" in inner:
        return inner
    # Se tem 'results' direto, é Crawl4AI puro
    if "results" in data:
        return data
    # Se 'data' tem os resultados de outra forma
    if "success" in data and "results" not in data and "data" in data:
        return data
    return data


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Extrator de dados OLX")
    parser.add_argument("action", choices=["busca", "detalhe"],
                        help="Tipo de extração")
    parser.add_argument("input_file", help="Arquivo/pipe JSON com resultado do Crawl4AI (pode ser envelope do CLI)")
    parser.add_argument("--output", "-o", help="Arquivo de saída (default: stdout)")

    args = parser.parse_args()

    with open(args.input_file) as f:
        raw_data = json.load(f)

    # Desencapsular se veio do CLI Printing Press
    raw_data = unwrap_cli_envelope(raw_data)

    if args.action == "busca":
        output = parse_listings(raw_data)
    elif args.action == "detalhe":
        output = parse_detail(raw_data)

    output_json = json.dumps(output, indent=2, ensure_ascii=False)

    if args.output:
        with open(args.output, "w") as f:
            f.write(output_json)
        print(f"Salvo em {args.output}")
    else:
        print(output_json)


if __name__ == "__main__":
    main()
