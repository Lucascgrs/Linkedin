"""
PeopleScraper — scrapes employees from a LinkedIn company /people/ page.

Stratégie :
  1. Interception réseau  : écoute les réponses XHR/fetch de l'API Voyager
     (/voyager/api/graphql  et  /voyager/api/search/blended) et extrait
     les profils directement depuis le JSON — robuste aux changements de DOM.
  2. Fallback DOM         : si l'interception ne ramène rien, tente de lire
     les cartes HTML présentes dans la page.
"""
import asyncio
import random
import re
import urllib.parse


class PeopleScraper:
    """Scrapes employee profiles from a LinkedIn company page."""

    def __init__(self, page) -> None:
        self.page = page

    # ------------------------------------------------------------------ #
    #  Point d'entrée principal                                           #
    # ------------------------------------------------------------------ #

    async def scrape_company_people(
        self,
        company_url: str,
        filtre_poste: str = "",
        max_personnes: int = 20,
        scrape_contact: bool = False,
    ) -> list[dict]:
        """
        Retrieve employees listed on a company's LinkedIn /people/ page.

        Args:
            company_url:    Full LinkedIn company URL.
            filtre_poste:   Optional keyword filter for job titles.
            max_personnes:  Maximum number of profiles to collect.
            scrape_contact: If True, visit each profile to attempt to
                            retrieve contact info (email, phone, website).

        Returns:
            List of dicts with keys: name, title, connection_degree,
            profile_url, location (and optionally email, phone, website,
            twitter if scrape_contact=True).
        """
        people_url = company_url.rstrip("/") + "/people/"
        if filtre_poste:
            people_url += "?" + urllib.parse.urlencode({"keywords": filtre_poste})

        # ── Collecteur des réponses réseau Voyager ──────────────────────
        intercepted: list[dict] = []

        async def _on_response(response):
            url = response.url
            if "voyager/api" not in url:
                return
            # On cible les endpoints qui contiennent des profils
            if not any(k in url for k in ("search/blended", "graphql", "members", "people", "search/cluster")):
                return
            try:
                ct = response.headers.get("content-type", "")
                if "json" not in ct:
                    return
                body = await response.json()
                profiles = self._parse_voyager_response(body)
                intercepted.extend(profiles)
            except Exception:
                pass

        self.page.on("response", _on_response)

        try:
            await self.page.goto(people_url, wait_until="domcontentloaded")
            await asyncio.sleep(5)

            current_url = self.page.url
            print(f"  📄 Page chargée : {current_url}")

            all_people: list[dict] = []
            no_new_count = 0
            max_scrolls = (max_personnes // 8) + 6

            for scroll_idx in range(max_scrolls):
                if len(all_people) >= max_personnes:
                    break

                prev_len = len(all_people)

                # ── 1. Profils interceptés via réseau ───────────────────
                for p in intercepted:
                    if not any(x["profile_url"] == p["profile_url"] for x in all_people):
                        all_people.append(p)
                        if len(all_people) >= max_personnes:
                            break

                # ── 2. Fallback DOM si réseau n'a rien donné ────────────
                if len(all_people) == 0:
                    dom_people = await self._extract_people_from_dom()
                    for p in dom_people:
                        if not any(x["profile_url"] == p["profile_url"] for x in all_people):
                            all_people.append(p)
                            if len(all_people) >= max_personnes:
                                break

                added = len(all_people) - prev_len
                print(f"  👥 Passe {scroll_idx + 1} : {len(all_people)} profil(s) total ({added} nouveaux)")

                if added == 0:
                    no_new_count += 1
                    if no_new_count >= 3:
                        print("  ⚠️  Aucun nouveau profil depuis 3 passes — arrêt.")
                        break
                else:
                    no_new_count = 0

                # Scroll pour déclencher le prochain batch réseau
                await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(random.uniform(2.0, 3.5))

        finally:
            self.page.remove_listener("response", _on_response)

        all_people = all_people[:max_personnes]

        if scrape_contact:
            for person in all_people:
                if person.get("profile_url"):
                    try:
                        contact_info = await self.scrape_contact_info(person["profile_url"])
                        person.update(contact_info)
                    except Exception:
                        pass
                    await asyncio.sleep(random.uniform(3, 5))

        return all_people

    # ------------------------------------------------------------------ #
    #  Parsing de l'API Voyager                                           #
    # ------------------------------------------------------------------ #

    def _parse_voyager_response(self, body: dict) -> list[dict]:
        """
        Extrait les profils depuis une réponse JSON Voyager.
        Compatible avec :
          - /voyager/api/search/blended   (included[])
          - /voyager/api/graphql          (data.searchDashClustersByAll…)
        """
        profiles = []

        # ── Format graphql / search moderne ────────────────────────────
        try:
            # Parcours générique du JSON à la recherche des entités de profil
            profiles.extend(self._deep_search_profiles(body))
        except Exception:
            pass

        return profiles

    def _deep_search_profiles(self, obj, _depth=0) -> list[dict]:
        """Parcourt récursivement le JSON Voyager et extrait tout ce qui ressemble à un profil."""
        results = []
        if _depth > 12 or not isinstance(obj, (dict, list)):
            return results

        if isinstance(obj, list):
            for item in obj:
                results.extend(self._deep_search_profiles(item, _depth + 1))
            return results

        # Détecter un nœud "profil" : doit avoir un publicIdentifier ou un firstName+lastName
        pub_id = obj.get("publicIdentifier") or obj.get("vanityName") or obj.get("profileId")
        first = obj.get("firstName") or ""
        last = obj.get("lastName") or ""

        if pub_id or (first and last):
            name = f"{first} {last}".strip() if (first or last) else ""
            # Titre : plusieurs clés possibles selon l'endpoint
            headline = (
                obj.get("headline")
                or obj.get("title")
                or obj.get("occupation")
                or ""
            )
            if isinstance(headline, dict):
                headline = headline.get("text", "")

            location = obj.get("locationName") or obj.get("geoLocationName") or ""
            if isinstance(location, dict):
                location = location.get("defaultLocalizedName", "")

            degree_raw = (
                obj.get("distance", {}) if isinstance(obj.get("distance"), dict) else {}
            )
            degree = degree_raw.get("value", "") or obj.get("connectionDegree", "")
            degree = self._normalize_degree(str(degree))

            profile_url = ""
            if pub_id:
                profile_url = f"https://www.linkedin.com/in/{pub_id}"
            elif obj.get("navigationUrl"):
                profile_url = obj["navigationUrl"].split("?")[0]

            if name and profile_url:
                results.append({
                    "name": name,
                    "title": headline,
                    "connection_degree": degree,
                    "location": location,
                    "profile_url": profile_url,
                })
                return results  # Ne pas descendre plus dans ce nœud

        # Descendre dans les valeurs
        for v in obj.values():
            if isinstance(v, (dict, list)):
                results.extend(self._deep_search_profiles(v, _depth + 1))

        return results

    @staticmethod
    def _normalize_degree(txt: str) -> str:
        txt = txt.strip()
        if txt in ("DISTANCE_1", "F", "1"):
            return "1st"
        if txt in ("DISTANCE_2", "S", "2"):
            return "2nd"
        if txt in ("DISTANCE_3", "3", "O"):
            return "3rd+"
        return txt

    # ------------------------------------------------------------------ #
    #  Fallback DOM                                                       #
    # ------------------------------------------------------------------ #

    async def _extract_people_from_dom(self) -> list[dict]:
        """Fallback : extrait les cartes HTML si le réseau n'a rien intercepté."""
        people = []
        try:
            try:
                await self.page.wait_for_selector(
                    "a[href*='/in/'], .org-people-profile-card, [data-view-name='profile-entity-lockup']",
                    timeout=10000,
                )
            except Exception:
                pass

            raw = await self.page.evaluate("""() => {
                const results = [];
                const seen = new Set();
                const DEGREE_RE = /^[·•]?\\s*(1er|1st|2e|2ème|2nd|3e|3ème|3rd\\+?)\\s*$/i;

                function extractName(link, card) {
                    const explicit = card.querySelector(
                        '.artdeco-entity-lockup__title span[aria-hidden="true"]:not([class*="dist"]):not([class*="badge"]),'
                        + '.org-people-profile-card__profile-title,'
                        + '[class*="actor-name"]'
                    );
                    if (explicit) {
                        const t = explicit.innerText?.trim();
                        if (t && t.length > 1 && !DEGREE_RE.test(t)) return t;
                    }
                    for (const sp of link.querySelectorAll('span[aria-hidden="true"]')) {
                        const t = sp.innerText?.trim();
                        if (t && t.length > 1 && !DEGREE_RE.test(t)) return t;
                    }
                    return (link.innerText?.trim() || '')
                        .replace(/[·•]?\\s*(1er|1st|2e|2ème|2nd|3e|3ème|3rd\\+?)\\s*/gi, '')
                        .trim();
                }

                function extractDegree(link, card) {
                    const badge = card.querySelector('[class*="dist-badge"]');
                    if (badge?.innerText?.trim()) return normDeg(badge.innerText.trim());
                    for (const sp of link.querySelectorAll('span[aria-hidden="true"]')) {
                        const t = sp.innerText?.trim();
                        if (t && DEGREE_RE.test(t)) return normDeg(t);
                    }
                    return '';
                }

                function normDeg(t) {
                    return t.replace(/[·•]\\s*/g, '')
                             .replace(/1er|1st/i, '1st')
                             .replace(/2e|2ème|2nd/i, '2nd')
                             .replace(/3e|3ème|3rd\\+?/i, '3rd+')
                             .trim();
                }

                const cardSelectors = [
                    'li[class*="org-people-profiles-module__profile-list-item"]',
                    '[data-view-name="profile-entity-lockup"]',
                    'li.scaffold-layout__list-item',
                    '.org-people-profile-card__card-spacing',
                    '.org-people-profile-card',
                    '.artdeco-entity-lockup',
                    '.reusable-search__result-container',
                    'li[class*="reusable-search"]',
                ];

                let cards = [];
                for (const sel of cardSelectors) {
                    const found = document.querySelectorAll(sel);
                    if (found.length > 0) { cards = found; break; }
                }

                const processLink = (link, card) => {
                    const href = link.href.split('?')[0];
                    if (seen.has(href)) return;
                    if (/\/(mynetwork|messaging|jobs|feed|learning)/.test(href)) return;
                    seen.add(href);

                    const name = extractName(link, card);
                    if (!name || name.length < 2 || name.toLowerCase().includes('linkedin')) return;

                    const connectionDegree = extractDegree(link, card);

                    let title = '';
                    for (const sel of ['.artdeco-entity-lockup__subtitle','.org-people-profile-card__profile-info','[class*="subtitle"]','.entity-result__primary-subtitle']) {
                        const el = card.querySelector(sel);
                        if (el) { title = el.innerText?.trim(); break; }
                    }

                    let location = '';
                    for (const sel of ['[class*="caption"]','[class*="location"]','.entity-result__secondary-subtitle','[class*="subline-level-2"]']) {
                        const el = card.querySelector(sel);
                        if (el) { location = el.innerText?.trim(); break; }
                    }

                    results.push({ name, title, connection_degree: connectionDegree, location, profile_url: href });
                };

                if (cards.length === 0) {
                    document.querySelectorAll('a[href*="/in/"]').forEach(link => {
                        const container = link.closest('li, div[class*="card"], div[class*="result"]') || link.parentElement;
                        processLink(link, container || link);
                    });
                } else {
                    cards.forEach(card => {
                        const link = card.querySelector('a[href*="/in/"]');
                        if (link) processLink(link, card);
                    });
                }

                return results;
            }""")
            people = raw if raw else []
        except Exception as e:
            print(f"  ⚠️  Erreur fallback DOM : {e}")
        return people

    # ------------------------------------------------------------------ #
    #  Contact info                                                       #
    # ------------------------------------------------------------------ #

    async def scrape_contact_info(self, profile_url: str) -> dict:
        """
        Attempt to retrieve contact info from a LinkedIn profile.

        Opens the "Contact info" overlay. Returns an empty dict silently
        if the information is not accessible.

        Args:
            profile_url: Full LinkedIn profile URL.

        Returns:
            Dict with keys: email, phone, website, twitter (all optional).
        """
        contact: dict = {"email": None, "phone": None, "website": None, "twitter": None}

        try:
            await self.page.goto(profile_url, wait_until="domcontentloaded")
            await asyncio.sleep(2)

            contact_btn_selectors = [
                'a[href*="overlay/contact-info"]',
                'a[id*="contact-info"]',
                'a:has-text("Coordonnées")',
                'a:has-text("Contact info")',
            ]
            clicked = False
            for sel in contact_btn_selectors:
                btn = self.page.locator(sel).first
                if await btn.count() > 0:
                    await btn.click()
                    await asyncio.sleep(2)
                    clicked = True
                    break

            if not clicked:
                return contact

            modal = self.page.locator(
                '.pv-profile-section__section-info, '
                '.pv-contact-info__contact-type, '
                'section.pv-contact-info'
            ).first
            if await modal.count() == 0:
                modal = self.page.locator('[data-test-modal]').first

            if await modal.count() > 0:
                text = (await modal.inner_text()).strip()
            else:
                text = await self.page.locator('div[role="dialog"]').first.inner_text()

            email_match = re.search(r'[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}', text)
            if email_match:
                contact["email"] = email_match.group(0)

            phone_match = re.search(r'(\+?\d[\d\s\-().]{7,20})', text)
            if phone_match:
                contact["phone"] = phone_match.group(0).strip()

            web_links = await self.page.locator('div[role="dialog"] a[href^="http"]').all()
            for link in web_links:
                href = await link.get_attribute("href") or ""
                if "linkedin.com" not in href:
                    contact["website"] = href
                    break

            close_btn = self.page.locator(
                'button[aria-label*="Fermer"], button[aria-label*="Close"]'
            ).first
            if await close_btn.count() > 0:
                await close_btn.click()

        except Exception:
            pass

        return contact
