import httpx
import asyncio
import logging
from bs4 import BeautifulSoup
from typing import List, Dict, Optional

logger = logging.getLogger("uvicorn.error")


# ===== المصادر الحقيقية =====
KNOWLEDGE_SOURCES = [
    # FAO — مقالات تقنية عن محاصيل مصر، نص HTML كامل
    "https://www.fao.org/4/v9978e/v9978e0e.htm",        # Egypt crops overview
    "https://www.fao.org/4/v9978e/v9978e0f.htm",        # Pest management Egypt
    "https://www.fao.org/4/v9978e/v9978e0g.htm",        # Soil & irrigation Egypt
    "https://www.fao.org/4/y4011e/y4011e00.htm",        # Fertilizer use guide
    "https://www.fao.org/4/y4110e/y4110e00.htm",        # Crop water requirements
    "https://www.fao.org/4/t0234e/t0234e00.htm",        # Wheat production guide
    "https://www.fao.org/4/s8850e/s8850e00.htm",        # Tomato production guide
    "https://www.fao.org/4/t0217e/t0217e00.htm",        # Maize production guide
    "https://www.fao.org/4/w3727e/w3727e00.htm",        # Rice production guide
    "https://www.fao.org/4/y5031e/y5031e00.htm",        # Soil fertility management
    # UMN Extension — نص كامل، أمراض + آفات
    "https://extension.umn.edu/crop-production",
    "https://extension.umn.edu/plant-diseases",
    "https://extension.umn.edu/nutrient-management",
    "https://extension.umn.edu/soil-management",
    # IPM — مكافحة آفات تفصيلية
    "https://ipm.ucanr.edu/agriculture.html",
]

AGRI_KEYWORDS = {
    "wheat", "tomato", "corn", "maize", "cotton", "rice", "potato",
    "fertilizer", "irrigation", "pest", "disease", "soil", "crop",
    "nitrogen", "phosphorus", "potassium", "fungus", "insect",
    "قمح", "طماطم", "ذرة", "قطن", "أرز", "بطاطس", "سماد",
    "ري", "حشرة", "مرض", "تربة", "نيتروجين", "تسميد", "محصول",
}

NOISE_PHRASES = {
    "تنزيل الكتاب", "download book", "click here to download",
    "اضغط هنا للتحميل", "روابط التحميل", "تحميل مباشر",
    "cookie", "javascript", "subscribe", "newsletter",
}


class FAOCrawler:
    """
    يـ crawl مصادر زراعية نصية حقيقية — FAO + UMN Extension + IPM
    بيرجع محتوى نصي زراعي حقيقي قابل للـ embedding
    """

    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (compatible; AgriResearchBot/1.0)",
            "Accept-Language": "ar,en;q=0.9",
        }

    async def fetch_all_sources(self, max_per_source: int = 5) -> List[Dict]:
        """الدالة الرئيسية — تجيب محتوى من كل المصادر"""
        all_docs = []
        async with httpx.AsyncClient(
            headers=self.headers,
            timeout=30,
            follow_redirects=True
        ) as client:
            for url in KNOWLEDGE_SOURCES:
                try:
                    docs = await self._crawl_url(client, url)
                    all_docs.extend(docs[:max_per_source])
                    logger.info(f"FAOCrawler: got {len(docs)} chunks from {url}")
                    await asyncio.sleep(1.5)  # احترام الـ rate limit
                except Exception as e:
                    logger.warning(f"FAOCrawler: failed {url} — {e}")
                    continue
        logger.info(f"FAOCrawler: total {len(all_docs)} clean chunks")
        return all_docs

    async def _crawl_url(self, client: httpx.AsyncClient, url: str) -> List[Dict]:
        """يجيب محتوى URL واحد ويقسمه لـ chunks نظيفة"""
        resp = await client.get(url, timeout=20)
        if resp.status_code != 200:
            return []

        soup = BeautifulSoup(resp.text, "html.parser")

        # احذف العناصر الزائدة
        for tag in soup(["script", "style", "nav", "footer",
                         "header", "aside", "form", "iframe"]):
            tag.decompose()

        # جيب العنوان
        title = ""
        h1 = soup.find("h1")
        if h1:
            title = h1.get_text(strip=True)
        elif soup.find("title"):
            title = soup.find("title").get_text(strip=True)

        # جيب المحتوى
        main = (
            soup.find("article") or
            soup.find("main") or
            soup.find("div", id=lambda i: i and "content" in i.lower()) or
            soup.find("body")
        )
        if not main:
            return []

        raw_text = main.get_text(separator="\n")
        chunks = self._split_to_chunks(raw_text, url, title)
        return chunks

    def _split_to_chunks(
        self, text: str, source_url: str, title: str, chunk_size: int = 800
    ) -> List[Dict]:
        """يقسم النص لـ chunks نظيفة قابلة للـ embedding"""
        # نظف السطور
        lines = [l.strip() for l in text.splitlines()]
        clean_lines = []
        for line in lines:
            if len(line) < 40:
                continue
            if any(noise in line.lower() for noise in NOISE_PHRASES):
                continue
            clean_lines.append(line)

        if not clean_lines:
            return []

        clean_text = "\n".join(clean_lines)

        # تأكد إن المحتوى زراعي
        text_lower = clean_text.lower()
        if not any(kw in text_lower for kw in AGRI_KEYWORDS):
            return []

        # قسم لـ chunks بـ 800 حرف مع overlap
        chunks = []
        words = clean_text.split()
        chunk_words = chunk_size // 6  # ~6 chars per word average

        for i in range(0, len(words), chunk_words - 50):  # 50 word overlap
            chunk = " ".join(words[i: i + chunk_words])
            if len(chunk) < 200:
                continue
            chunks.append({
                "source_name": "fao-extension",
                "source_url": source_url,
                "title": title,
                "content": chunk,
                "language": "ar" if any(c in chunk for c in "أابتثجح") else "en",
                "metadata": {
                    "source_type": "article",
                    "topic": self._detect_topic(chunk.lower()),
                    "tags": self._detect_crop_tags(chunk.lower()),
                },
            })
        return chunks

    def _detect_topic(self, text: str) -> str:
        if any(w in text for w in ["fertiliz", "nitrogen", "phosphor", "تسميد", "سماد"]):
            return "fertilization"
        if any(w in text for w in ["irrigat", "water requir", "ري", "احتياجات مائية"]):
            return "irrigation"
        if any(w in text for w in ["disease", "fungus", "blight", "مرض", "فطر", "عفن"]):
            return "disease_management"
        if any(w in text for w in ["pest", "insect", "aphid", "حشرة", "آفة", "دودة"]):
            return "pest_management"
        if any(w in text for w in ["soil", "salinity", "تربة", "ملوحة", "خصوبة"]):
            return "soil_management"
        return "crop_production"

    def _detect_crop_tags(self, text: str) -> List[str]:
        crop_map = {
            "wheat": ["wheat", "قمح"],
            "tomato": ["tomato", "طماطم"],
            "corn": ["corn", "maize", "ذرة"],
            "cotton": ["cotton", "قطن"],
            "rice": ["rice", "أرز"],
            "potato": ["potato", "بطاطس"],
            "onion": ["onion", "بصل"],
            "pepper": ["pepper", "فلفل"],
            "sugarcane": ["sugar cane", "sugarcane", "قصب السكر"],
        }
        return [crop for crop, keywords in crop_map.items()
                if any(kw in text for kw in keywords)]