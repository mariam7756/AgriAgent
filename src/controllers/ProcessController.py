from .BaseController import BaseController
from .ProjectController import ProjectController
import os
import re
import hashlib
from langchain_community.document_loaders import TextLoader
from langchain_community.document_loaders import PyMuPDFLoader

from models import ProcessingEnum
from typing import List, Dict, Optional
from dataclasses import dataclass, field






@dataclass
class Document:
    page_content: str
    metadata: dict


# ─────────────────────────────────────────────────────────────────────────────
# Agricultural metadata inference — same constants as pipeline.py
# ─────────────────────────────────────────────────────────────────────────────

CROP_INFERENCE = {
    "زيتون": "olive", "الزيتون": "olive", "olive": "olive",
    "قمح": "wheat", "القمح": "wheat", "wheat": "wheat",
    "ذرة": "corn", "الذرة": "corn", "corn": "corn", "maize": "corn",
    "طماطم": "tomato", "الطماطم": "tomato", "tomato": "tomato",
    "أرز": "rice", "الأرز": "rice", "rice": "rice",
    "قطن": "cotton", "القطن": "cotton", "cotton": "cotton",
    "بطاطس": "potato", "البطاطس": "potato", "potato": "potato",
    "بصل": "onion", "البصل": "onion", "onion": "onion",
    "فلفل": "pepper", "الفلفل": "pepper", "pepper": "pepper",
    "قصب": "sugarcane", "sugarcane": "sugarcane",
    "فاكهة": "fruit", "خضر": "vegetables", "خضروات": "vegetables",
}

TOPIC_INFERENCE = {
    "تسميد": "fertilization", "سماد": "fertilization", "يوريا": "fertilization",
    "فوسفات": "fertilization", "بوتاسيوم": "fertilization", "نيتروجين": "fertilization",
    "fertiliz": "fertilization", "nitrogen": "fertilization",
    "ري": "irrigation", "سقي": "irrigation", "مياه": "irrigation",
    "irrigat": "irrigation", "water": "irrigation",
    "مرض": "disease_management", "فطر": "disease_management", "لفحة": "disease_management",
    "بياض": "disease_management", "عفن": "disease_management",
    "disease": "disease_management", "fungus": "disease_management",
    "حشرة": "pest_management", "آفة": "pest_management", "دودة": "pest_management",
    "مبيد": "pest_management", "pest": "pest_management", "insect": "pest_management",
    "زراعة": "cultivation", "بذر": "cultivation", "شتل": "cultivation",
    "إنتاج": "cultivation", "cultivat": "cultivation",
    "تربة": "soil_management", "soil": "soil_management", "خصوبة": "soil_management",
    "حصاد": "harvest", "harvest": "harvest", "قطاف": "harvest",
    "وقاية": "pest_management", "مكافحة": "pest_management",
    "تغذية": "fertilization", "فسيولوجيا": "physiology",
    "تقليم": "cultivation", "تفتيش": "cultivation",
}

# أنماط الـ noise في الكتب العربية
NOISE_PATTERNS = [
    re.compile(r"^\s*\d+\s*$"),                          # أرقام الصفحات وحدها
    re.compile(r"^صفحة\s+\d+", re.MULTILINE),            # "صفحة 5"
    re.compile(r"^Page\s+\d+", re.IGNORECASE),           # "Page 5"
    re.compile(r"^-\s*\d+\s*-$"),                        # "- 5 -"
    re.compile(r"^[\u0600-\u06FF\s]{1,30}$"),            # سطر عربي قصير جداً (هيدر/فوتر)
    re.compile(r"جميع الحقوق محفوظة"),
    re.compile(r"all rights reserved", re.IGNORECASE),
    re.compile(r"©|copyright", re.IGNORECASE),
    re.compile(r"^الفهرس\s*$", re.MULTILINE),
    re.compile(r"^فهرس المحتويات\s*$", re.MULTILINE),
    re.compile(r"^\.\.\.\s*\d+$", re.MULTILINE),         # "....... 5" (فهرس)
    re.compile(r"^[\.\-\_\s]{5,}$", re.MULTILINE),       # خطوط فاصلة
    re.compile(r"بسم الله الرحمن الرحيم\s*$"),
]

HEADING_PATTERNS = re.compile(
    r"^(الفصل|الباب|القسم|المحور|الوحدة|Chapter|Section|Unit)\s+[\w\d]+",
    re.MULTILINE | re.IGNORECASE,
)


def _infer_crop_from_text(text: str) -> str:
    text_lower = text.lower()
    for keyword, crop in CROP_INFERENCE.items():
        if keyword in text_lower:
            return crop
    return "general"


