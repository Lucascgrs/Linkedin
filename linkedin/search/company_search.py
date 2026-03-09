"""
CompanySearch — searches LinkedIn for companies with optional filters.
"""
import asyncio
import random
import urllib.parse

from linkedin.scrapers.company_scraper import CompanyScraper
from linkedin.utils.filters import (
    GEO_IDS,
    INDUSTRY_IDS,
    COMPANY_SIZE_IDS,
    resolve_filter,
)


class CompanySearch:
    """Searches LinkedIn companies with optional geo, industry, size, and keyword filters."""

    def __init__(self, page) -> None:
        self.page = page

    # ------------------------------------------------------------------
    # URL builder
    # ------------------------------------------------------------------

    def build_url(
        self,
        pays: str = "",
        secteur: str = "",
        taille: list | None = None,
        keywords: str = "",
        page: int = 0,
    ) -> str:
        """
        Build a LinkedIn company search URL.

        Args:
            pays:     Country name (e.g. "france").
            secteur:  Industry name (e.g. "software").
            taille:   List of company size ranges (e.g. ["11-50", "51-200"]).
            keywords: Free-text keyword filter.
            page:     Page offset (0-based).

        Returns:
            Full search URL string.
        """
        geo_id = resolve_filter(pays, GEO_IDS, "pays") if pays else None
        industry_id = resolve_filter(secteur, INDUSTRY_IDS, "secteur") if secteur else None
        size_codes = self._resolve_sizes(taille or [])

        def encode_list_param(ids: list) -> str:
            inner = ",".join(f'"{i}"' for i in ids)
            return urllib.parse.quote(f"[{inner}]", safe="")

        parts = []
        if keywords:
            parts.append(f"keywords={urllib.parse.quote(keywords)}")
        parts.append("origin=FACETED_SEARCH")
        if geo_id:
            parts.append(f"companyHqGeo={encode_list_param([geo_id])}")
        if industry_id:
            parts.append(f"industryCompanyVertical={encode_list_param([industry_id])}")
        if size_codes:
            parts.append(f"companyHqSize={encode_list_param(size_codes)}")
        if page > 0:
            parts.append(f"start={page * 10}")

        base = "https://www.linkedin.com/search/results/companies/"
        return base + ("?" + "&".join(parts) if parts else "")

    # ------------------------------------------------------------------
    # Search — returns a list of company URLs
    # ------------------------------------------------------------------

    async def search(
        self,
        pays: str = "",
        secteur: str = "",
        taille: list | None = None,
        keywords: str = "",
        max_companies: int = 20,
    ) -> list[str]:
        """
        Collect company LinkedIn URLs matching the given filters.

        Args:
            pays:          Country name.
            secteur:       Industry name.
            taille:        List of company size labels.
            keywords:      Keyword filter.
            max_companies: Maximum number of company URLs to return.

        Returns:
            List of company LinkedIn URLs.
        """
        all_urls: list[str] = []
        page_num = 0

        while len(all_urls) < max_companies:
            search_url = self.build_url(pays, secteur, taille, keywords, page=page_num)
            await self.page.goto(search_url, wait_until="domcontentloaded")
            await asyncio.sleep(random.uniform(2, 3))

            new_urls = await self._extract_company_urls_from_page()
            fresh = [u for u in new_urls if u not in all_urls]
            all_urls.extend(fresh)

            if not fresh:
                break

            page_num += 1
            await asyncio.sleep(random.uniform(1.5, 3))

        return all_urls[:max_companies]

    # ------------------------------------------------------------------
    # Search + scrape details
    # ------------------------------------------------------------------

    async def search_and_scrape(
        self,
        pays: str = "",
        secteur: str = "",
        taille: list | None = None,
        keywords: str = "",
        max_companies: int = 20,
    ) -> list[dict]:
        """
        Search for companies then scrape details for each result.

        Args:
            pays:          Country name.
            secteur:       Industry name.
            taille:        List of company size labels.
            keywords:      Keyword filter.
            max_companies: Maximum number of companies to return.

        Returns:
            List of company detail dicts.
        """
        urls = await self.search(pays, secteur, taille, keywords, max_companies)
        scraper = CompanyScraper(self.page)
        results = []
        for i, url in enumerate(urls, 1):
            print(f"  [{i:2d}/{len(urls)}] {url}")
            try:
                company = await scraper.scrape(url)
                results.append(company)
            except Exception as e:
                print(f"         ⚠️ Erreur : {e}")
                results.append({"linkedin_url": url, "error": str(e)})
            await asyncio.sleep(random.uniform(3, 6))
        return results

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_sizes(sizes: list) -> list:
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

    async def _extract_company_urls_from_page(self) -> list[str]:
        urls = []
        try:
            await self.page.wait_for_selector('a[href*="/company/"]', timeout=10000)
            await asyncio.sleep(1)

            links = await self.page.locator('a[href*="/company/"]').all()
            seen: set[str] = set()

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
                    and not any(
                        sub in clean
                        for sub in ["/jobs", "/posts", "/people", "/about", "/life"]
                    )
                ):
                    if not clean.startswith("http"):
                        clean = "https://www.linkedin.com" + clean
                    seen.add(clean)
                    urls.append(clean)
        except Exception as e:
            print(f"  ⚠️ Erreur extraction URLs : {e}")
        return urls
