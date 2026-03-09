"""
JobSearch — searches LinkedIn job offers with optional filters.
"""
import asyncio
import random
import urllib.parse

from linkedin.scrapers.job_scraper import JobScraper
from linkedin.utils.filters import (
    GEO_IDS,
    DATE_POSTED,
    WORKPLACE_TYPE,
    JOB_TYPE,
    EXPERIENCE_LEVEL,
    resolve_filter,
    resolve_multi,
)


class JobSearch:
    """Searches LinkedIn job offers with optional keyword, geo, and filter parameters."""

    def __init__(self, page) -> None:
        self.page = page

    # ------------------------------------------------------------------
    # URL builder
    # ------------------------------------------------------------------

    def build_url(
        self,
        keywords: str = "",
        pays: str = "",
        date_publiee: str = "",
        mode_travail: list | None = None,
        type_contrat: list | None = None,
        niveau_experience: list | None = None,
        page: int = 0,
    ) -> str:
        """
        Build a LinkedIn jobs search URL.

        Args:
            keywords:          Search terms.
            pays:              Country name (e.g. "france").
            date_publiee:      Recency filter: "24h", "semaine", or "mois".
            mode_travail:      List of workplace types (e.g. ["remote", "hybride"]).
            type_contrat:      List of contract types (e.g. ["cdi"]).
            niveau_experience: List of experience levels (e.g. ["junior"]).
            page:              Page offset (0-based).

        Returns:
            Full search URL string.
        """
        geo_id = resolve_filter(pays, GEO_IDS, "pays") if pays else None
        date_code = resolve_filter(date_publiee, DATE_POSTED, "date") if date_publiee else None
        workplace_codes = resolve_multi(mode_travail or [], WORKPLACE_TYPE, "mode_travail")
        job_type_codes = resolve_multi(type_contrat or [], JOB_TYPE, "type_contrat")
        exp_codes = resolve_multi(niveau_experience or [], EXPERIENCE_LEVEL, "experience")

        parts = []
        if keywords:
            parts.append(f"keywords={urllib.parse.quote(keywords)}")
        if geo_id:
            parts.append(f"geoId={geo_id}")
        if date_code:
            parts.append(f"f_TPR={date_code}")
        if workplace_codes:
            parts.append(f"f_WT={','.join(workplace_codes)}")
        if job_type_codes:
            parts.append(f"f_JT={','.join(job_type_codes)}")
        if exp_codes:
            parts.append(f"f_E={','.join(exp_codes)}")
        if page > 0:
            parts.append(f"start={page * 25}")

        base = "https://www.linkedin.com/jobs/search/"
        return base + ("?" + "&".join(parts) if parts else "")

    # ------------------------------------------------------------------
    # Search — returns a list of job offer URLs
    # ------------------------------------------------------------------

    async def search(
        self,
        keywords: str = "",
        pays: str = "",
        date_publiee: str = "",
        mode_travail: list | None = None,
        type_contrat: list | None = None,
        niveau_experience: list | None = None,
        max_offres: int = 20,
    ) -> list[str]:
        """
        Collect job offer LinkedIn URLs matching the given filters.

        Args:
            keywords:          Search terms.
            pays:              Country name.
            date_publiee:      Recency filter.
            mode_travail:      Workplace type filter.
            type_contrat:      Contract type filter.
            niveau_experience: Experience level filter.
            max_offres:        Maximum number of job URLs to return.

        Returns:
            List of job offer URLs.
        """
        all_urls: list[str] = []
        page_num = 0

        while len(all_urls) < max_offres:
            search_url = self.build_url(
                keywords, pays, date_publiee,
                mode_travail, type_contrat, niveau_experience,
                page=page_num,
            )
            await self.page.goto(search_url, wait_until="domcontentloaded")
            await asyncio.sleep(random.uniform(2, 3))

            new_urls = await self._extract_job_urls_from_page()
            fresh = [u for u in new_urls if u not in all_urls]
            all_urls.extend(fresh)

            if not fresh:
                break

            page_num += 1
            await asyncio.sleep(random.uniform(1.5, 2.5))

        return all_urls[:max_offres]

    # ------------------------------------------------------------------
    # Search + scrape details
    # ------------------------------------------------------------------

    async def search_and_scrape(
        self,
        keywords: str = "",
        pays: str = "",
        date_publiee: str = "",
        mode_travail: list | None = None,
        type_contrat: list | None = None,
        niveau_experience: list | None = None,
        max_offres: int = 20,
    ) -> list[dict]:
        """
        Search for job offers then scrape details for each result.

        Args:
            keywords:          Search terms.
            pays:              Country name.
            date_publiee:      Recency filter.
            mode_travail:      Workplace type filter.
            type_contrat:      Contract type filter.
            niveau_experience: Experience level filter.
            max_offres:        Maximum number of job offers to return.

        Returns:
            List of job detail dicts.
        """
        urls = await self.search(
            keywords, pays, date_publiee,
            mode_travail, type_contrat, niveau_experience,
            max_offres,
        )
        scraper = JobScraper(self.page)
        results = []
        for i, url in enumerate(urls, 1):
            print(f"  [{i:2d}/{len(urls)}] {url}")
            try:
                job = await scraper.scrape(url)
                results.append(job)
            except Exception as e:
                print(f"         ⚠️ Erreur : {e}")
                results.append({"linkedin_url": url, "error": str(e)})
            await asyncio.sleep(random.uniform(2, 4))
        return results

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _extract_job_urls_from_page(self) -> list[str]:
        urls = []
        try:
            await self.page.wait_for_selector('a[href*="/jobs/view/"]', timeout=10000)
            await asyncio.sleep(1)

            await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
            await asyncio.sleep(1)
            await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(1)

            links = await self.page.locator('a[href*="/jobs/view/"]').all()
            seen: set[str] = set()
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
