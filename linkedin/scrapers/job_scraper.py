"""
JobScraper — scrapes a LinkedIn job offer detail page via Playwright.

Stratégie (par ordre de priorité) :
  1. JSON-LD  : <script type="application/ld+json"> contient souvent toutes les
                données structurées (JobPosting) — méthode la plus fiable.
  2. CSS selectors : multiples sélecteurs couvrant l'ancienne et la nouvelle UI.
  3. Regex HTML    : fallback sur le contenu brut de la page.
"""
import asyncio
import json
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

    # Keywords used to classify pill-based criteria (nouvelle UI sans étiquettes)
    _EMPLOYMENT_KEYWORDS = {
        "full-time", "part-time", "contract", "temporary", "volunteer",
        "internship", "cdi", "cdd", "stage", "alternance", "interim",
        "temps plein", "temps partiel", "freelance",
    }
    _SENIORITY_KEYWORDS = {
        "entry level", "associate", "junior", "mid-senior", "senior",
        "director", "executive", "internship", "débutant", "confirmé",
        "manager", "directeur", "executif",
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
            "easy_apply":       False,
        }

        try:
            # domcontentloaded uniquement — networkidle bloque sur LinkedIn (polling permanent)
            await self.page.goto(linkedin_url, wait_until="domcontentloaded", timeout=30000)

            # Vérifier si LinkedIn affiche un mur de connexion / modal
            await asyncio.sleep(1)
            try:
                dismiss_btns = [
                    "button.modal__dismiss",
                    "button[aria-label='Ignorer']",
                    "button[aria-label='Dismiss']",
                ]
                for btn_sel in dismiss_btns:
                    btn = self.page.locator(btn_sel).first
                    if await btn.count() > 0:
                        await btn.click()
                        await asyncio.sleep(0.5)
                        break
            except Exception:
                pass

            # Attendre que le contenu soit rendu — ancres stables de la nouvelle UI SDUI
            for anchor_sel in [
                # Nouvelle UI SDUI 2025 (éléments confirmés dans le HTML)
                "[data-sdui-screen]",
                "[data-testid='lazy-column']",
                "[data-sdui-component*='aboutTheJob']",
                "[data-testid='expandable-text-box']",
                # UI intermédiaire
                ".job-details-jobs-unified-top-card__job-title",
                ".jobs-unified-top-card__job-title",
                # Ancienne UI
                "h1.t-24",
                "h1",
                "[data-job-id]",
            ]:
                try:
                    await self.page.wait_for_selector(anchor_sel, timeout=6000)
                    break
                except Exception:
                    continue
            else:
                await asyncio.sleep(5)

            # Attente supplémentaire pour le rendu dynamique (company, location, etc.)
            await asyncio.sleep(2.5)

            # Scroll complet pour déclencher le lazy-load de toutes les sections
            await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight / 3)")
            await asyncio.sleep(1.0)
            await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
            await asyncio.sleep(1.0)
            await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(1.0)
            await self.page.evaluate("window.scrollTo(0, 0)")
            await asyncio.sleep(0.8)

            # Avertissement si la page est anormalement courte (blocage anti-bot probable)
            try:
                html_len = len(await self.page.content())
                if html_len < 5000:
                    pass
            except Exception:
                pass

            await self._extract_all(result)

        except Exception:
            pass

        return result

    # ------------------------------------------------------------------
    # Extraction de tous les champs
    # ------------------------------------------------------------------

    async def _extract_all(self, result: dict) -> None:
        page = self.page

        # --- Stratégie 1 : JSON-LD (méthode la plus fiable) ---
        await self._extract_from_jsonld(result)

        # --- Titre ---
        if not result["title"]:
            title = await _try_selectors(page, [
                "h1",
                "h1[class*='job-title']",
                "h1.t-24",
            ])
            if not title:
                title_tag = await page.title()
                if title_tag:
                    # Format : "Data Analyst - Bordeaux, France (H/F) | Astek | LinkedIn"
                    # → on prend tout avant le premier " | "
                    title = re.split(r"\s*\|\s*", title_tag)[0].strip()
                    # Nettoyer le suffixe " - Ville, Pays (H/F)"
                    title = re.sub(r"\s+-\s+[^-]+$", "", title).strip()
                    # Si toujours vide, prendre le raw nettoyé LinkedIn
                    if not title:
                        title = re.sub(r"\s*[|\-–].*LinkedIn.*$", "", title_tag).strip()
            if title:
                result["title"] = title

        # --- Titre (fallback SDUI : le <p> principal de l'offre) ---
        if not result["title"]:
            try:
                all_p = await page.locator("main p, [role='main'] p").all()
                for p_el in all_p[:30]:
                    txt = (await p_el.inner_text()).strip()
                    if txt and 5 < len(txt) < 120 and "LinkedIn" not in txt and "·" not in txt and "candidature" not in txt.lower():
                        result["title"] = txt
                        break
            except Exception:
                pass

        # --- Location depuis le titre si pas encore trouvée ---
        if not result["location"]:
            try:
                title_tag = await page.title()
                # "Data Analyst - Bordeaux, France (H/F) | Astek | LinkedIn"
                m = re.search(r"-\s*([^|(H/F)]+?)(?:\s*\(H/F\))?\s*\|", title_tag)
                if m:
                    loc = m.group(1).strip()
                    if loc and len(loc) > 2:
                        result["location"] = loc
            except Exception:
                pass

        # --- Entreprise (nom + URL) ---
        if not result["company_url"]:
            company_url = await _try_attr_selectors(page, [
                # Nouvelle UI : lien vers /company/ dans le top-card
                ("a[href*='/company/'][aria-label*='Entreprise']", "href"),
                ("a[href*='/company/'][aria-label*='Company']", "href"),
                # Fallback : premier lien /company/ hors nav
                ("main a[href*='/company/']", "href"),
                ("a[href*='/company/']", "href"),
            ])
            if company_url:
                result["company_url"] = company_url.split("?")[0]

        if not result["company_name"]:
            # Nouvelle UI : l'entreprise est dans un <p> enfant du bloc avec aria-label="Entreprise, XXX"
            try:
                company_block = page.locator("[aria-label*='Entreprise'], [aria-label*='Company']").first
                if await company_block.count() > 0:
                    link = company_block.locator("a").first
                    if await link.count() > 0:
                        name = (await link.inner_text()).strip()
                        if name:
                            result["company_name"] = name
            except Exception:
                pass

        if not result["company_name"]:
            company_name = await _try_selectors(page, [
                "main a[href*='/company/']",
                "a[href*='/company/']",
            ])
            if company_name:
                result["company_name"] = company_name.strip()

        # Fallback : extraire company_name depuis company_url
        if not result["company_name"] and result["company_url"]:
            m = re.search(r"/company/([^/?#]+)", result["company_url"])
            if m:
                result["company_name"] = m.group(1).replace("-", " ").title()

        # --- Localisation / Date / Candidats depuis le <p> avec séparateurs "·" ---
        # Nouvelle UI : un seul <p> contient "Bordeaux · Republié il y a X · Plus de 100 candidatures"
        await self._extract_meta_paragraph(result)

        # --- Description ---
        if not result["description"]:
            # Cliquer sur "Voir plus" si disponible
            try:
                see_more = page.locator(
                    "[data-testid='expandable-text-box'] button, "
                    "button[aria-label*='Voir plus'], "
                    "button[aria-label*='more'], "
                    "button.show-more-less-html__button"
                ).first
                if await see_more.count() > 0:
                    await see_more.click()
                    await asyncio.sleep(0.8)
            except Exception:
                pass

            description = await _try_selectors(page, [
                # Nouvelle UI SDUI : data-testid stable
                "[data-testid='expandable-text-box']",
                # data-sdui-component aboutTheJob
                "[data-sdui-component*='aboutTheJob'] p",
                # Ancienne UI
                "#job-details",
                "div#job-details",
                "div.show-more-less-html__markup",
                "div[class*='show-more-less-html__markup']",
                "div.jobs-description__content",
                "div.description__text",
            ])
            if description:
                result["description"] = description

        # --- Critères (séniorité, type contrat, fonction, secteur) ---
        await self._extract_criteria(result)

        # --- Candidature simplifiée (Easy Apply) ---
        await self._detect_easy_apply(result)


    # ------------------------------------------------------------------
    # Extraction localisation / date / candidats depuis le paragraphe meta
    # ------------------------------------------------------------------

    async def _extract_meta_paragraph(self, result: dict) -> None:
        """
        Nouvelle UI LinkedIn 2025 : localisation, date et candidats sont dans un seul <p>
        au format : "Bordeaux, France · Republié il y a 4 min · Plus de 100 candidatures"
        """
        page = self.page
        try:
            # Chercher le <p> contenant un séparateur "·" dans la zone principale
            all_p = await page.locator("main p, [role='main'] p").all()
            for p_el in all_p[:60]:
                try:
                    txt = (await p_el.inner_text()).strip()
                    if "·" not in txt:
                        continue
                    parts = [p.strip() for p in txt.split("·")]
                    if len(parts) < 2:
                        continue

                    # Heuristiques pour identifier le bon <p>
                    has_location = any(
                        kw in parts[0].lower()
                        for kw in ["france", "paris", "lyon", "bordeaux", "marseille",
                                   "toulouse", "nantes", "lille", "remote", "télétravail",
                                   "region", "département", "belgique", "suisse", "luxembourg"]
                    ) or (len(parts[0]) > 3 and len(parts[0]) < 80)

                    has_time = any(
                        kw in txt.lower()
                        for kw in ["il y a", "ago", "repost", "republié", "publié", "posted",
                                   "hour", "day", "week", "heure", "jour", "semaine", "minute"]
                    )

                    if not (has_location or has_time):
                        continue

                    # Localisation : premier segment (avant le premier ·)
                    if not result["location"] and parts[0]:
                        result["location"] = parts[0]

                    # Date et candidats dans les segments suivants
                    for part in parts[1:]:
                        part_lower = part.lower()
                        if not result["posted_time"] and any(
                            kw in part_lower for kw in ["il y a", "ago", "republié", "publié",
                                                         "posted", "heure", "jour", "semaine",
                                                         "minute", "repost"]
                        ):
                            # Nettoyer les balises potentielles
                            result["posted_time"] = re.sub(r"\s+", " ", part).strip()

                        elif not result["applicants_count"] and any(
                            kw in part_lower for kw in ["candidat", "applicant", "postul",
                                                          "postuler", "candidature"]
                        ):
                            result["applicants_count"] = re.sub(r"\s+", " ", part).strip()

                    # Si on a trouvé au moins la localisation, on arrête
                    if result["location"]:
                        break
                except Exception:
                    continue
        except Exception:
            pass

        # Fallback CSS pour chaque champ encore null
        if not result["location"]:
            result["location"] = await _try_selectors(page, [
                "span[class*='bullet']",
                "span[class*='location']",
                "span.topcard__flavor--bullet",
            ])

        if not result["posted_time"]:
            result["posted_time"] = await _try_selectors(page, [
                "span[class*='posted']",
                "span[class*='time-ago']",
                "time",
            ])

    # ------------------------------------------------------------------
    # Extraction depuis JSON-LD (stratégie principale)
    # ------------------------------------------------------------------

    async def _extract_from_jsonld(self, result: dict) -> None:
        """Extrait les données depuis les balises <script type='application/ld+json'>."""
        try:
            scripts = await self.page.query_selector_all('script[type="application/ld+json"]')
            for script in scripts:
                try:
                    content = await script.inner_text()
                    data = json.loads(content)
                except Exception:
                    continue

                if not isinstance(data, dict):
                    continue
                if data.get("@type") != "JobPosting":
                    continue

                if not result["title"] and data.get("title"):
                    result["title"] = data["title"].strip()

                if not result["description"] and data.get("description"):
                    result["description"] = _strip_tags(data["description"])

                hiring_org = data.get("hiringOrganization", {})
                if isinstance(hiring_org, dict):
                    if not result["company_name"] and hiring_org.get("name"):
                        result["company_name"] = hiring_org["name"].strip()
                    if not result["company_url"] and hiring_org.get("sameAs"):
                        result["company_url"] = hiring_org["sameAs"].split("?")[0]

                # Localisation depuis jobLocation
                if not result["location"]:
                    job_loc = data.get("jobLocation", {})
                    if isinstance(job_loc, list):
                        job_loc = job_loc[0] if job_loc else {}
                    address = job_loc.get("address", {}) if isinstance(job_loc, dict) else {}
                    if isinstance(address, dict):
                        parts = [
                            address.get("addressLocality", ""),
                            address.get("addressRegion", ""),
                            address.get("addressCountry", ""),
                        ]
                        loc_str = ", ".join(p for p in parts if p)
                        if loc_str:
                            result["location"] = loc_str

                if not result["employment_type"] and data.get("employmentType"):
                    result["employment_type"] = data["employmentType"]

                if not result["posted_time"] and data.get("datePosted"):
                    result["posted_time"] = data["datePosted"]

                if not result["seniority_level"] and data.get("experienceRequirements"):
                    req = data["experienceRequirements"]
                    if isinstance(req, dict):
                        result["seniority_level"] = req.get("name") or req.get("educationalCredentialAwarded")
                    elif isinstance(req, str):
                        result["seniority_level"] = req

                if not result["industries"] and data.get("industry"):
                    result["industries"] = data["industry"]

                # Un seul bloc JobPosting suffit
                return
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Extraction des critères structurés
    # ------------------------------------------------------------------

    async def _extract_criteria(self, result: dict) -> None:
        page = self.page

        # ------------------------------------------------------------------
        # Stratégie 0 : Nouvelle UI SDUI 2025 — pills <a> dans le top-card
        # Dans le HTML on voit des <a href="/jobs/view/ID/"> contenant le texte
        # "Hybride", "Temps plein", "CDI", etc. directement cliquables.
        # ------------------------------------------------------------------
        try:
            # Tous les liens internes vers la même offre (pills de tags)
            pill_links = await page.locator(
                "main a[href*='/jobs/view/']"
            ).all()
            for link in pill_links:
                try:
                    txt = (await link.inner_text()).strip()
                    if not txt or len(txt) > 40:
                        continue
                    txt_lower = txt.lower()
                    if any(k in txt_lower for k in self._EMPLOYMENT_KEYWORDS):
                        if not result["employment_type"]:
                            result["employment_type"] = txt
                    elif any(k in txt_lower for k in self._SENIORITY_KEYWORDS):
                        if not result["seniority_level"]:
                            result["seniority_level"] = txt
                except Exception:
                    continue
        except Exception:
            pass

        # ------------------------------------------------------------------
        # Stratégie A : liste <li> avec header h3 + span valeur (ancienne UI)
        # ------------------------------------------------------------------
        criteria_items = page.locator(
            "li.description__job-criteria-item, "
            "li[class*='job-criteria-item']"
        )
        count = await criteria_items.count()
        if count > 0:
            for i in range(count):
                item = criteria_items.nth(i)
                try:
                    header_el = item.locator("h3, dt").first
                    value_el = item.locator("span:not(h3 span), dd").first
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

        # ------------------------------------------------------------------
        # Stratégie B : pills nommées (ancienne nouvelle UI)
        # ------------------------------------------------------------------
        pill_items = page.locator(
            "li.job-details-preferences-and-skills__pill, "
            "span.job-details-preferences-and-skills__pill, "
            "li[class*='preferences-and-skills__pill']"
        )
        count_pills = await pill_items.count()
        if count_pills > 0:
            for i in range(count_pills):
                item = pill_items.nth(i)
                try:
                    text = (await item.inner_text()).strip()
                    text_lower = text.lower()
                    if any(k in text_lower for k in self._EMPLOYMENT_KEYWORDS):
                        if not result["employment_type"]:
                            result["employment_type"] = text
                    elif any(k in text_lower for k in self._SENIORITY_KEYWORDS):
                        if not result["seniority_level"]:
                            result["seniority_level"] = text
                except Exception:
                    continue

        # ------------------------------------------------------------------
        # Stratégie C : fallback HTML brut
        # ------------------------------------------------------------------
        try:
            html = await page.content()
            await self._extract_criteria_from_html(html, result)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Extraction critères depuis le HTML brut (fallback regex)
    # ------------------------------------------------------------------

    async def _extract_criteria_from_html(self, html: str, result: dict) -> None:
        """Extraction des champs restants par regex sur le HTML brut."""

        # ------------------------------------------------------------------
        # Employment type & seniority : chercher les textes visibles dans des
        # balises courtes (spans, a, strong) qui matchent les keywords connus
        # ------------------------------------------------------------------
        all_employment = [
            "full-time", "part-time", "contract", "temporary", "volunteer",
            "internship", "cdi", "cdd", "stage", "alternance", "intérim",
            "temps plein", "temps partiel", "freelance", "hybride",
            "présentiel", "télétravail", "remote",
        ]
        all_seniority = [
            "entry level", "associate", "junior", "mid-senior", "senior",
            "director", "executive", "débutant", "confirmé",
            "manager", "directeur",
        ]

        # Regex : texte court dans une balise inline
        inline_texts = re.findall(
            r'<(?:span|a|strong|p)[^>]{0,200}>\s*([^<]{2,40})\s*</(?:span|a|strong|p)>',
            html, re.IGNORECASE
        )
        for txt in inline_texts:
            txt_clean = txt.strip()
            txt_lower = txt_clean.lower()
            if not result["employment_type"] and any(k == txt_lower for k in all_employment):
                result["employment_type"] = txt_clean
            if not result["seniority_level"] and any(k == txt_lower for k in all_seniority):
                result["seniority_level"] = txt_clean

        # ------------------------------------------------------------------
        # Patterns ancienne UI avec label explicite
        # ------------------------------------------------------------------
        patterns_criteria = [
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

        # ------------------------------------------------------------------
        # Localisation fallback
        # ------------------------------------------------------------------
        if not result["location"]:
            # Chercher dans le title : "Intitulé - Ville, Pays | Entreprise | LinkedIn"
            m = re.search(r'<title>[^<]+-\s*([^|<(]+?)(?:\s*\(H/F\))?\s*\|', html)
            if m:
                loc = m.group(1).strip()
                if loc and "LinkedIn" not in loc:
                    result["location"] = loc

        # Posted time fallback
        if not result["posted_time"]:
            m = re.search(r'<span[^>]*posted-time-ago__text[^>]*>(.*?)</span>', html, re.DOTALL)
            if m:
                result["posted_time"] = _strip_tags(m.group(1))

        # Applicants fallback
        if not result["applicants_count"]:
            m = re.search(r'<span[^>]*num-applicants__caption[^>]*>(.*?)</span>', html, re.DOTALL)
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

    # ------------------------------------------------------------------
    # Détection Candidature simplifiée / Easy Apply
    # ------------------------------------------------------------------

    async def _detect_easy_apply(self, result: dict) -> None:
        """
        Détecte si l'offre propose une candidature simplifiée (Easy Apply).
        Remplit result["easy_apply"] = True si détecté.

        Stratégies :
          1. Présence du bouton Easy Apply / Candidature simplifiée (CSS selectors)
          2. Attribut aria-label contenant "Easy Apply" ou "Candidature simplifiée"
          3. Fallback HTML : recherche textuelle dans le contenu brut
        """
        page = self.page

        # Sélecteurs CSS connus pour le bouton Easy Apply (LinkedIn FR + EN)
        easy_apply_selectors = [
            # Nouvelle UI SDUI 2025
            "button[aria-label*='Easy Apply']",
            "button[aria-label*='Candidature simplifiée']",
            "button[aria-label*='easy apply' i]",
            "button[aria-label*='candidature simplifi' i]",
            # Classes spécifiques LinkedIn
            ".jobs-apply-button--top-card",
            "button.jobs-apply-button",
            # Ancienne UI
            ".jobs-unified-top-card__content--two-pane button.artdeco-button--primary",
        ]

        for sel in easy_apply_selectors:
            try:
                loc = page.locator(sel).first
                if await loc.count() > 0:
                    label = (await loc.get_attribute("aria-label") or "").lower()
                    text  = (await loc.inner_text()).strip().lower()
                    if any(kw in label or kw in text for kw in [
                        "easy apply", "candidature simplifiée", "candidature simplifiee",
                        "postuler facilement",
                    ]):
                        result["easy_apply"] = True
                        return
                    # Si pas de texte explicite, vérifier que le bouton n'est PAS
                    # un bouton de redirection externe (qui ouvrirait un autre site)
                    # → on marque True si c'est un bouton primary sans href
                    if "jobs-apply-button" in sel:
                        href = await loc.get_attribute("href")
                        if href is None:  # bouton natif LinkedIn = Easy Apply
                            result["easy_apply"] = True
                            return
            except Exception:
                continue

        # Fallback : analyse du HTML brut
        try:
            html = await page.content()
            easy_apply_patterns = [
                r'easy\s*apply',
                r'candidature\s*simplifi',
                r'postuler\s*facilement',
                r'data-job-application-type\s*=\s*["\']EASY_APPLY["\']',
                r'"easyApplyUrl"\s*:',
                r'easy-apply',
            ]
            html_lower = html.lower()
            for pattern in easy_apply_patterns:
                if re.search(pattern, html_lower, re.IGNORECASE):
                    result["easy_apply"] = True
                    return
        except Exception:
            pass

