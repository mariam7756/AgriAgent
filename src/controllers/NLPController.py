from .BaseController import BaseController
from models.db_schemes import Project, DataChunk
from stores.llm.LLMEnums import DocumentTypeEnum
from stores.llm.LLMEnums import DocumentTypeEnum
from helpers.retrieval import rerank_documents, build_source_citation
from typing import List, Optional
from knowledge.classifier import MessageClassifier
from knowledge.router import KnowledgeRouter
from services.conversation.active_entity_scope import ActiveEntityScope
import re
import json



class NLPController(BaseController):
    RETRIEVAL_CANDIDATE_MULTIPLIER = 5
    MIN_CANDIDATE_POOL = 25

    # لو ظهرت حروف من سكريبت مش عربي/لاتيني في الرد (علامة على hallucination/خلط لغات
    # من الموديل)، نشيلها بدل ما نبعتها للمستخدم زي ما هي.
    _FOREIGN_SCRIPT_PATTERN = re.compile(
        r"[^\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF"  # عربي
        r"\u0020-\u007E"  # ASCII (لاتيني، أرقام، علامات ترقيم، إيموجي أساسي)
        r"\u2000-\u206F"  # علامات ترقيم عامة
        r"\U0001F300-\U0001FAFF"  # إيموجي
        r"]"
    )

    def __init__(self, vectordb_client, generation_client, 
                 embedding_client, template_parser):
        super().__init__()

        self.vectordb_client = vectordb_client
        self.generation_client = generation_client
        self.embedding_client = embedding_client
        self.template_parser = template_parser
        self.router = KnowledgeRouter()

    def create_collection_name(self, project_id: str):
        return f"collection_{self.vectordb_client.default_vector_size}_{project_id}".strip()
        
    
    async def reset_vector_db_collection(self, project: Project):
        collection_name = self.create_collection_name(project_id=project.project_id)
        return await self.vectordb_client.delete_collection(collection_name=collection_name)
    
    async def get_vector_db_collection_info(self, project: Project):
        collection_name = self.create_collection_name(project_id=project.project_id)
        collection_info = await self.vectordb_client.get_collection_info(collection_name=collection_name)

        return json.loads(
            json.dumps(collection_info, default=lambda x: x.__dict__)
        )
    
    async def index_into_vector_db(self, project: Project, chunks: List[DataChunk],
                                   chunks_ids: List[int], 
                                   do_reset: bool = False):
        
        
        collection_name = self.create_collection_name(project_id=project.project_id)

        
        texts = [ c.chunk_text for c in chunks ]
        metadata = [ c.chunk_metadata for c in  chunks]
        vectors = self.embedding_client.embed_text(
            text=texts,
            document_type=DocumentTypeEnum.DOCUMENT.value,
        )
        if not vectors:
            return False

        if isinstance(vectors[0], (int, float)):
            vectors = [vectors]

        if len(vectors) != len(chunks_ids):
            return False

        # step3: create collection if not exists
        _ = await self.vectordb_client.create_collection(
            collection_name=collection_name,
            embedding_size=self.embedding_client.embedding_size,
            do_reset=do_reset,
        )

        inserted = await self.vectordb_client.insert_many(
            collection_name=collection_name,
            texts=texts,
            metadata=metadata,
            vectors=vectors,
            record_ids=chunks_ids,
        )

        return bool(inserted)

    async def search_vector_db_collection(self, project: Project, text: str, limit: int = 10, current_crop: Optional[str] = None):

        collection_name = self.create_collection_name(project_id=project.project_id)

        # لو المحصول الحالي معروف، نضمّه في نص البحث نفسه — عشان الـ embedding
        # يبقى مقيّد بالمحصول ده، مش نص عام ممكن يطابق أي محصول تاني (السبب
        # المباشر في مشكلة رجوع معلومات عن القمح وقت الكلام عن النعناع).
        search_text = f"{current_crop} {text}" if current_crop else text

        vectors = self.embedding_client.embed_text(
            text=search_text,
            document_type=DocumentTypeEnum.QUERY.value,
        )

        if not vectors:
        
            return False
        

        if isinstance(vectors[0], (int, float)):
            query_vector = vectors
        elif isinstance(vectors, list) and len(vectors) > 0:
            query_vector = vectors[0]
        else:
            return False

        if not query_vector:
            return False

        candidate_limit = max(limit * self.RETRIEVAL_CANDIDATE_MULTIPLIER, self.MIN_CANDIDATE_POOL)
        
        
        results = await self.vectordb_client.search_by_vector(
            collection_name=collection_name,
            vector=query_vector,
            limit=candidate_limit,
        )

        if not results:
            return []

        seen = set()
        unique_docs = []
        for doc in results:
            dedupe_key = doc.text.strip()
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            unique_docs.append(doc)
        return rerank_documents(
            documents=unique_docs,
            query=text,
            limit=limit,
        )
    
    def _is_context_relevant(self, query: str, docs: list, current_crop: Optional[str] = None, min_score: float = 0.35) -> bool:
        if not docs:
            return False

        # فلتر موحّد (Active Entity Scope) بدل شرط inline كان مكرر هنا ومرة
        # تانية في KnowledgeController بمنطق مختلف — دلوقتي مصدر واحد للحقيقة.
        scope = ActiveEntityScope(current_crop)
        if not scope.matches([d.text for d in docs]):
            return False

        top_score = max((getattr(d, "score", 0) or 0) for d in docs)
        if top_score < min_score:
            return False
        query_tokens = [w.strip() for w in query.replace("؟", "").split() if len(w.strip()) > 2]
        if not query_tokens:
            return top_score >= min_score
        joined_context = " ".join((d.text or "") for d in docs).lower()
        hits = sum(1 for t in query_tokens if t.lower() in joined_context)
        return hits > 0 or top_score >= 0.55
    
   
    def _sanitize_answer(self, answer: str) -> str:
        """يشيل أي حروف من سكريبت غريب (زي الفيتنامي/الصيني) ظهرت غلط في التوليد،
        وده بيحصل أحيانًا مع موديلات صغيرة بتعمل hallucination في اللغة."""
        if not answer:
            return answer
        cleaned = self._FOREIGN_SCRIPT_PATTERN.sub("", answer)
        # لو الفلترة شالت حروف فعلية في نص الكلمة (مش مجرد مسافة)، نضمن مفيش مسافات مضاعفة
        cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
        return cleaned or answer

    def _build_known_facts_text(self, current_crop: Optional[str], collected_slots: dict) -> str:
        if not current_crop and not collected_slots:
            return "لسه مفيش معلومات معروفة عن المستخدم — دي أول حاجة هتعرفها منه."

        parts = []
        if collected_slots.get("user_name"):
            parts.append(f"اسم المستخدم: {collected_slots['user_name']}")
        if current_crop:
            parts.append(f"المحصول: {current_crop}")
        label_map = {
            "governorate": "المحافظة",
            "location": "مكان الزراعة",
            "sun_exposure": "التعرض للشمس",
            "watering_frequency": "تكرار الري",
            "soil_type": "نوع التربة",
        }
        for key, label in label_map.items():
            if collected_slots.get(key):
                parts.append(f"{label}: {collected_slots[key]}")

        if not parts:
            return "لسه مفيش معلومات معروفة عن المستخدم — دي أول حاجة هتعرفها منه."

        return (
            "معلومات معروفة بالفعل عن المستخدم من كلامه قبل كده (متسألش عنها تاني): "
            + "، ".join(parts) + "."
        )

    async def answer_rag_question(
        self,
        project: Project,
        query: str,
        limit: int = 3,
        current_crop: Optional[str] = None,
        memory_state: Optional[dict] = None,
        preloaded_context: Optional[str] = None,
    ):
        """
        ⚠️ DEPRECATED — مش بتستخدم من ConversationService تاني (كانت بتعمل
        classify/prompt/generate/sanitize مكررة مع services/conversation/*).
        ConversationService دلوقتي بيستخدم search_vector_db_collection() و
        _is_context_relevant() مباشرة عن طريق VectorSource. الميثود دي متسيبة
        هنا للتوافق الخلفي بس، مفيش استدعاء ليها في الكود الحالي.
        """
        answer, context_text, chat_history, sources = None, None, None, []

        memory_state = memory_state or {}
        recent_turns = memory_state.get("recent_turns", [])
        is_first_message = memory_state.get("is_first_message", len(recent_turns) == 0)
        collected_slots = memory_state.get("collected_slots", {})

        # ── Classify + route (نستخدمها هنا برضه عشان نعرف الأسلوب how_to/informational) ──
        classifier = MessageClassifier()
        classification = classifier.classify(text=query, current_crop=current_crop)
        intent = self.router.detect_intent(query=query, message=classification)

        is_negation_or_ack = classification.intent_hint == "negation_or_continuation"
        is_agri = classification.message_type not in ("general_chat",) and not is_negation_or_ack

        # ── Retrieval — بس لو السؤال زراعي فعلي (مش رد قصير زي "لا") ──────────
        clean_context = "لا يوجد سياق زراعي محدد — أجب من خبرتك الزراعية العامة."

        if preloaded_context:
            # جايه من الـ knowledge store (KnowledgeController) — بنستخدمها كسياق
            # للموديل يصيغه، مش كإجابة نهائية جاهزة، عشان يفضل صوت واحد ثابت
            # وميكررش نفس الجملة الجاهزة كل مرة.
            clean_context = preloaded_context

        elif is_agri:
            retrieved_documents = await self.search_vector_db_collection(
                project=project,
                text=query,
                limit=limit,
                current_crop=current_crop,
            )

            NOISE = {"تنزيل الكتاب", "تحميل الكتاب", "download", "اضغط هنا", "-----"}
            context_blocks = []

            for doc in (retrieved_documents or []):
                text = doc.text or ""
                if len(text.strip()) < 60 or any(n in text for n in NOISE):
                    continue
                citation = build_source_citation(doc.metadata)
                context_blocks.append(f"[{citation}]\n{text}")
                sources.append({
                    "title": (doc.metadata or {}).get("title"),
                    "source_url": (doc.metadata or {}).get("source_url"),
                    "category": (doc.metadata or {}).get("category"),
                    "author": (doc.metadata or {}).get("author"),
                    "score": doc.score,
                    "vector_score": doc.vector_score,
                    "metadata_score": doc.metadata_score,
                })

            context_text = "\n---\n".join(context_blocks)

            # تأكد إن الـ context ذي صلة بالسؤال (ومطابق للمحصول الحالي لو معروف)
            if context_blocks and self._is_context_relevant(query, retrieved_documents or [], current_crop=current_crop):
                clean_context = context_text
            # لو الـ context مش ذي صلة أو بيتكلم عن محصول تاني — خليه يجاوب من خبرته
            # العامة بدل ما يستخدم معلومة غلط عن محصول مختلف.

        # ── System prompt: نمرر حالة المحادثة كمتغيرات فعلية بدل placeholders فاضية ──
        greeting_rule = (
            "دي أول رسالة في المحادثة — رحب بالمستخدم بجملة ودّية قصيرة مرة واحدة دلوقتي."
            if is_first_message else
            "المحادثة مستمرة بالفعل — ممنوع تقول 'أهلاً بيك' أو أي ترحيب تاني، ادخل في الموضوع على طول."
        )
        known_facts = self._build_known_facts_text(current_crop, collected_slots)

        style_instruction = ""
        if intent.style == "how_to":
            style_instruction = "المستخدم عايز خطوات عملية (إزاي يعمل الحاجة) — جاوب بخطوات مباشرة، متشرحش عن المحصول نفسه الأول."
        elif intent.style == "informational":
            style_instruction = "المستخدم عايز يعرف معلومة عامة عن المحصول — نبذة مختصرة تكفي."

        system_prompt_template = self.template_parser.get("rag", "system_prompt")
        if hasattr(system_prompt_template, "safe_substitute"):
            system_content = system_prompt_template.safe_substitute(
                greeting_rule=greeting_rule,
                known_facts=known_facts,
            )
        else:
            system_content = str(system_prompt_template) if system_prompt_template else "أنت AgriSense — مهندس زراعي مصري خبير."

        # ── Build chat history ────────────────────────────────────────────────
        chat_history = [{"role": "system", "content": system_content}]
        chat_history.extend(
            recent_turns[-4:] if len(recent_turns) > 4 else recent_turns
        )

        user_message_parts = [f"المعلومات المتاحة:\n{clean_context}"]
        if style_instruction:
            user_message_parts.append(style_instruction)
        user_message_parts.append(f"---\nرسالة المستخدم: {query}\n\nرد بشكل طبيعي كخبير زراعي مصري.")

        chat_history.append({
            "role": "user",
            "content": "\n\n".join(user_message_parts),
        })

        # ── Generate ──────────────────────────────────────────────────────────
        answer = self.generation_client.generate_text(chat_history=chat_history)

        if answer:
            answer = (
                answer
                .replace("المستند رقم", "")
                .replace("بناءً على البيانات", "")
                .replace("بناءً على المستندات", "")
                .replace("وفقاً للسياق", "")
                .replace("بالطبع،", "")
                .strip()
            )
            answer = self._sanitize_answer(answer)

        return answer, context_text, chat_history, sources
    