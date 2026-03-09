"""
CompanyScraper — scrapes LinkedIn company /about/ pages.
"""
import asyncio
import urllib.parse


class CompanyScraper:
    """Scrapes company information from a LinkedIn /about/ page."""

    LABEL_MAP = {
        # website
        "site web":             "website",
        "website":              "website",
        # phone
        "téléphone":            "phone",
        "phone":                "phone",
        # headquarters
        "siège social":         "headquarters",
        "siège":                "headquarters",
        "headquarters":         "headquarters",
        "location":             "headquarters",
        # founded
        "fondée":               "founded",
        "created":              "founded",
        "founded":              "founded",
        # industry
        "secteur":              "industry",
        "industry":             "industry",
        "industries":           "industry",
        # company type
        "type d'entreprise":    "company_type",
        "company type":         "company_type",
        "type":                 "company_type",
        # company size
        "taille de l'entreprise": "company_size",
        "taille":               "company_size",
        "company size":         "company_size",
        # specialties
        "spécialisations":      "specialties",
        "specialties":          "specialties",
        "specialization":       "specialties",
    }

    def __init__(self, page) -> None:
        self.page = page

    async def scrape(self, linkedin_url: str) -> dict:
        """
        Scrape company information from a LinkedIn company page.

        Args:
            linkedin_url: Full LinkedIn company URL
                          (e.g. "https://www.linkedin.com/company/microsoft/").

        Returns:
            Dict with keys: linkedin_url, name, about_us, website, phone,
            headquarters, founded, industry, company_type, company_size,
            specialties.
        """
        url_about = linkedin_url.rstrip("/") + "/about/"
        await self.page.goto(url_about, wait_until="domcontentloaded")
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

        # --- Name ---
        try:
            result["name"] = (await self.page.locator("h1").first.inner_text()).strip()
        except Exception:
            pass

        # --- About us ---
        try:
            sections = await self.page.locator("section").all()
            for section in sections:
                text = await section.inner_text()
                if any(kw in text[:60] for kw in ["Vue d'ensemble", "Overview", "À propos"]):
                    paras = await section.locator("p").all()
                    texts = [(await p.inner_text()).strip() for p in paras]
                    best = max(texts, key=len, default="")
                    if best:
                        result["about_us"] = best
                        break
        except Exception as e:
            print(f"  ⚠️ about_us error: {e}")

        # --- dt/dd label parsing (FR + EN) ---
        try:
            dts = await self.page.locator("dt").all()
            for dt in dts:
                label_raw = (await dt.inner_text()).strip()
                label = label_raw.lower()

                field = None
                for key, val in self.LABEL_MAP.items():
                    if key in label:
                        field = val
                        break
                if field is None:
                    continue

                dd = dt.locator("xpath=following-sibling::dd[1]")
                if await dd.count() == 0:
                    continue

                if field == "website":
                    a_tag = dd.locator("a").first
                    if await a_tag.count() > 0:
                        href = await a_tag.get_attribute("href") or ""
                        # Decode LinkedIn redirect (/redir/redirect?url=…)
                        if "redirect" in href:
                            parsed = urllib.parse.urlparse(href)
                            params = urllib.parse.parse_qs(parsed.query)
                            href = urllib.parse.unquote(params.get("url", [href])[0])
                        result["website"] = href
                    else:
                        result["website"] = (await dd.inner_text()).strip().split("\n")[0]
                else:
                    lines = [
                        line.strip()
                        for line in (await dd.inner_text()).strip().split("\n")
                        if line.strip()
                    ]
                    if lines:
                        result[field] = lines[0]

        except Exception as e:
            print(f"  ⚠️ dt/dd parsing error: {e}")

        return result
