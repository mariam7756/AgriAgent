import asyncio
import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup

from helpers.config import get_settings

logger = logging.getLogger("uvicorn.error")


class AgroLibCrawler:
    DEFAULT_LABELS = [
        "الانتاج النباتي",
        "الانتاج الحيواني",
        "وقاية النبات",
        "علوم الاغذية",
        "الري و المياه",
        "علم الحشرات",
        "الاقتصاد الزراعي",
        "علوم البيئة و التلوث",
    ]

    def __init__(self, base_url: Optional[str] = None):
        settings = get_settings()
        self.base_url = (base_url or settings.AGRO_LIB_BASE_URL).rstrip("/")
        self.crawl_delay = settings.AGRO_LIB_CRAWL_DELAY
        self.page_size = 20

    def _feed_url(self, label: str, start_index: int) -> str:
        encoded_label = quote(label)
        return (
            f"{self.base_url}/feeds/posts/default/-/{encoded_label}"
            f"?alt=json&max-results={self.page_size}&start-index={start_index}"
        )

    def _extract_post_url(self, entry: dict) -> Optional[str]:
        for link in entry.get("link", []):
            if link.get("rel") == "alternate":
                return link.get("href")
        return None

    def _html_to_text(self, html: str) -> str:
        if not html:
            return ""
        soup = BeautifulSoup(html, "html.parser")
        return soup.get_text(separator="\n", strip=True)

    def _extract_author(self, entry: dict) -> str:
        authors = entry.get("author", [])
        if not authors:
            return "المكتبة الزراعية الشاملة"

        author = authors[0].get("name", {}).get("$t", "").strip()
        return author or "المكتبة الزراعية الشاملة"

    def _parse_entry(self, entry: dict, category: str) -> Optional[Dict]:
        source_url = self._extract_post_url(entry)
        if not source_url:
            return None

        title = entry.get("title", {}).get("$t", "").strip()
        published_at = entry.get("published", {}).get("$t", "")
        content_html = entry.get("content", {}).get("$t") or entry.get("summary", {}).get("$t", "")
        content = self._html_to_text(content_html)

        if len(content) < 50:
            return None

        return {
            "source_url": source_url,
            "title": title,
            "category": category,
            "author": self._extract_author(entry),
            "language": "ar",
            "source_type": "web",
            "source_name": "agro-lib",
            "content": content,
            "content_hash": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            "published_at": published_at[:10] if published_at else None,
            "last_crawled_at": datetime.now(timezone.utc).isoformat(),
        }

    async def fetch_label_page(
        self,
        client: httpx.AsyncClient,
        label: str,
        page_no: int,
    ) -> List[Dict]:
        start_index = (page_no - 1) * self.page_size + 1
        feed_url = self._feed_url(label=label, start_index=start_index)

        try:
            response = await client.get(feed_url, timeout=30.0, follow_redirects=True)
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            logger.error(f"Failed to fetch label '{label}' page {page_no}: {exc}")
            return []

        entries = payload.get("feed", {}).get("entry", [])
        if not entries:
            return []

        posts = []
        for entry in entries:
            parsed = self._parse_entry(entry=entry, category=label)
            if parsed:
                posts.append(parsed)

        return posts

    async def _fetch_full_post(self, client: httpx.AsyncClient, post: Dict) -> Dict:
        try:
            response = await client.get(post["source_url"], timeout=30.0, follow_redirects=True)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            body = soup.select_one(".post-body, .entry-content, article")
            if not body:
                return post

            full_text = body.get_text(separator="\n", strip=True)
            if len(full_text) > len(post["content"]):
                post["content"] = full_text
                post["content_hash"] = hashlib.sha256(full_text.encode("utf-8")).hexdigest()
        except Exception as exc:
            logger.warning(f"Could not fetch full post {post['source_url']}: {exc}")

        return post

    async def crawl_labels(self, labels: Optional[List[str]] = None, max_pages: int = 2) -> List[Dict]:
        labels = labels or self.DEFAULT_LABELS
        all_posts: List[Dict] = []
        seen_urls = set()

        async with httpx.AsyncClient() as client:
            for label in labels:
                for page_no in range(1, max_pages + 1):
                    posts = await self.fetch_label_page(
                        client=client,
                        label=label,
                        page_no=page_no,
                    )

                    if not posts:
                        break

                    for post in posts:
                        if post["source_url"] in seen_urls:
                            continue
                        post = await self._fetch_full_post(client=client, post=post)
                        seen_urls.add(post["source_url"])
                        all_posts.append(post)
                        await asyncio.sleep(self.crawl_delay)

        return all_posts
