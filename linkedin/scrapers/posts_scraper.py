"""
PostsScraper — scrapes posts from a LinkedIn company page.
"""
from linkedin_scraper.scrapers.company_posts import CompanyPostsScraper as _LibScraper


class PostsScraper:
    """Scrapes recent posts from a LinkedIn company page."""

    def __init__(self, page) -> None:
        self.page = page
        self._scraper = _LibScraper(page)

    async def scrape(self, company_url: str, limit: int = 10) -> list[dict]:
        """
        Retrieve the most recent posts from a company page.

        Args:
            company_url: Full LinkedIn company URL.
            limit:       Maximum number of posts to return.

        Returns:
            List of dicts with post data (text, posted_date, reactions_count,
            comments_count, reposts_count, …).
        """
        raw_posts = await self._scraper.scrape(company_url, limit=limit)
        results = []
        for post in raw_posts:
            if hasattr(post, "model_dump"):
                results.append(post.model_dump())
            elif isinstance(post, dict):
                results.append(post)
            else:
                results.append(vars(post))
        return results
