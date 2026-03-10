"""
JobScraper — scrapes details from a LinkedIn job posting.
"""
import asyncio
import random

# Texts from UI buttons/labels that should never be treated as a company name
_COMPANY_SKIP_TEXTS = {
    "voir plus", "see more", "voir", "see", "suivre", "follow",
    "voir l'entreprise", "view company", "plus", "more",
}


class JobScraper:
    """Scrapes details from a single LinkedIn job offer page."""

    def __init__(self, page) -> None:
        self.page = page

    async def scrape(self, job_url: str) -> dict:
        """
        Scrape a LinkedIn job offer.

        Args:
            job_url: Full URL to the job posting
                     (e.g. "https://www.linkedin.com/jobs/view/1234567890/").

        Returns:
            Dict with keys: linkedin_url, job_title, company,
            company_linkedin_url, location, workplace_type, posted_date,
            applicant_count, job_type, experience_level, seniority_level,
            job_description.
        """
        await self.page.goto(job_url, wait_until="domcontentloaded")
        # Wait for job-specific content rather than a generic h1 (which may
        # belong to the navigation bar and be empty / image-only).
        try:
            await self.page.wait_for_selector(
                ".job-details-jobs-unified-top-card__job-title, "
                ".jobs-unified-top-card__job-title, "
                ".jobs-details-top-card__job-title, "
                "h1.top-card-layout__title, "
                "h1.topcard__title, "
                "h1.t-24, "
                "h1",
                timeout=15000,
            )
        except Exception:
            pass
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
            "seniority_level": None,
            "job_description": None,
        }

        # --- Job title ---
        # Try targeted selectors first, then progressively broader ones.
        # Includes both logged-in interface classes and public/guest page classes.
        _TITLE_SELECTORS = [
            ".job-details-jobs-unified-top-card__job-title h1",
            ".job-details-jobs-unified-top-card__job-title a",
            ".job-details-jobs-unified-top-card__job-title",
            ".job-details-jobs-unified-top-card__job-title-link",
            ".jobs-unified-top-card__job-title h1",
            ".jobs-unified-top-card__job-title",
            ".jobs-details-top-card__job-title",
            # Public/guest page selectors
            "h1.top-card-layout__title",
            "h1.topcard__title",
            "h1.t-24",
            "h2.t-24",
            ".t-24.t-bold",
            "h1",
        ]
        for sel in _TITLE_SELECTORS:
            try:
                elem = self.page.locator(sel).first
                if await elem.count() > 0:
                    text = (await elem.inner_text()).strip()
                    if text:
                        result["job_title"] = text
                        break
            except Exception:
                continue

        # JavaScript fallback for job title when CSS selectors miss
        if result["job_title"] is None:
            try:
                title = await self.page.evaluate(
                    f"""() => {{
                        const sels = {_TITLE_SELECTORS!r};
                        for (const s of sels) {{
                            const el = document.querySelector(s);
                            if (el) {{
                                const t = (el.innerText || el.textContent || '').trim();
                                if (t) return t;
                            }}
                        }}
                        return null;
                    }}"""
                )
                if title:
                    result["job_title"] = title
            except Exception:
                pass

        # --- Company + company LinkedIn URL ---
        # 1. Try specific company-name containers first (avoids picking up
        #    "Voir plus" / "See more" buttons that link to the company page).
        company_name_selectors = [
            ".job-details-jobs-unified-top-card__company-name a",
            ".job-details-jobs-unified-top-card__company-name",
            ".jobs-unified-top-card__company-name a",
            ".jobs-unified-top-card__company-name",
            ".job-details-jobs-unified-top-card__primary-description-without-tagline a[href*='/company/']",
            ".artdeco-entity-lockup__title a[href*='/company/']",
            ".artdeco-entity-lockup__title",
            # Public/guest page selector
            ".topcard__org-name-link",
        ]
        for sel in company_name_selectors:
            try:
                elem = self.page.locator(sel).first
                if await elem.count() > 0:
                    text = (await elem.inner_text()).strip()
                    if text and len(text) > 1 and text.lower() not in _COMPANY_SKIP_TEXTS:
                        # len > 1 filters out lone bullet or separator characters
                        result["company"] = text
                        href = (await elem.get_attribute("href")) or ""
                        if not href:
                            # The container itself is not an anchor; look for a
                            # child anchor linking to a company page.
                            try:
                                child = self.page.locator(sel + " a[href*='/company/']").first
                                if await child.count() > 0:
                                    href = (await child.get_attribute("href")) or ""
                            except Exception:
                                pass
                        if href:
                            clean = href.split("?")[0]
                            if not clean.startswith("http"):
                                clean = "https://www.linkedin.com" + clean
                            result["company_linkedin_url"] = clean
                        break
            except Exception:
                continue

        # 2. Fallback: scan all /company/ links and skip UI-button texts
        if result["company"] is None:
            try:
                company_links = await self.page.locator('a[href*="/company/"]').all()
                for link in company_links:
                    href = await link.get_attribute("href") or ""
                    href_path = href.split("?")[0]
                    segments = [s for s in href_path.split("/") if s]
                    company_idx = next(
                        (i for i, s in enumerate(segments) if s == "company"), None
                    )
                    # Skip sub-pages like /life, /jobs, /about
                    if company_idx is not None and len(segments) > company_idx + 2:
                        continue
                    text = (await link.inner_text()).strip()
                    if (
                        text
                        and len(text) > 1  # filter lone bullet/separator characters
                        and text.lower() not in _COMPANY_SKIP_TEXTS
                    ):
                        result["company"] = text
                        clean = href_path
                        if not clean.startswith("http"):
                            clean = "https://www.linkedin.com" + clean
                        result["company_linkedin_url"] = clean
                        break
            except Exception:
                pass

        # --- Location / workplace type / posted date / applicant count ---

        # Public/guest page: direct selectors for date and applicant count
        try:
            posted = self.page.locator(".posted-time-ago__text")
            if await posted.count() > 0:
                t = (await posted.first.inner_text()).strip()
                if t:
                    result["posted_date"] = t
        except Exception:
            pass

        try:
            applicants = self.page.locator(".num-applicants__caption")
            if await applicants.count() > 0:
                t = (await applicants.first.inner_text()).strip()
                if t:
                    result["applicant_count"] = t
        except Exception:
            pass

        # Public/guest page: location is in .topcard__flavor--bullet (but not --metadata)
        if result["location"] is None:
            try:
                loc_spans = await self.page.locator(".topcard__flavor--bullet").all()
                for span in loc_spans:
                    classes = (await span.get_attribute("class")) or ""
                    if "topcard__flavor--metadata" not in classes:
                        t = (await span.inner_text()).strip()
                        if t and len(t) > 1:
                            result["location"] = t
                            break
            except Exception:
                pass

        try:
            info_spans = await self.page.locator(
                ".job-details-jobs-unified-top-card__primary-description-without-tagline span, "
                ".job-details-jobs-unified-top-card__primary-description-container span, "
                ".job-details-jobs-unified-top-card__primary-description span, "
                ".job-details-jobs-unified-top-card__tertiary-description span, "
                ".jobs-unified-top-card__subtitle-primary-grouping span, "
                ".jobs-unified-top-card__primary-description span, "
                ".jobs-unified-top-card__tertiary-description span, "
                ".tvm__text span, "
                "h1 ~ div span, h1 ~ p span"
            ).all()
            info_texts = []
            for span in info_spans:
                t = (await span.inner_text()).strip()
                if t and t not in ("·", "•", "") and len(t) > 1:
                    info_texts.append(t)

            for t in info_texts:
                tl = t.lower()
                if any(
                    w in tl
                    for w in ["remote", "hybride", "hybrid", "on-site", "présentiel",
                              "télétravail", "en présentiel", "full remote"]
                ):
                    result["workplace_type"] = t
                elif result["posted_date"] is None and any(
                    w in tl
                    for w in ["il y a", "ago", "heure", "jour", "semaine", "mois",
                              "hour", "day", "week", "month", "minute"]
                ):
                    result["posted_date"] = t
                elif result["applicant_count"] is None and any(
                    w in tl for w in ["candidat", "applicant", "postulant", "candidature"]
                ):
                    result["applicant_count"] = t
                elif result["location"] is None and (
                    "," in t or any(c.isupper() for c in t[1:])
                ):
                    result["location"] = t
        except Exception:
            pass

        # --- Job type + seniority / experience level from "Job details" section ---

        # Public/guest page: structured criteria list with labelled items
        try:
            criteria_items = await self.page.locator(".description__job-criteria-item").all()
            for item in criteria_items:
                try:
                    header_el = item.locator(".description__job-criteria-subheader").first
                    value_el = item.locator(".description__job-criteria-text").first
                    if await header_el.count() > 0 and await value_el.count() > 0:
                        header = (await header_el.inner_text()).strip().lower()
                        value = (await value_el.inner_text()).strip()
                        if "seniority" in header or "niveau" in header or "ancienneté" in header:
                            if result["seniority_level"] is None:
                                result["seniority_level"] = value
                            if result["experience_level"] is None:
                                result["experience_level"] = value
                        elif "employment" in header or "type de contrat" in header or "type d'emploi" in header:
                            result["job_type"] = value
                except Exception:
                    continue
        except Exception:
            pass

        try:
            detail_items = await self.page.locator(
                ".job-details-jobs-unified-top-card__job-insight span, "
                ".jobs-unified-top-card__job-insight span, "
                ".job-details-jobs-unified-top-card__job-insight li, "
                ".jobs-unified-top-card__job-insight li, "
                ".job-details-jobs-unified-top-card__job-insight-item span, "
                ".jobs-details-top-card__job-info-container span, "
                ".jobs-details__details li"
            ).all()

            for li in detail_items:
                text = (await li.inner_text()).strip()
                tl = text.lower()

                # Job type
                if result["job_type"] is None and any(
                    w in tl
                    for w in ["temps plein", "full-time", "temps partiel", "part-time",
                              "contrat", "stage", "intérim", "bénévole", "freelance",
                              "cdi", "cdd", "interim"]
                ):
                    result["job_type"] = text

                # Experience / seniority
                if result["experience_level"] is None and any(
                    w in tl
                    for w in ["junior", "senior", "débutant", "confirmé", "manager",
                              "directeur", "entry", "associate", "mid-senior",
                              "director", "executive", "internship"]
                ):
                    result["experience_level"] = text

                # Seniority level (LinkedIn often has a separate field)
                if result["seniority_level"] is None and any(
                    w in tl
                    for w in ["seniority", "niveau", "ancienneté"]
                ):
                    result["seniority_level"] = text
        except Exception:
            pass

        # --- Full job description (not truncated) ---
        try:
            desc_selectors = [
                ".job-details-jobs-unified-top-card__job-description",
                ".jobs-description__content",
                ".jobs-description",
                "#job-details",
                "#job-details article",
                ".jobs-box__html-content",
                # Public/guest page selectors
                ".show-more-less-html__markup",
                ".description__text",
                "article",
            ]
            for sel in desc_selectors:
                elem = self.page.locator(sel).first
                if await elem.count() > 0:
                    text = (await elem.inner_text()).strip()
                    if len(text) > 100:
                        result["job_description"] = text
                        break
        except Exception:
            pass

        return result
