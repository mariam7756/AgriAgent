from typing import Dict, List


class AgricultureOntology:
    def __init__(self):
        self.ontology = {
            "crop": ["olive", "wheat", "corn", "tomato", "potato"],
            "topic": ["cultivation", "irrigation", "fertilization", "pruning", "harvest"],
            "disease": ["leaf_spot", "powdery_mildew", "root_rot"],
            "pest": ["aphids", "whitefly", "fruit_fly"],
            "knowledge_source_type": ["directory", "knowledge_source"],
        }

    def to_dict(self) -> Dict:
        return self.ontology


class FAQDataset:
    def __init__(self):
        self.faq: List[Dict] = [
            {
                "question": "كيف أزرع الزيتون؟",
                "intent": "cultivation",
                "crop": "olive",
                "answer_template": "ابدأ باختيار تربة جيدة الصرف ومكان مشمس.",
            },
            {
                "question": "ورق الزيتون عندي أصفر",
                "intent": "diagnosis",
                "crop": "olive",
                "answer_template": "راجع انتظام الري وافحص أعراض نقص العناصر أو الإصابة المرضية.",
            },
        ]

    def list_items(self) -> List[Dict]:
        return self.faq
