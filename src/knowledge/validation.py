from typing import Dict, List


class ValidationLayer:
    def validate_grounding(self, answer: str, supporting_facts: List[str]) -> Dict:
        answer = (answer or "").strip()
        if not answer:
            return {"is_valid": False, "reason": "empty_answer"}
        if not supporting_facts:
            return {"is_valid": False, "reason": "missing_facts"}

        matched = sum(1 for fact in supporting_facts if fact and fact in answer)
        return {
            "is_valid": matched > 0,
            "reason": "ok" if matched > 0 else "answer_not_grounded",
            "matched_facts": matched,
            "total_facts": len(supporting_facts),
        }


class FeedbackLoopStore:
    def __init__(self):
        self.records: List[Dict] = []

    def append(self, question: str, answer: str, feedback: str = "pending") -> Dict:
        item = {
            "question": question,
            "answer": answer,
            "feedback": feedback,
        }
        self.records.append(item)
        return item

    def list_records(self) -> List[Dict]:
        return self.records
