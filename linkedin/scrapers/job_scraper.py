"""
JobScraper — scrapes a LinkedIn job offer detail page via Playwright.

Stratégie :
  - Playwright navigue directement vers la page de l'offre (session authentifiée).
  - On extrait les données depuis le DOM rendu avec des sélecteurs CSS robustes
    et de multiples fallbacks (identique à la stratégie qui fonctionne pour les titres).
"""
import asyncio
import random
import re


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _strip_tags(html: str) -> str:
    """Supprime les balises HTML et décode les entités basiques."""
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&#(\d+);", lambda m: chr(int(m.group(1))), text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


async def _try_selectors(page, selectors: list[str]) -> str | None:
    """Essaie chaque sélecteur CSS dans l'ordre et retourne le premier texte trouvé."""
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if await loc.count() > 0:
                text = await loc.inner_text()
                text = text.strip()
                if text:
                    return text
        except Exception:
            continue
    return None


async def _try_attr_selectors(page, selectors: list[tuple[str, str]]) -> str | None:
    """Essaie chaque (sélecteur, attribut) dans l'ordre et retourne la première valeur trouvée."""
    for sel, attr in selectors:
        try:
            loc = page.locator(sel).first
            if await loc.count() > 0:
                val = await loc.get_attribute(attr)
                if val and val.strip():
                    return val.strip()
        except Exception:
            continue
    return None


