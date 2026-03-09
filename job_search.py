#!/usr/bin/env python3
"""
Recherche d'offres d'emploi LinkedIn avec filtres optionnels.
Tous les filtres sont optionnels.
"""
import asyncio
import json
import random
import urllib.parse
from typing import Optional
from linkedin_scraper.core.browser import BrowserManager
from linkedin_scraper.scrapers.job import JobScraper


# ============================================================
# 🗺️  RÉFÉRENTIELS DE FILTRES
# ============================================================

# Même GEO_IDS que company_search.py (geoId pour les jobs)
GEO_IDS = {
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
    "royaume-uni":          "101165590",
    "irlande":              "104738515",
    "etats-unis":           "103644278",
    "canada":               "101174742",
    "mexique":              "103323778",
    "bresil":               "106057199",
    "argentine":            "100446943",
    "japon":                "101355337",
    "chine":                "102890883",
    "inde":                 "102713980",
    "singapour":            "102454443",
    "emirats-arabes-unis":  "104305776",
    "australie":            "101452733",
    "maroc":                "102047416",
    "tunisie":              "104278506",
}

# f_TPR — Ancienneté de l'offre
DATE_POSTED = {
    "24h":      "r86400",
    "semaine":  "r604800",
    "mois":     "r2592000",
}

# f_WT — Mode de travail
WORKPLACE_TYPE = {
    "presentiel":   "1",
    "sur-site":     "1",
    "on-site":      "1",
    "hybride":      "2",
    "hybrid":       "2",
    "remote":       "3",
    "teletravail":  "3",
    "distanciel":   "3",
}

# f_JT — Type de contrat
JOB_TYPE = {
    "cdi":          "F",
    "full-time":    "F",
    "temps-plein":  "F",
    "cdd":          "C",
    "contract":     "C",
    "contrat":      "C",
    "temps-partiel":"P",
    "part-time":    "P",
    "stage":        "I",
    "internship":   "I",
    "interim":      "T",
    "temporary":    "T",
    "benevole":     "V",
    "volunteer":    "V",
}

# f_E — Niveau d'expérience
EXPERIENCE_LEVEL = {
    "stage":            "1",
    "internship":       "1",
    "debutant":         "2",
    "junior":           "2",
    "entry":            "2",
    "entry-level":      "2",
    "associe":          "3",
    "associate":        "3",
    "confirme":         "4",
    "senior":           "4",
    "mid-senior":       "4",
    "manager":          "4",
    "directeur":        "5",
    "director":         "5",
    "executif":         "6",
    "executive":        "6",
    "vp":               "6",
}


# ============================================================
# 🔧  UTILITAIRES
# ============================================================

def normalize(s: str) -> str:
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


def resolve(value: str, mapping: dict, name: str) -> Optional[str]:
    if not value:
        return None
    key = normalize(value)
    if key in mapping:
        return mapping[key]
    # Correspondance partielle
    matches = [(k, v) for k, v in mapping.items() if key in k or k in key]
    if len(matches) == 1:
        print(f"  ℹ️  [{name}] '{value}' → '{matches[0][0]}'")
        return matches[0][1]
    elif len(matches) > 1:
        print(f"  ⚠️  [{name}] '{value}' ambigu : {[m[0] for m in matches]} → '{matches[0][0]}' utilisé")
        return matches[0][1]
    print(f"  ⚠️  [{name}] '{value}' non reconnu, ignoré. Valeurs : {list(mapping.keys())[:8]}...")
    return None


def resolve_multi(values: list, mapping: dict, name: str) -> list:
    """Résout une liste de valeurs."""
    return [r for v in values if (r := resolve(v, mapping, name)) is not None]


def build_job_search_url(keywords="", geo_id=None, date_posted=None,
                         workplace_codes=None, job_type_codes=None,
                         experience_codes=None, page=0) -> str:
    """
    Construit l'URL de recherche d'offres LinkedIn.
    Uniquement les filtres non-vides sont ajoutés.
    """
    parts = []

    if keywords:
        parts.append(f"keywords={urllib.parse.quote(keywords)}")
    if geo_id:
        parts.append(f"geoId={geo_id}")
    if date_posted:
        parts.append(f"f_TPR={date_posted}")
    if workplace_codes:
        parts.append(f"f_WT={','.join(workplace_codes)}")
    if job_type_codes:
        parts.append(f"f_JT={','.join(job_type_codes)}")
    if experience_codes:
        parts.append(f"f_E={','.join(experience_codes)}")
    if page > 0:
        parts.append(f"start={page * 25}")

    base = "https://www.linkedin.com/jobs/search/"
    return base + ("?" + "&".join(parts) if parts else "")


