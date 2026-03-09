#!/usr/bin/env python3
"""
Recherche d'entreprises LinkedIn avec filtres optionnels en langage naturel.
"""
import asyncio
import json
import random
import urllib.parse
from typing import Optional
from linkedin_scraper.core.browser import BrowserManager


# ============================================================
# 🗺️  RÉFÉRENTIELS DE FILTRES
# ============================================================

GEO_IDS = {
    # Europe
    "france":               "105015875",
    "belgique":             "100565514",
    "suisse":               "106693272",
    "luxembourg":           "104042105",
    "allemagne":            "101282230",
    "autriche":             "103883259",
    "espagne":              "105646813",
    "italie":               "103350119",
    "portugal":             "105294751",
    "pays-bas":             "104514075",
    "suede":                "105117694",
    "norvege":              "103819153",
    "danemark":             "104514162",
    "finlande":             "100456013",
    "pologne":              "105072130",
    "republique-tcheque":   "104508036",
    "hongrie":              "100288700",
    "roumanie":             "106670623",
    "grece":                "104677530",
    "royaume-uni":          "101165590",
    "irlande":              "104738515",
    # Amérique du Nord
    "etats-unis":           "103644278",
    "canada":               "101174742",
    "mexique":              "103323778",
    # Amérique du Sud
    "bresil":               "106057199",
    "argentine":            "100446943",
    # Asie
    "japon":                "101355337",
    "chine":                "102890883",
    "inde":                 "102713980",
    "coree-du-sud":         "105149290",
    "singapour":            "102454443",
    "emirats-arabes-unis":  "104305776",
    # Océanie
    "australie":            "101452733",
    "nouvelle-zelande":     "105490917",
    # Afrique
    "maroc":                "102047416",
    "tunisie":              "104278506",
    "afrique-du-sud":       "104035573",
}

INDUSTRY_IDS = {
    "software":                 "4",
    "informatique":             "4",
    "it":                       "4",
    "hardware":                 "48",
    "semiconducteurs":          "49",
    "internet":                 "6",
    "telecom":                  "8",
    "jeux-video":               "41",
    "intelligence-artificielle":"1810",
    "finance":                  "43",
    "banque":                   "41",
    "assurance":                "42",
    "capital-risque":           "44",
    "comptabilite":             "50",
    "conseil":                  "96",
    "consulting":               "96",
    "management":               "96",
    "sante":                    "14",
    "medecine":                 "14",
    "pharma":                   "15",
    "biotechnologie":           "16",
    "industrie":                "22",
    "automobile":               "23",
    "aeronautique":             "24",
    "energie":                  "30",
    "marketing":                "80",
    "publicite":                "80",
    "rh":                       "97",
    "recrutement":              "137",
    "juridique":                "74",
    "immobilier":               "44",
    "logistique":               "78",
    "transport":                "77",
    "education":                "69",
    "media":                    "36",
    "presse":                   "36",
    "ecommerce":                "27",
    "retail":                   "27",
    "restauration":             "9",
    "tourisme":                 "53",
    "luxe":                     "60",
    "mode":                     "60",
    "ong":                      "94",
    "association":              "94",
    "gouvernement":             "76",
    "administration":           "76",
}

COMPANY_SIZE_IDS = {
    "1-10":       "A",
    "11-50":      "B",
    "51-200":     "C",
    "201-500":    "D",
    "501-1000":   "E",
    "1001-5000":  "F",
    "5001-10000": "G",
    "10001+":     "H",
}


# ============================================================
# 🔧  RÉSOLUTION DES FILTRES
# ============================================================

def normalize(s: str) -> str:
    """Normalise une chaîne : minuscules, tirets, sans accents."""
    return (
        s.strip().lower()
        .replace(" ", "-")
        .replace("é", "e").replace("è", "e").replace("ê", "e").replace("ë", "e")
        .replace("à", "a").replace("â", "a").replace("ä", "a")
        .replace("ô", "o").replace("ö", "o")
        .replace("ù", "u").replace("û", "u").replace("ü", "u")
        .replace("î", "i").replace("ï", "i")
        .replace("ç", "c").replace("œ", "oe").replace("æ", "ae")
    )


def resolve_filter(value: str, mapping: dict, filter_name: str) -> Optional[str]:
    """Résout un nom lisible en ID LinkedIn."""
    if not value:
        return None

    key = normalize(value)

    # Correspondance exacte
    if key in mapping:
        return mapping[key]

    # ID numérique direct
    if value.strip().isdigit():
        return value.strip()

    # Correspondance partielle
    matches = [(k, v) for k, v in mapping.items() if key in k or k in key]
    if len(matches) == 1:
        print(f"  ℹ️  [{filter_name}] '{value}' → '{matches[0][0]}' (id={matches[0][1]})")
        return matches[0][1]
    elif len(matches) > 1:
        print(f"  ⚠️  [{filter_name}] '{value}' ambigu : {[m[0] for m in matches]} → '{matches[0][0]}' utilisé")
        return matches[0][1]

    print(f"  ⚠️  [{filter_name}] '{value}' non reconnu, filtre ignoré.")
    print(f"      Disponibles : {', '.join(list(mapping.keys())[:12])}...")
    return None


