"""
RAG Evaluator - Đánh giá chất lượng generation
"""

from typing import List, Dict, Any, Optional
import numpy as np
from dataclasses import dataclass
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class RAGScore:
    """Điểm số cho RAG generation"""
    faithfulness: float  # 0-1: Có hallucination không
    answer_relevance: float  # 0-1: Trả lời đúng câu hỏi không
    context_relevance: float  # 0-1: Context có liên quan không
    overall: float  # Điểm tổng hợp


class RAGEvaluator:
    """Đánh giá chất lượng generation của RAG pipeline"""
    
    def __init__(self, use_llm_judge: bool = True, llm_model: str = "gpt-4o-mini"):
        self.use_llm_judge = use_llm_judge
        self.llm_model = llm_model
        
    def calculate_faithfulness(self, 
                               answer: str, 
                               contexts: List[str]) -> float:
        """
        Tính faithfulness: Câu trả lời có dựa trên context không
        (Tránh hallucination)
        
        Phương pháp đơn giản: Kiểm tra các claim trong answer có trong context không
        """
        if not answer or not contexts:
            return 0.0
        
        # Đơn giản hóa: Kiểm tra overlap giữa answer và contexts
        combined_context = " ".join(contexts).lower()
        answer_lower = answer.lower()
        
        # Tách thành các câu hoặc claims (đơn giản hóa)
        # Trong thực tế nên dùng LLM để đánh giá
        sentences = answer_lower.split('.')
        
        supported_claims = 0
        total_claims = len([s for s in sentences if len(s.strip()) > 10])
        
        if total_claims == 0:
            return 0.5
        
        for sentence in sentences:
            if len(sentence.strip()) < 10:
                continue
            # Kiểm tra sentence có trong context không
            if sentence.strip() in combined_context:
                supported_claims += 1
            else:
                # Kiểm tra từ khóa chính
                words = set(sentence.split())
                context_words = set(combined_context.split())
                overlap = len(words & context_words) / len(words) if words else 0
                if overlap > 0.5:
                    supported_claims += 0.5
        
        return supported_claims / total_claims
    
    def calculate_answer_relevance(self, 
                                   question: str, 
                                   answer: str) -> float:
        """
        Tính answer relevance: Câu trả lời có liên quan đến câu hỏi không
        """
        if not question or not answer:
            return 0.0
        
        # Đơn giản hóa: Kiểm tra overlap giữa question và answer
        q_words = set(question.lower().split())
        a_words = set(answer.lower().split())
        
        if not q_words:
            return 0.5
        
        overlap = len(q_words & a_words) / len(q_words)
        
        # Bonus: Kiểm tra answer có trực tiếp trả lời không
        question_lower = question.lower()
        answer_lower = answer.lower()
        
        if "không" in question_lower and ("không" in answer_lower or "có" in answer_lower):
            overlap += 0.2
        if "bao nhiêu" in question_lower and any(c.isdigit() for c in answer):
            overlap += 0.2
        
        return min(1.0, overlap)
    
    def calculate_context_relevance(self, 
                                    question: str, 
                                    contexts: List[str]) -> float:
        """
        Tính context relevance: Context có liên quan đến câu hỏi không
        """
        if not question or not contexts:
            return 0.0
        
        q_words = set(question.lower().split())
        
        if not q_words:
            return 0.5
        
        total_relevance = 0.0
        for context in contexts:
            context_lower = context.lower()
            context_words = set(context_lower.split())
            overlap = len(q_words & context_words) / len(q_words)
            total_relevance += overlap
        
        return total_relevance / len(contexts)
    
    async def evaluate_with_llm(self,
                                question: str,
                                answer: str,
                                expected_answer: str,
                                contexts: List[str]) -> Dict[str, float]:
        """
        Đánh giá sử dụng LLM judge (chính xác hơn)
        """
        # Placeholder - implement với actual LLM calls
        # Trong thực tế, gọi OpenAI/Anthropic API
        
        # Tạm thời dùng heuristic
        return {
            "faithfulness": self.calculate_faithfulness(answer, contexts),
            "answer_relevance": self.calculate_answer_relevance(question, answer),
            "context_relevance": self.calculate_context_relevance(question, contexts)
        }
    
    async def evaluate_single(self,
                             question: str,
                             answer: str,
                             expected_answer: str,
                             contexts: List[str]) -> RAGScore:
        """
        Đánh giá toàn diện cho 1 query
        """
        if self.use_llm_judge:
            scores = await self.evaluate_with_llm(question, answer, expected_answer, contexts)
        else:
            scores = {
                "faithfulness": self.calculate_faithfulness(answer, contexts),
                "answer_relevance": self.calculate_answer_relevance(question, answer),
                "context_relevance": self.calculate_context_relevance(question, contexts)
            }
        
        # Tính overall score (weighted average)
        overall = (
            scores["faithfulness"] * 0.4 +
            scores["answer_relevance"] * 0.4 +
            scores["context_relevance"] * 0.2
        )
        
        return RAGScore(
            faithfulness=scores["faithfulness"],
            answer_relevance=scores["answer_relevance"],
            context_relevance=scores["context_relevance"],
            overall=overall
        )
    
    async def evaluate_batch(self,
                            results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Đánh giá batch các kết quả RAG
        """
        all_scores = []
        
        for item in results:
            score = await self.evaluate_single(
                question=item.get("question", ""),
                answer=item.get("answer", ""),
                expected_answer=item.get("expected_answer", ""),
                contexts=item.get("contexts", [])
            )
            all_scores.append(score)
        
        # Aggregate
        if not all_scores:
            return {}
        
        return {
            "avg_faithfulness": np.mean([s.faithfulness for s in all_scores]),
            "avg_answer_relevance": np.mean([s.answer_relevance for s in all_scores]),
            "avg_context_relevance": np.mean([s.context_relevance for s in all_scores]),
            "avg_overall": np.mean([s.overall for s in all_scores]),
            "std_faithfulness": np.std([s.faithfulness for s in all_scores]),
            "std_overall": np.std([s.overall for s in all_scores]),
            "detailed_scores": all_scores
        }