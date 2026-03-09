"""
PeopleScraper — scrapes employees from a LinkedIn company /people/ page.
"""
import asyncio
import random
import re
import urllib.parse


class PeopleScraper:
    """Scrapes employee profiles from a LinkedIn company page."""

    def __init__(self, page) -> None:
        self.page = page

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

        await self.page.goto(people_url, wait_until="domcontentloaded")
        await asyncio.sleep(3)

        all_people: list[dict] = []
        scroll_count = 0
        max_scrolls = (max_personnes // 8) + 3

        while len(all_people) < max_personnes and scroll_count < max_scrolls:
            people_on_page = await self._extract_people_from_page()

            for person in people_on_page:
                if not any(p["profile_url"] == person["profile_url"] for p in all_people):
                    all_people.append(person)
                    if len(all_people) >= max_personnes:
                        break

            if len(all_people) < max_personnes:
                await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(random.uniform(2, 3))
                scroll_count += 1
            else:
                break

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

    async def _extract_people_from_page(self) -> list[dict]:
        """Extract visible employee cards from the current page state."""
        people = []
        try:
            await self.page.wait_for_selector(
                "a[href*='/in/'], .org-people-profile-card",
                timeout=8000,
            )

            raw = await self.page.evaluate("""() => {
                const results = [];
                const seen = new Set();

                const cardSelectors = [
                    '.org-people-profile-card__card-spacing',
                    '.org-people-profile-card',
                    '[data-view-name="profile-entity-lockup"]',
                    '.artdeco-entity-lockup',
                ];

                let cards = [];
                for (const sel of cardSelectors) {
                    cards = document.querySelectorAll(sel);
                    if (cards.length > 0) break;
                }

                // Fallback: collect from main /in/ links
                if (cards.length === 0) {
                    const links = document.querySelectorAll('main a[href*="/in/"]');
                    links.forEach(link => {
                        const href = link.href.split('?')[0];
                        if (seen.has(href)) return;
                        seen.add(href);

                        const container = link.closest(
                            'li, div.artdeco-entity-lockup, div[class*="card"]'
                        ) || link.parentElement;

                        // Name: prefer aria-hidden span inside the /in/ link
                        const nameEl = link.querySelector('span[aria-hidden="true"]');
                        const name = nameEl?.innerText?.trim()
                            || link.innerText?.trim()
                            || '';

                        // Title
                        const titleEl = container?.querySelector(
                            '.artdeco-entity-lockup__subtitle, [class*="subtitle"]'
                        );
                        const title = titleEl?.innerText?.trim() || '';

                        // Connection degree
                        const degreeEl = container?.querySelector('[class*="dist-badge"]');
                        let connectionDegree = degreeEl?.innerText?.trim() || '';
                        connectionDegree = connectionDegree
                            .replace(/1er|1st/i, '1st')
                            .replace(/2e|2nd/i, '2nd')
                            .replace(/3e|3rd\\+?/i, '3rd+')
                            .trim();

                        if (name && name.length > 1) {
                            results.push({
                                name,
                                title,
                                connection_degree: connectionDegree,
                                profile_url: href,
                                location: '',
                            });
                        }
                    });
                    return results;
                }

                cards.forEach(card => {
                    const link = card.querySelector('a[href*="/in/"]');
                    if (!link) return;
                    const href = link.href.split('?')[0];
                    if (seen.has(href)) return;
                    seen.add(href);

                    // Name: span[aria-hidden="true"] inside the /in/ link
                    const nameEl = link.querySelector('span[aria-hidden="true"]')
                        || card.querySelector(
                            '.artdeco-entity-lockup__title span[aria-hidden="true"], '
                            + '.org-people-profile-card__profile-title'
                        );
                    const name = nameEl?.innerText?.trim() || '';

                    // Title / position
                    const titleEl = card.querySelector(
                        '.artdeco-entity-lockup__subtitle, '
                        + '.org-people-profile-card__profile-info, '
                        + '[class*="subtitle"]'
                    );
                    const title = titleEl?.innerText?.trim() || '';

                    // Connection degree badge
                    const degreeEl = card.querySelector('[class*="dist-badge"]');
                    let connectionDegree = degreeEl?.innerText?.trim() || '';
                    connectionDegree = connectionDegree
                        .replace(/1er|1st/i, '1st')
                        .replace(/2e|2nd/i, '2nd')
                        .replace(/3e|3rd\\+?/i, '3rd+')
                        .trim();

                    // Location
                    const locationEl = card.querySelector(
                        '[class*="caption"], [class*="location"]'
                    );
                    const location = locationEl?.innerText?.trim() || '';

                    if (name) {
                        results.push({
                            name,
                            title,
                            connection_degree: connectionDegree,
                            location,
                            profile_url: href,
                        });
                    }
                });

                return results;
            }""")

            people = raw if raw else []

        except Exception as e:
            print(f"  ⚠️ Erreur extraction employés : {e}")

        return people

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