def resolve_sizes(sizes: list) -> list:
    """Résout une liste de tailles en codes LinkedIn."""
    codes = []
    for s in sizes:
        s = s.strip()
        if s.upper() in COMPANY_SIZE_IDS.values():
            codes.append(s.upper())
        elif s in COMPANY_SIZE_IDS:
            codes.append(COMPANY_SIZE_IDS[s])
        else:
            print(f"  ⚠️  Taille '{s}' non reconnue. Valeurs : {list(COMPANY_SIZE_IDS.keys())}")
    return codes


# ============================================================
# 🔗  CONSTRUCTION DE L'URL  ← LE FIX EST ICI
# ============================================================

def build_search_url(geo_id=None, industry_id=None, size_codes=None,
                     keywords="", page=0) -> str:
    """
    Construit l'URL de recherche LinkedIn entreprises.
    Paramètres corrects vérifiés depuis le navigateur :
        - companyHqGeo  (et NON geoUrn qui est pour les personnes/jobs)
        - industryCompanyVertical
        - companyHqSize
    """
    def encode_list_param(ids: list) -> str:
        """Encode ["123"] → %5B%22123%22%5D comme LinkedIn le fait."""
        inner = ",".join(f'"{i}"' for i in ids)
        raw = f"[{inner}]"
        return urllib.parse.quote(raw, safe="")

    parts = []

    if keywords:
        parts.append(f"keywords={urllib.parse.quote(keywords)}")
    parts.append("origin=FACETED_SEARCH")           # LinkedIn l'ajoute toujours
    if geo_id:
        parts.append(f"companyHqGeo={encode_list_param([geo_id])}")   # ← FIX
    if industry_id:
        parts.append(f"industryCompanyVertical={encode_list_param([industry_id])}")
    if size_codes:
        parts.append(f"companyHqSize={encode_list_param(size_codes)}")
    if page > 0:
        parts.append(f"start={page * 10}")

    base = "https://www.linkedin.com/search/results/companies/"
    return base + ("?" + "&".join(parts) if parts else "")


# ============================================================
# 🕷️  SCRAPING
# ============================================================

async def extract_company_urls_from_page(page) -> list:
    """Extrait les URLs des entreprises depuis une page de résultats."""
    urls = []
    try:
        await page.wait_for_selector('a[href*="/company/"]', timeout=10000)
        await asyncio.sleep(1)

        links = await page.locator('a[href*="/company/"]').all()
        seen = set()

        for link in links:
            href = await link.get_attribute("href")
            if not href:
                continue
            clean = href.split("?")[0].rstrip("/")
            parts = clean.split("/")
            if (
                "company" in parts
                and len(parts) >= 5
                and parts[-1] != "company"
                and clean not in seen
                and not any(sub in clean for sub in ["/jobs", "/posts", "/people", "/about", "/life"])
            ):
                if not clean.startswith("http"):
                    clean = "https://www.linkedin.com" + clean
                seen.add(clean)
                urls.append(clean)

    except Exception as e:
        print(f"  ⚠️ Erreur extraction URLs : {e}")

    return urls


async def scrape_company_details(page, linkedin_url: str) -> dict:
    """Scrape les infos /about/ d'une entreprise."""
    url_about = linkedin_url.rstrip("/") + "/about/"
    await page.goto(url_about, wait_until="domcontentloaded")
    await asyncio.sleep(random.uniform(2, 4))

    result = {
        "linkedin_url": linkedin_url,
        "name": None, "about_us": None, "website": None,
        "headquarters": None, "founded": None, "industry": None,
        "company_type": None, "company_size": None, "specialties": None,
    }

    try:
        result["name"] = (await page.locator("h1").first.inner_text()).strip()
    except Exception:
        pass

    try:
        sections = await page.locator("section").all()
        for section in sections:
            text = await section.inner_text()
            if any(kw in text[:60] for kw in ["Vue d'ensemble", "Overview", "À propos"]):
                paras = await section.locator("p").all()
                texts = [(await p.inner_text()).strip() for p in paras]
                best = max(texts, key=len, default="")
                if best:
                    result["about_us"] = best
                    break
    except Exception:
        pass

    LABEL_MAP = {
        "site web": "website",      "website": "website",
        "siège social": "headquarters", "headquarters": "headquarters",
        "fondée": "founded",        "founded": "founded",
        "secteur": "industry",      "industry": "industry",
        "type": "company_type",
        "taille": "company_size",   "company size": "company_size",
        "spécialisations": "specialties", "specialties": "specialties",
    }
    try:
        dts = await page.locator("dt").all()
        for dt in dts:
            label = (await dt.inner_text()).strip().lower()
            field = next((v for k, v in LABEL_MAP.items() if k in label), None)
            if not field:
                continue
            dd = dt.locator("xpath=following-sibling::dd[1]")
            if await dd.count() == 0:
                continue
            if field == "website":
                a_tag = dd.locator("a").first
                if await a_tag.count() > 0:
                    href = await a_tag.get_attribute("href") or ""
                    if "redirect" in href:
                        parsed = urllib.parse.urlparse(href)
                        params = urllib.parse.parse_qs(parsed.query)
                        href = urllib.parse.unquote(params.get("url", [href])[0])
                    result["website"] = href
            else:
                lines = [l.strip() for l in (await dd.inner_text()).strip().split("\n") if l.strip()]
                if lines:
                    result[field] = lines[0]
    except Exception:
        pass

    return result