# ============================================================
# 🕷️  SCRAPING
# ============================================================

async def extract_job_urls_from_page(page) -> list:
    """Extrait les URLs des offres depuis une page de résultats."""
    urls = []
    try:
        await page.wait_for_selector('a[href*="/jobs/view/"]', timeout=10000)
        await asyncio.sleep(1)

        # Scroll pour charger toutes les offres lazy-loaded
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
        await asyncio.sleep(1)
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(1)

        links = await page.locator('a[href*="/jobs/view/"]').all()
        seen = set()
        for link in links:
            href = await link.get_attribute("href")
            if not href:
                continue
            clean = href.split("?")[0].rstrip("/")
            if not clean.startswith("http"):
                clean = "https://www.linkedin.com" + clean
            if "/jobs/view/" in clean and clean not in seen:
                seen.add(clean)
                urls.append(clean)
    except Exception as e:
        print(f"  ⚠️ Erreur extraction URLs offres : {e}")
    return urls


async def scrape_job_details(page, job_url: str) -> dict:
    """Scrape les détails d'une offre d'emploi."""
    await page.goto(job_url, wait_until="domcontentloaded")
    await asyncio.sleep(random.uniform(2, 3))

    result = {
        "linkedin_url": job_url,
        "job_title": None,
        "company": None,
        "company_linkedin_url": None,
        "location": None,
        "workplace_type": None,
        "posted_date": None,
        "applicant_count": None,
        "job_type": None,
        "experience_level": None,
        "job_description": None,
    }

    # Titre
    try:
        result["job_title"] = (await page.locator("h1").first.inner_text()).strip()
    except Exception:
        pass

    # Entreprise + URL entreprise
    try:
        company_links = await page.locator('a[href*="/company/"]').all()
        for link in company_links:
            text = (await link.inner_text()).strip()
            if text and len(text) > 1:
                result["company"] = text
                href = await link.get_attribute("href") or ""
                clean = href.split("?")[0]
                if not clean.startswith("http"):
                    clean = "https://www.linkedin.com" + clean
                result["company_linkedin_url"] = clean
                break
    except Exception:
        pass

    # Infos sous le titre (localisation, type de travail, etc.)
    try:
        # LinkedIn groupe ces infos dans des <span> sous le h1
        info_spans = await page.locator(
            ".job-details-jobs-unified-top-card__primary-description-container span, "
            ".jobs-unified-top-card__subtitle-primary-grouping span, "
            "h1 ~ div span, h1 ~ p span"
        ).all()
        info_texts = []
        for span in info_spans:
            t = (await span.inner_text()).strip()
            if t and t not in ("·", "•", "") and len(t) > 1:
                info_texts.append(t)

        for t in info_texts:
            tl = t.lower()
            if any(w in tl for w in ["remote", "hybride", "hybrid", "on-site", "présentiel", "télétravail"]):
                result["workplace_type"] = t
            elif any(w in tl for w in ["il y a", "ago", "heure", "jour", "semaine", "mois", "hour", "day", "week"]):
                result["posted_date"] = t
            elif any(w in tl for w in ["candidat", "applicant", "postulant"]):
                result["applicant_count"] = t
            elif result["location"] is None and ("," in t or any(c.isupper() for c in t[1:])):
                result["location"] = t
    except Exception:
        pass

    # Description du poste
    try:
        desc_selectors = [
            ".jobs-description__content",
            ".jobs-description",
            "#job-details",
            "article",
        ]
        for sel in desc_selectors:
            elem = page.locator(sel).first
            if await elem.count() > 0:
                text = (await elem.inner_text()).strip()
                if len(text) > 100:
                    result["job_description"] = text[:3000]
                    break
    except Exception:
        pass

    return result


# ============================================================
# 🚀  FONCTION PRINCIPALE
# ============================================================