class JobScraper:
    """
    Scrape les offres d'emploi LinkedIn via Playwright (session authentifiée).

    Instanciation :
        scraper = JobScraper(page, context)
    """

    # Criteria labels (FR + EN) → normalized field name
    CRITERIA_MAP = {
        "seniority level":     "seniority_level",
        "niveau de séniorité": "seniority_level",
        "niveau":              "seniority_level",
        "employment type":     "employment_type",
        "type d'emploi":       "employment_type",
        "type de poste":       "employment_type",
        "job function":        "job_function",
        "fonction":            "job_function",
        "domaine":             "job_function",
        "industries":          "industries",
        "industrie":           "industries",
        "secteur":             "industries",
    }

    def __init__(self, page, context=None) -> None:
        self.page = page
        self.context = context

    # ------------------------------------------------------------------
    # Point d'entrée principal
    # ------------------------------------------------------------------

    async def scrape(self, linkedin_url: str) -> dict:
        """
        Scrape une offre d'emploi LinkedIn.

        Args:
            linkedin_url: URL complète, ex. "https://www.linkedin.com/jobs/view/1234567890/"

        Returns:
            Dict avec les champs : linkedin_url, title, company_name, company_url,
            location, posted_time, applicants_count, description,
            seniority_level, employment_type, job_function, industries.
        """
        result = {
            "linkedin_url":     linkedin_url,
            "title":            None,
            "company_name":     None,
            "company_url":      None,
            "location":         None,
            "posted_time":      None,
            "applicants_count": None,
            "description":      None,
            "seniority_level":  None,
            "employment_type":  None,
            "job_function":     None,
            "industries":       None,
        }

        try:
            # domcontentloaded uniquement — networkidle bloque sur LinkedIn (polling permanent)
            await self.page.goto(linkedin_url, wait_until="domcontentloaded", timeout=30000)

            # Attendre qu'Ember rende le contenu : essayer plusieurs ancres dans l'ordre
            for anchor_sel in [
                "h1",
                ".jobs-unified-top-card",
                ".jobs-details__main-content",
                "[data-job-id]",
                "section.core-rail",
                ".job-view-layout",
            ]:
                try:
                    await self.page.wait_for_selector(anchor_sel, timeout=8000)
                    break
                except Exception:
                    continue
            else:
                await asyncio.sleep(4)

            # Scroll pour déclencher le lazy-load des sections
            await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight / 3)")
            await asyncio.sleep(0.7)
            await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
            await asyncio.sleep(0.7)
            await self.page.evaluate("window.scrollTo(0, 0)")
            await asyncio.sleep(0.5)

            await self._extract_all(result)

        except Exception as e:
            print(f"  ⚠️ Erreur scraping {linkedin_url} : {e}")

        return result

    # ------------------------------------------------------------------
    # Extraction de tous les champs
    # ------------------------------------------------------------------

    async def _extract_all(self, result: dict) -> None:
        page = self.page

        # --- Titre ---
        title = await _try_selectors(page, [
            "h1.topcard__title",
            "h1.t-24.t-bold.inline",
            "h1.t-24",
            "h1[class*='job-title']",
            "h1",
        ])
        if not title:
            # Fallback balise <title>
            title_tag = await page.title()
            if title_tag:
                title = re.sub(r"\s*[|\-–].*LinkedIn.*$", "", title_tag).strip()
        if title:
            result["title"] = title

        # --- Entreprise (nom + URL) ---
        company_url = await _try_attr_selectors(page, [
            ("a.topcard__org-name-link", "href"),
            ("a[data-tracking-control-name*='company']", "href"),
            (".job-details-jobs-unified-top-card__company-name a", "href"),
            (".topcard__flavor--black-link", "href"),
        ])
        company_name = await _try_selectors(page, [
            "a.topcard__org-name-link",
            ".job-details-jobs-unified-top-card__company-name a",
            ".job-details-jobs-unified-top-card__company-name",
            "a[data-tracking-control-name*='company']",
            ".topcard__flavor--black-link",
            "span.topcard__flavor a",
        ])
        if company_url:
            result["company_url"] = company_url.split("?")[0]
        if company_name:
            result["company_name"] = company_name.strip()

        # --- Localisation ---
        location = await _try_selectors(page, [
            "span.topcard__flavor--bullet",
            ".job-details-jobs-unified-top-card__bullet",
            ".job-details-jobs-unified-top-card__workplace-type",
            "span[class*='location']",
            ".topcard__flavor:not(a)",
        ])
        if location:
            result["location"] = location

        # --- Date de publication ---
        posted = await _try_selectors(page, [
            "span.posted-time-ago__text",
            "span[class*='posted-time']",
            ".job-details-jobs-unified-top-card__posted-date",
            "span[class*='time-ago']",
            "time",
        ])
        if posted:
            result["posted_time"] = posted

        # --- Nombre de candidats ---
        applicants = await _try_selectors(page, [
            "span.num-applicants__caption",
            "span[class*='num-applicants']",
            ".job-details-jobs-unified-top-card__applicant-count",
            "span[class*='applicant']",
            "figcaption[class*='applicant']",
        ])
        if applicants:
            result["applicants_count"] = applicants

        # --- Description ---
        # Essayer d'abord de cliquer sur "Voir plus" pour déplier la description
        try:
            see_more = page.locator(
                "button.show-more-less-html__button, "
                "button[aria-label*='more'], "
                "button[class*='show-more']"
            ).first
            if await see_more.count() > 0:
                await see_more.click()
                await asyncio.sleep(0.5)
        except Exception:
            pass

        description = await _try_selectors(page, [
            "div.show-more-less-html__markup",
            "div[class*='show-more-less-html__markup']",
            ".job-details-jobs-unified-top-card__job-insight",
            "div.description__text",
            "section.description div",
            "#job-details",
            "div[class*='description']",
        ])
        if description:
            result["description"] = description

        # --- Critères (séniorité, type contrat, fonction, secteur) ---
        await self._extract_criteria(result)

    # ------------------------------------------------------------------
    # Extraction des critères structurés
    # ------------------------------------------------------------------

    async def _extract_criteria(self, result: dict) -> None:
        page = self.page

        # Stratégie 1 : liste <li> avec header h3 + span valeur
        criteria_items = page.locator(
            "li.description__job-criteria-item, "
            "li[class*='job-criteria-item']"
        )
        count = await criteria_items.count()
        if count > 0:
            for i in range(count):
                item = criteria_items.nth(i)
                try:
                    header_el = item.locator(
                        "h3.description__job-criteria-subheader, "
                        "h3[class*='job-criteria-subheader'], "
                        "span[class*='criteria-label'], "
                        "h3, dt"
                    ).first
                    value_el = item.locator(
                        "span.description__job-criteria-text, "
                        "span[class*='job-criteria-text'], "
                        "span[class*='criteria-value'], "
                        "span:not(h3 span), dd"
                    ).first

                    header_text = ""
                    value_text = ""
                    if await header_el.count() > 0:
                        header_text = (await header_el.inner_text()).strip().lower()
                    if await value_el.count() > 0:
                        value_text = (await value_el.inner_text()).strip()

                    if header_text and value_text:
                        for key, field in self.CRITERIA_MAP.items():
                            if key in header_text:
                                result[field] = value_text
                                break
                except Exception:
                    continue
            return

        # Stratégie 2 : sections "insight" unifiées (nouvelle UI LinkedIn)
        insight_items = page.locator(
            "li.job-details-jobs-unified-top-card__job-insight, "
            "li[class*='job-insight'], "
            "span[class*='job-insight']"
        )
        count2 = await insight_items.count()
        if count2 > 0:
            for i in range(count2):
                item = insight_items.nth(i)
                try:
                    text = (await item.inner_text()).strip().lower()
                    # Heuristiques simples sur le texte brut
                    if any(k in text for k in ["temps plein", "full-time", "part-time", "cdi", "cdd", "stage", "alternance"]):
                        if not result["employment_type"]:
                            result["employment_type"] = (await item.inner_text()).strip()
                    if any(k in text for k in ["junior", "senior", "confirmé", "mid-senior", "entry"]):
                        if not result["seniority_level"]:
                            result["seniority_level"] = (await item.inner_text()).strip()
                except Exception:
                    continue

        # Stratégie 3 : extraire depuis le HTML brut de la page
        try:
            html = await page.content()
            await self._extract_criteria_from_html(html, result)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Extraction critères depuis le HTML brut (fallback regex)
    # ------------------------------------------------------------------

    async def _extract_criteria_from_html(self, html: str, result: dict) -> None:
        # Nouvelle UI : data-test-id ou attributs aria
        patterns_criteria = [
            # Format "label : valeur" dans le HTML
            (r'<span[^>]*>\s*(Niveau d[^<]*|Seniority[^<]*)\s*</span>\s*<span[^>]*>\s*([^<]+)\s*</span>', "seniority_level"),
            (r'<span[^>]*>\s*(Type d.emploi|Employment type[^<]*)\s*</span>\s*<span[^>]*>\s*([^<]+)\s*</span>', "employment_type"),
            (r'<span[^>]*>\s*(Fonction|Job function[^<]*)\s*</span>\s*<span[^>]*>\s*([^<]+)\s*</span>', "job_function"),
            (r'<span[^>]*>\s*(Secteur[^<]*|Industri[^<]*)\s*</span>\s*<span[^>]*>\s*([^<]+)\s*</span>', "industries"),
        ]

        for pattern, field in patterns_criteria:
            if result[field]:
                continue
            m = re.search(pattern, html, re.DOTALL | re.IGNORECASE)
            if m:
                result[field] = _strip_tags(m.group(2))

        # Entreprise fallback via regex HTML
        if not result["company_name"]:
            m = re.search(
                r'<a[^>]*(?:topcard__org-name-link|company)[^>]*href="([^"?]+)[^"]*"[^>]*>(.*?)</a>',
                html, re.DOTALL | re.IGNORECASE
            )
            if m:
                result["company_url"] = m.group(1).split("?")[0]
                result["company_name"] = _strip_tags(m.group(2))

        # Localisation fallback
        if not result["location"]:
            m = re.search(
                r'<span[^>]*topcard__flavor--bullet[^>]*>(.*?)</span>',
                html, re.DOTALL
            )
            if m:
                result["location"] = _strip_tags(m.group(1))

        # Posted time fallback
        if not result["posted_time"]:
            m = re.search(
                r'<span[^>]*posted-time-ago__text[^>]*>(.*?)</span>',
                html, re.DOTALL
            )
            if m:
                result["posted_time"] = _strip_tags(m.group(1))

        # Applicants fallback
        if not result["applicants_count"]:
            m = re.search(
                r'<span[^>]*num-applicants__caption[^>]*>(.*?)</span>',
                html, re.DOTALL
            )
            if m:
                result["applicants_count"] = _strip_tags(m.group(1))

        # Description fallback
        if not result["description"]:
            m = re.search(
                r'<div[^>]*(?:show-more-less-html__markup|description__text--rich)[^>]*>(.*?)</div>',
                html, re.DOTALL
            )
            if m:
                result["description"] = _strip_tags(m.group(1))