# ============================================================
# 🚀  FONCTION PRINCIPALE
# ============================================================

async def search_companies(
    pays: str = "",
    secteur: str = "",
    taille: list = None,
    keywords: str = "",
    max_companies: int = 20,
    scrape_details: bool = True,
):
    """
    Recherche des entreprises LinkedIn avec des filtres en langage naturel.
    Tous les filtres sont optionnels.

    Args:
        pays:           "france", "suede", "belgique"... ou "" pour tous
        secteur:        "software", "conseil", "sante"... ou "" pour tous
        taille:         ["11-50", "51-200"]... ou [] / None pour toutes
        keywords:       "data", "startup"... ou "" pour aucun
        max_companies:  Nombre max d'entreprises à récupérer
        scrape_details: True = scrape les infos /about/ de chaque entreprise
    """
    print("\n" + "=" * 60)
    print("  🔍 Recherche d'entreprises LinkedIn")
    print("=" * 60)

    geo_id = resolve_filter(pays, GEO_IDS, "pays") if pays else None
    industry_id = resolve_filter(secteur, INDUSTRY_IDS, "secteur") if secteur else None
    size_codes = resolve_sizes(taille) if taille else None

    print(f"  Pays        : {pays or '(tous)'}" + (f"  → id={geo_id}" if geo_id else ""))
    print(f"  Secteur     : {secteur or '(tous)'}" + (f"  → id={industry_id}" if industry_id else ""))
    print(f"  Taille      : {', '.join(taille) if taille else '(toutes)'}" + (f"  → {size_codes}" if size_codes else ""))
    print(f"  Keywords    : {keywords or '(aucun)'}")
    print(f"  Max résultats: {max_companies}")

    # Vérification : afficher l'URL exacte qui sera utilisée
    test_url = build_search_url(geo_id, industry_id, size_codes, keywords, page=0)
    print(f"\n  🔗 URL page 1 : {test_url}")
    print("=" * 60 + "\n")

    async with BrowserManager(headless=False, slow_mo=100) as browser:
        await browser.load_session("linkedin_session.json")
        print("✓ Session chargée\n")

        all_company_urls = []
        page_num = 0

        print("📋 Collecte des URLs d'entreprises...")
        while len(all_company_urls) < max_companies:
            search_url = build_search_url(geo_id, industry_id, size_codes, keywords, page=page_num)
            print(f"  → Page {page_num + 1}")
            await browser.page.goto(search_url, wait_until="domcontentloaded")
            await asyncio.sleep(random.uniform(2, 3))

            urls = await extract_company_urls_from_page(browser.page)
            new_urls = [u for u in urls if u not in all_company_urls]
            all_company_urls.extend(new_urls)
            print(f"     +{len(new_urls)} nouvelles (total: {len(all_company_urls)})")

            if not new_urls:
                print("  ⚠️ Plus de résultats, arrêt.")
                break

            page_num += 1
            await asyncio.sleep(random.uniform(1.5, 3))

        all_company_urls = all_company_urls[:max_companies]
        print(f"\n✅ {len(all_company_urls)} URLs collectées\n")

        results = []
        if scrape_details:
            print("🏢 Scraping des détails...\n")
            for i, url in enumerate(all_company_urls, 1):
                print(f"  [{i:2d}/{len(all_company_urls)}] {url}")
                try:
                    company = await scrape_company_details(browser.page, url)
                    results.append(company)
                    print(f"         → {company.get('name', '?')} | {company.get('industry', '?')} | {company.get('company_size', '?')}")
                except Exception as e:
                    print(f"         ⚠️ Erreur : {e}")
                    results.append({"linkedin_url": url, "error": str(e)})
                await asyncio.sleep(random.uniform(3, 6))
        else:
            results = [{"linkedin_url": u} for u in all_company_urls]

        with open("output_search_results.json", "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        print(f"\n{'=' * 60}")
        print(f"✅ {len(results)} entreprises → output_search_results.json")
        print("=" * 60)

        return results


if __name__ == "__main__":
    asyncio.run(search_companies(
        pays="france",
        secteur="conseil",
        taille=[],
        keywords="data",
        max_companies=2,
        scrape_details=True,
    ))