def _infer_topic_from_text(text: str) -> str:
    text_lower = text.lower()
    for keyword, topic in TOPIC_INFERENCE.items():
        if keyword in text_lower:
            return topic
    return "general"


def _get_source_rank(source_type: str) -> int:
    return {"book": 4, "manual": 5, "guide": 5, "seed": 3, "faq": 2}.get(source_type, 6)


def _content_hash(text: str) -> str:
    return hashlib.md5(text.strip().encode("utf-8")).hexdigest()


class ProcessController(BaseController):

    def __init__(self, project_id: str):
        super().__init__()
        
        self.project_id = project_id
        self.project_path = ProjectController().get_project_path(project_id=project_id)
        self._seen_hashes: set = set()

    def get_file_extension(self, file_id: str):
        return os.path.splitext(file_id)[-1]

    def get_file_loader(self, file_id: str):
        
        file_ext = self.get_file_extension(file_id=file_id)
        file_path = os.path.join(self.project_path, file_id)

        if not os.path.exists(file_path):
            
            return None
        
        if file_ext == ProcessingEnum.TXT.value:
            return TextLoader(file_path, encoding="utf-8")
        
        if file_ext == ProcessingEnum.PDF.value:
            return PyMuPDFLoader(file_path)
        
        return None

    def get_file_content(self, file_id: str):
        
        loader = self.get_file_loader(file_id=file_id)
        if loader:
            return loader.load()
        
        return None

    # ─────────────────────────────────────────────────────────────────────
    # Metadata extraction — الجوهر اللي كان ناقص
    # ─────────────────────────────────────────────────────────────────────

    def extract_agri_metadata(self, file_id: str, content_sample: str) -> dict:
        """
        يستخرج metadata زراعية من اسم الملف + أول 2000 حرف من المحتوى.
        النتيجة بتتحفظ في chunk_metadata لكل chunk.
        """
        file_name = os.path.splitext(file_id)[0].lower().replace("_", " ")
        sample = (file_name + " " + content_sample[:2000]).lower()

        crop = _infer_crop_from_text(file_name) or _infer_crop_from_text(sample)
        topic = _infer_topic_from_text(file_name) or _infer_topic_from_text(sample)

        source_type = "book"
        if any(w in file_name for w in ["دليل", "guide", "manual", "مرجع"]):
            source_type = "manual"
        elif any(w in file_name for w in ["مذكرة", "notes", "تطبيقات"]):
            source_type = "manual"
        elif any(w in file_name for w in ["علم", "فسيولوجيا", "physiology"]):
            source_type = "book"

        document_name = (
            os.path.splitext(file_id)[0]
            .replace("_", " ")
            .replace("-", " ")
            .strip()
        )

        return {
            "crop": crop or "general",
            "topic": topic or "general",
            "document_name": document_name,
            "title": document_name,
            "source_type": source_type,
            "source_rank": _get_source_rank(source_type),
            "language": "ar",
            "country": "EG",
            "author": "",
            "source_url": f"local://{file_id}",
            "category": topic or "general",
        }

    # ─────────────────────────────────────────────────────────────────────
    # Text cleaning — يشيل الـ noise
    # ─────────────────────────────────────────────────────────────────────

    def clean_pdf_text(self, text: str) -> str:
        """
        يشيل من نص الـ PDF:
        - أرقام الصفحات
        - الهيدر والفوتر
        - الفهارس
        - حقوق النشر
        - الأسطر القصيرة الفارغة من المعنى
        """
        lines = text.split("\n")
        cleaned_lines = []

        for line in lines:
            stripped = line.strip()

            # تجاهل الأسطر الفارغة المتتالية
            if not stripped:
                if cleaned_lines and cleaned_lines[-1] != "":
                    cleaned_lines.append("")
                continue

            # تطبيق patterns الـ noise
            is_noise = False
            for pattern in NOISE_PATTERNS:
                if pattern.search(stripped):
                    is_noise = True
                    break

            if is_noise:
                continue

            # تجاهل الأسطر القصيرة جداً (أقل من 10 حروف) اللي مش headings
            if len(stripped) < 10 and not HEADING_PATTERNS.match(stripped):
                continue

            cleaned_lines.append(stripped)

        return "\n".join(cleaned_lines).strip()

    # ─────────────────────────────────────────────────────────────────────
    # Smart chunking — paragraph + heading aware
    # ─────────────────────────────────────────────────────────────────────

    def process_file_content(
        self,
        file_content: list,
        file_id: str,
        chunk_size: int = 800,
        overlap_size: int = 100,
    ):
        """
        Pipeline كامل:
        raw pages → merge → clean → smart chunk → enrich metadata
        """
        # دمج كل الصفحات
        full_text = "\n".join([
            rec.page_content for rec in file_content if rec.page_content
        ])

        # تنظيف النص
        cleaned_text = self.clean_pdf_text(full_text)

        if not cleaned_text.strip():
            return []

        # استخراج الـ agri metadata
        agri_meta = self.extract_agri_metadata(
            file_id=file_id,
            content_sample=cleaned_text[:3000],
        )

        # smart chunking
        chunks = self.smart_chunk(
            text=cleaned_text,
            base_metadata=agri_meta,
            chunk_size=chunk_size,
        )

        return chunks

    def smart_chunk(
        self,
        text: str,
        base_metadata: dict,
        chunk_size: int = 800,
    ) -> List[Document]:
        """
        Paragraph-aware + Heading-aware chunking.
        - لا يقطع في منتصف فقرة
        - كل chunk يعرف الفصل والقسم اللي هو فيه
        - deduplication بـ content hash
        """
        self._seen_hashes = set()

        current_chapter = ""
        current_section = ""
        current_chunk = ""
        chunks = []

        # قسم النص لفقرات
        paragraphs = re.split(r"\n{2,}", text)

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # كشف الـ heading
            if HEADING_PATTERNS.match(para) or (len(para) < 80 and para.endswith(":")):
                # احفظ الـ chunk الحالي قبل الـ heading الجديد
                if current_chunk.strip() and len(current_chunk.strip()) > 100:
                    self._save_chunk(
                        chunks=chunks,
                        text=current_chunk.strip(),
                        base_metadata=base_metadata,
                        chapter=current_chapter,
                        section=current_section,
                    )
                    current_chunk = ""

                # حدد مستوى الـ heading
                if any(w in para for w in ["الفصل", "الباب", "Chapter"]):
                    current_chapter = para
                    current_section = ""
                else:
                    current_section = para
                continue

            current_chunk += para + "\n\n"

            # لو الـ chunk وصل الحجم المطلوب — احفظه
            if len(current_chunk) >= chunk_size:
                if current_chunk.strip() and len(current_chunk.strip()) > 100:
                    self._save_chunk(
                        chunks=chunks,
                        text=current_chunk.strip(),
                        base_metadata=base_metadata,
                        chapter=current_chapter,
                        section=current_section,
                    )
                # overlap: خد آخر فقرة للـ chunk الجديد
                paras_in_chunk = [p for p in current_chunk.split("\n\n") if p.strip()]
                overlap_text = paras_in_chunk[-1] if paras_in_chunk else ""
                current_chunk = overlap_text + "\n\n" if overlap_text else ""

        # احفظ المتبقي
        if current_chunk.strip() and len(current_chunk.strip()) > 100:
            self._save_chunk(
                chunks=chunks,
                text=current_chunk.strip(),
                base_metadata=base_metadata,
                chapter=current_chapter,
                section=current_section,
            )

        return chunks

    def _save_chunk(
        self,
        chunks: list,
        text: str,
        base_metadata: dict,
        chapter: str,
        section: str,
    ):
        """يحفظ chunk بعد deduplication."""
        h = _content_hash(text)
        if h in self._seen_hashes:
            return
        self._seen_hashes.add(h)

        metadata = {
            **base_metadata,
            "chapter": chapter,
            "section": section,
        }
        chunks.append(Document(page_content=text, metadata=metadata))

    
    # Legacy method — محتاجة في KnowledgeController للـ seed pipeline
    
    def process_simpler_splitter(
        self,
        texts: List[str],
        metadatas: List[dict],
        chunk_size: int,
        splitter_tag: str = "\n",
    ):
        """
        محتفظ بيها للـ backward compatibility مع KnowledgeController.
        مش بتتستخدم للـ PDFs — بتتستخدم للـ seed text فقط.
        """
        full_text = " ".join(texts)
        lines = [doc.strip() for doc in full_text.split(splitter_tag) if len(doc.strip()) > 1]
        chunks = []
        current_chunk = ""

        for line in lines:
            current_chunk += line + splitter_tag
            if len(current_chunk) >= chunk_size:
                chunks.append(Document(
                    page_content=current_chunk.strip(),
                    metadata=metadatas[0] if metadatas else {},
                ))
                
                current_chunk = ""

        if current_chunk.strip():
            chunks.append(Document(
                page_content=current_chunk.strip(),
                metadata=metadatas[0] if metadatas else {},
            ))

        return chunks