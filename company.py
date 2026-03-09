#!/usr/bin/env python3
"""
Version corrigée du scraping entreprise.
Basée sur l'inspection réelle de la page LinkedIn (labels en FR + EN).
"""
import asyncio
import json
from linkedin_scraper.core.browser import BrowserManager

COMPANY_URL = "https://www.linkedin.com/company/microsoft/"


async def scrape_company_manual(page, linkedin_url: str) -> dict:
    url_about = linkedin_url.rstrip("/") + "/about/"
    await page.goto(url_about, wait_until="domcontentloaded")
    await asyncio.sleep(3)

    result = {
        "linkedin_url": linkedin_url,
        "name": None,
        "about_us": None,
        "website": None,
        "phone": None,
        "headquarters": None,
        "founded": None,
        "industry": None,
        "company_type": None,
        "company_size": None,
        "specialties": None,
    }

    # --- Nom ---
    try:
        result["name"] = (await page.locator("h1").first.inner_text()).strip()
    except Exception:
        pass

    # --- About us ---
    # Le texte "Vue d'ensemble" précède le paragraphe about dans la page.
    # On cible la section qui contient "Vue d'ensemble" et on prend ses <p>
    try:
        sections = await page.locator("section").all()
        for section in sections:
            text = await section.inner_text()
            # La section about contient ce header sur la page LinkedIn FR
            if any(kw in text[:60] for kw in ["Vue d'ensemble", "Overview", "À propos"]):
                paras = await section.locator("p").all()
                # Prendre le plus long paragraphe (le vrai "about", pas un label)
                best = ""
                for p in paras:
                    content = (await p.inner_text()).strip()
                    if len(content) > len(best):
                        best = content
                if best:
                    result["about_us"] = best
                    break
    except Exception as e:
        print(f"  ⚠️ about_us error: {e}")

    # --- Overview via dt/dd (labels FR + EN) ---
    # Labels observés sur la page réelle :
    #   FR : Site web, Secteur, Taille de l'entreprise, Siège social, Spécialisations
    #   EN : Website, Industry, Company size, Headquarters, Specialties
    LABEL_MAP = {
        # website
        "site web": "website",
        "website": "website",
        # phone
        "téléphone": "phone",
        "phone": "phone",
        # headquarters
        "siège social": "headquarters",
        "siège": "headquarters",
        "headquarters": "headquarters",
        "location": "headquarters",
        # founded
        "fondée": "founded",
        "created": "founded",
        "founded": "founded",
        # industry
        "secteur": "industry",
        "industry": "industry",
        "industries": "industry",
        # company type
        "type d'entreprise": "company_type",
        "company type": "company_type",
        "type": "company_type",
        # company size
        "taille de l'entreprise": "company_size",
        "taille": "company_size",
        "company size": "company_size",
        # specialties
        "spécialisations": "specialties",
        "specialties": "specialties",
        "specialization": "specialties",
    }

    try:
        dts = await page.locator("dt").all()
        for dt in dts:
            label_raw = (await dt.inner_text()).strip()
            label = label_raw.lower()

            # Chercher la clé correspondante (correspondance partielle)
            field = None
            for key, val in LABEL_MAP.items():
                if key in label:
                    field = val
                    break
            if field is None:
                continue

            # Récupérer le <dd> suivant
            dd = dt.locator("xpath=following-sibling::dd[1]")
            if await dd.count() == 0:
                continue

            # Pour le site web : chercher le href dans le <a> en priorité
            if field == "website":
                a_tag = dd.locator("a").first
                if await a_tag.count() > 0:
                    href = await a_tag.get_attribute("href")
                    # LinkedIn redirige via /redir/redirect?url=... — extraire l'URL réelle
                    if href and "redirect" in href:
                        import urllib.parse
                        parsed = urllib.parse.urlparse(href)
                        params = urllib.parse.parse_qs(parsed.query)
                        url_real = params.get("url", [href])[0]
                        result["website"] = urllib.parse.unquote(url_real)
                    elif href:
                        result["website"] = href
                else:
                    result["website"] = (await dd.inner_text()).strip().split("\n")[0]
            else:
                # Pour les autres champs : prendre la première ligne du texte
                # (évite de récupérer le texte des sous-éléments parasites)
                dd_text = (await dd.inner_text()).strip()
                # Garder seulement la première ligne non vide
                lines = [l.strip() for l in dd_text.split("\n") if l.strip()]
                if lines:
                    result[field] = lines[0]

    except Exception as e:
        print(f"  ⚠️ dt/dd parsing error: {e}")

    return result


async def main():
    print(f"\n🔍 Scraping entreprise : {COMPANY_URL}\n")

    async with BrowserManager(headless=False, slow_mo=200) as browser:
        await browser.load_session("linkedin_session.json")
        print("✓ Session chargée")

        company = await scrape_company_manual(browser.page, COMPANY_URL)

        print("\n" + "=" * 55)
        for key, value in company.items():
            if value:
                preview = str(value)[:80] + ("..." if len(str(value)) > 80 else "")
                print(f"  {key:20s} : {preview}")
            else:
                print(f"  {key:20s} : ❌ non récupéré")
        print("=" * 55)

        with open("output_company_fixed.json", "w", encoding="utf-8") as f:
            json.dump(company, f, ensure_ascii=False, indent=2)
        print("\n💾 Sauvegardé dans output_company_fixed.json")


if __name__ == "__main__":
    asyncio.run(main())