async def search_jobs(
    keywords: str = "",
    pays: str = "",
    date_publiee: str = "",
    mode_travail: list = None,
    type_contrat: list = None,
    niveau_experience: list = None,
    max_offres: int = 20,
    scrape_details: bool = True,
):
    """
    Recherche des offres d'emploi LinkedIn avec filtres en langage naturel.
    Tous les filtres sont optionnels.

    Args:
        keywords:           "data analyst", "python developer"... ou "" pour tous
        pays:               "france", "belgique"... ou "" pour tous
        date_publiee:       "24h", "semaine", "mois" ou "" pour toutes
        mode_travail:       ["remote"], ["hybride", "presentiel"] ou [] pour tous
        type_contrat:       ["cdi"], ["stage", "cdd"] ou [] pour tous
        niveau_experience:  ["junior"], ["senior", "manager"] ou [] pour tous
        max_offres:         Nombre max d'offres à récupérer
        scrape_details:     True = scrape le détail de chaque offre
    """
    print("\n" + "=" * 60)
    print("  💼 Recherche d'offres d'emploi LinkedIn")
    print("=" * 60)

    geo_id          = resolve(pays, GEO_IDS, "pays") if pays else None
    date_code       = resolve(date_publiee, DATE_POSTED, "date") if date_publiee else None
    workplace_codes = resolve_multi(mode_travail or [], WORKPLACE_TYPE, "mode_travail")
    job_type_codes  = resolve_multi(type_contrat or [], JOB_TYPE, "type_contrat")
    exp_codes       = resolve_multi(niveau_experience or [], EXPERIENCE_LEVEL, "experience")

    print(f"  Keywords    : {keywords or '(tous)'}")
    print(f"  Pays        : {pays or '(tous)'}" + (f" → {geo_id}" if geo_id else ""))
    print(f"  Publié      : {date_publiee or '(toutes dates)'}")
    print(f"  Mode travail: {mode_travail or '(tous)'}")
    print(f"  Contrat     : {type_contrat or '(tous)'}")
    print(f"  Expérience  : {niveau_experience or '(tous niveaux)'}")
    print(f"  Max offres  : {max_offres}")

    test_url = build_job_search_url(keywords, geo_id, date_code, workplace_codes, job_type_codes, exp_codes)
    print(f"\n  🔗 URL page 1 : {test_url}")
    print("=" * 60 + "\n")

    async with BrowserManager(headless=False, slow_mo=100) as browser:
        await browser.load_session("linkedin_session.json")
        print("✓ Session chargée\n")

        all_job_urls = []
        page_num = 0

        print("📋 Collecte des URLs d'offres...")
        while len(all_job_urls) < max_offres:
            search_url = build_job_search_url(
                keywords, geo_id, date_code,
                workplace_codes, job_type_codes, exp_codes, page=page_num
            )
            print(f"  → Page {page_num + 1}")
            await browser.page.goto(search_url, wait_until="domcontentloaded")
            await asyncio.sleep(random.uniform(2, 3))

            urls = await extract_job_urls_from_page(browser.page)
            new_urls = [u for u in urls if u not in all_job_urls]
            all_job_urls.extend(new_urls)
            print(f"     +{len(new_urls)} nouvelles (total: {len(all_job_urls)})")

            if not new_urls:
                print("  ⚠️ Plus de résultats, arrêt.")
                break

            page_num += 1
            await asyncio.sleep(random.uniform(1.5, 2.5))

        all_job_urls = all_job_urls[:max_offres]
        print(f"\n✅ {len(all_job_urls)} URLs collectées\n")

        results = []
        if scrape_details:
            print("🔎 Scraping des détails de chaque offre...\n")
            for i, url in enumerate(all_job_urls, 1):
                print(f"  [{i:2d}/{len(all_job_urls)}] {url}")
                try:
                    job = await scrape_job_details(browser.page, url)
                    results.append(job)
                    print(f"         → {job.get('job_title', '?')} | {job.get('company', '?')} | {job.get('location', '?')}")
                except Exception as e:
                    print(f"         ⚠️ Erreur : {e}")
                    results.append({"linkedin_url": url, "error": str(e)})
                await asyncio.sleep(random.uniform(2, 4))
        else:
            results = [{"linkedin_url": u} for u in all_job_urls]

        with open("output_jobs.json", "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        print(f"\n{'=' * 60}")
        print(f"✅ {len(results)} offres → output_jobs.json")
        print("=" * 60)
        return results


if __name__ == "__main__":
    asyncio.run(search_jobs(
        keywords="data analyst",
        pays="france",
        date_publiee="semaine",
        mode_travail=["hybride", "remote"],
        type_contrat=["cdi"],
        niveau_experience=["junior", "confirme"],
        max_offres=2,
        scrape_details=True,
    ))