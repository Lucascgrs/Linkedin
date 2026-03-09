#!/usr/bin/env python3
"""
ÉTAPE 3 : Scraper les posts récents d'une entreprise.
"""
import asyncio
import json
from linkedin_scraper.scrapers.company_posts import CompanyPostsScraper
from linkedin_scraper.core.browser import BrowserManager


COMPANY_URL = "https://www.linkedin.com/company/microsoft/"
NB_POSTS = 5  # Nombre de posts à récupérer


async def test_posts_scraping():
    print(f"\n📝 Test scraping posts de : {COMPANY_URL}\n")

    async with BrowserManager(headless=False, slow_mo=500) as browser:
        await browser.load_session("linkedin_session.json")
        print("✓ Session chargée")

        scraper = CompanyPostsScraper(browser.page)

        print(f"🔍 Récupération des {NB_POSTS} derniers posts...")
        posts = await scraper.scrape(COMPANY_URL, limit=NB_POSTS)

        print(f"\n✓ {len(posts)} posts récupérés\n")
        print("=" * 60)

        for i, post in enumerate(posts, 1):
            print(f"\n📌 Post #{i}")
            print(f"   Date       : {post.posted_date}")
            print(f"   Réactions  : {post.reactions_count}")
            print(f"   Commentaires: {post.comments_count}")
            print(f"   Reposts    : {post.reposts_count}")
            if post.text:
                preview = post.text[:300] + "..." if len(post.text) > 300 else post.text
                print(f"   Texte      : {preview}")
            print("-" * 40)

        # Sauvegarder en JSON
        data = [p.model_dump() for p in posts]
        with open("output_posts.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"\n💾 Posts sauvegardés dans output_posts.json")


if __name__ == "__main__":
    asyncio.run(test_posts_scraping())