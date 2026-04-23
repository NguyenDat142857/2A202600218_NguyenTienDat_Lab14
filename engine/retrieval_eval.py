"""
Retrieval Evaluator - Tính Hit Rate & MRR cho Vector DB
"""

from typing import List, Dict, Any
import numpy as np
from collections import defaultdict
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RetrievalEvaluator:
    """Đánh giá chất lượng retrieval stage của RAG pipeline"""
    
    def __init__(self, k_values: List[int] = [1, 3, 5, 10]):
        """
        Khởi tạo RetrievalEvaluator
        
        Args:
            k_values: Các giá trị k để tính hit rate và recall
        """
        self.k_values = k_values
        
    def calculate_hit_rate(self, expected_ids: List[str], retrieved_ids: List[str], top_k: int = 3) -> float:
        """
        Tính Hit Rate @k: Có ít nhất 1 document đúng trong top-k hay không
        
        Args:
            expected_ids: List các document ID mong đợi (ground truth)
            retrieved_ids: List các document ID retrieved bởi hệ thống
            top_k: Số lượng top documents xét đến
            
        Returns:
            float: 1.0 nếu có hit, 0.0 nếu không
        """
        if not expected_ids or not retrieved_ids:
            return 0.0
            
        top_retrieved = retrieved_ids[:top_k]
        hit = any(doc_id in top_retrieved for doc_id in expected_ids)
        return 1.0 if hit else 0.0

    def calculate_mrr(self, expected_ids: List[str], retrieved_ids: List[str]) -> float:
        """
        Tính Mean Reciprocal Rank (MRR)
        MRR = 1 / position của document đúng đầu tiên (1-indexed)
        
        Args:
            expected_ids: List các document ID mong đợi
            retrieved_ids: List các document ID retrieved bởi hệ thống
            
        Returns:
            float: MRR value (0-1)
        """
        if not expected_ids or not retrieved_ids:
            return 0.0
            
        for i, doc_id in enumerate(retrieved_ids, start=1):
            if doc_id in expected_ids:
                return 1.0 / i
        return 0.0
    
    def calculate_recall(self, expected_ids: List[str], retrieved_ids: List[str], top_k: int = 3) -> float:
        """
        Tính Recall @k: Tỷ lệ document đúng được retrieve trong top-k
        
        Args:
            expected_ids: List các document ID mong đợi
            retrieved_ids: List các document ID retrieved
            top_k: Số lượng top documents xét đến
            
        Returns:
            float: Recall value (0-1)
        """
        if not expected_ids:
            return 0.0
            
        top_retrieved_set = set(retrieved_ids[:top_k])
        expected_set = set(expected_ids)
        
        if not expected_set:
            return 0.0
            
        hits = len(top_retrieved_set & expected_set)
        return hits / len(expected_set)
    
    def calculate_precision(self, expected_ids: List[str], retrieved_ids: List[str], top_k: int = 3) -> float:
        """
        Tính Precision @k: Tỷ lệ documents retrieved là đúng
        
        Args:
            expected_ids: List các document ID mong đợi
            retrieved_ids: List các document ID retrieved
            top_k: Số lượng top documents xét đến
            
        Returns:
            float: Precision value (0-1)
        """
        if top_k == 0 or not retrieved_ids:
            return 0.0
            
        top_retrieved = retrieved_ids[:top_k]
        if not top_retrieved:
            return 0.0
            
        expected_set = set(expected_ids)
        correct = sum(1 for doc_id in top_retrieved if doc_id in expected_set)
        return correct / len(top_retrieved)
    
    def calculate_ndcg(self, expected_ids: List[str], retrieved_ids: List[str], top_k: int = 3) -> float:
        """
        Tính Normalized Discounted Cumulative Gain @k
        
        Args:
            expected_ids: List các document ID mong đợi
            retrieved_ids: List các document ID retrieved
            top_k: Số lượng top documents xét đến
            
        Returns:
            float: nDCG value (0-1)
        """
        if not expected_ids or not retrieved_ids:
            return 0.0
            
        # Tạo relevance scores (1 cho expected, 0 cho others)
        expected_set = set(expected_ids)
        relevance = [1.0 if doc_id in expected_set else 0.0 for doc_id in retrieved_ids[:top_k]]
        
        if not relevance or sum(relevance) == 0:
            return 0.0
        
        # Calculate DCG
        dcg = 0.0
        for i, rel in enumerate(relevance):
            dcg += rel / np.log2(i + 2)  # i+2 vì log2(2)=1 cho vị trí đầu
        
        # Calculate IDCG (ideal DCG)
        ideal_relevance = sorted(relevance, reverse=True)
        idcg = 0.0
        for i, rel in enumerate(ideal_relevance):
            idcg += rel / np.log2(i + 2)
        
        if idcg == 0:
            return 0.0
            
        return dcg / idcg
    
    def evaluate_single_query(self, 
                              retrieved_ids: List[str], 
                              expected_ids: List[str],
                              query_id: str = None) -> Dict[str, Any]:
        """
        Đánh giá retrieval cho 1 query duy nhất
        
        Args:
            retrieved_ids: List các document ID retrieved
            expected_ids: List các document ID mong đợi
            query_id: ID của query (optional)
            
        Returns:
            Dict với các metrics chi tiết
        """
        results = {
            "query_id": query_id,
            "expected_count": len(expected_ids),
            "retrieved_count": len(retrieved_ids),
            "mrr": self.calculate_mrr(expected_ids, retrieved_ids),
            "first_correct_position": None,
            "missing_documents": []
        }
        
        # Tìm vị trí đầu tiên của document đúng
        for i, doc_id in enumerate(retrieved_ids, start=1):
            if doc_id in expected_ids:
                results["first_correct_position"] = i
                break
        
        # Tìm documents bị missing
        expected_set = set(expected_ids)
        retrieved_set = set(retrieved_ids)
        results["missing_documents"] = list(expected_set - retrieved_set)
        
        # Tính metrics cho các k values
        for k in self.k_values:
            results[f"hit_rate@{k}"] = self.calculate_hit_rate(expected_ids, retrieved_ids, k)
            results[f"recall@{k}"] = self.calculate_recall(expected_ids, retrieved_ids, k)
            results[f"precision@{k}"] = self.calculate_precision(expected_ids, retrieved_ids, k)
            results[f"ndcg@{k}"] = self.calculate_ndcg(expected_ids, retrieved_ids, k)
        
        return results
    
    async def evaluate_batch(self, 
                            dataset: List[Dict], 
                            retrieval_function=None,
                            verbose: bool = True) -> Dict[str, Any]:
        """
        Chạy evaluation cho toàn bộ dataset
        
        Args:
            dataset: List các test cases, mỗi case có 'expected_retrieval_ids' và 'question'
            retrieval_function: Async function để retrieve documents (optional)
            verbose: In progress logs
            
        Returns:
            Dict với overall metrics và detailed analysis
        """
        if not dataset:
            logger.warning("Dataset is empty!")
            return {
                "avg_hit_rate": 0.0,
                "avg_mrr": 0.0,
                "total_queries": 0,
                "detailed_results": []
            }
        
        all_results = []
        
        for idx, case in enumerate(dataset):
            if verbose and idx % 10 == 0:
                logger.info(f"Processing query {idx + 1}/{len(dataset)}")
            
            # Get expected IDs
            expected_ids = case.get("expected_retrieval_ids", [])
            
            # If retrieval function provided, use it to get retrieved IDs
            retrieved_ids = case.get("retrieved_ids", [])
            if retrieval_function and not retrieved_ids:
                question = case.get("question", "")
                if question:
                    retrieved_ids = await retrieval_function(question)
            
            # Evaluate
            result = self.evaluate_single_query(
                retrieved_ids=retrieved_ids,
                expected_ids=expected_ids,
                query_id=case.get("id", f"query_{idx}")
            )
            
            # Add metadata for failure analysis
            result["metadata"] = case.get("metadata", {})
            result["question"] = case.get("question", "")
            result["expected_answer"] = case.get("expected_answer", "")
            
            all_results.append(result)
        
        # Aggregate overall metrics
        overall_metrics = self._aggregate_metrics(all_results)
        
        # Analyze failures
        failure_analysis = self._analyze_failures(all_results)
        
        return {
            "overall_metrics": overall_metrics,
            "failure_analysis": failure_analysis,
            "detailed_results": all_results,
            "total_queries": len(dataset),
            "total_expected_docs": sum(r["expected_count"] for r in all_results),
            "total_retrieved_docs": sum(r["retrieved_count"] for r in all_results)
        }
    
    def _aggregate_metrics(self, results: List[Dict]) -> Dict[str, Any]:
        """Tổng hợp metrics từ tất cả queries"""
        if not results:
            return {}
        
        aggregated = {}
        
        # Lấy tất cả metric keys từ result đầu tiên
        metric_keys = [k for k in results[0].keys() 
                      if not k in ["query_id", "metadata", "question", "expected_answer", 
                                   "missing_documents", "first_correct_position"]]
        
        for key in metric_keys:
            values = [r[key] for r in results if key in r]
            if values:
                aggregated[key] = np.mean(values)
                aggregated[f"{key}_std"] = np.std(values)
                aggregated[f"{key}_min"] = np.min(values)
                aggregated[f"{key}_max"] = np.max(values)
        
        # Thêm statistics đặc biệt
        first_positions = [r["first_correct_position"] for r in results if r["first_correct_position"] is not None]
        if first_positions:
            aggregated["avg_first_correct_position"] = np.mean(first_positions)
            aggregated["median_first_correct_position"] = np.median(first_positions)
        
        # Hit rate tổng thể (có ít nhất 1 hit cho bất kỳ k nào)
        aggregated["overall_hit_rate"] = sum(1 for r in results if r.get("hit_rate@1", 0) > 0) / len(results)
        
        return aggregated
    
    def _analyze_failures(self, results: List[Dict]) -> Dict[str, Any]:
        """
        Phân tích chi tiết các retrieval failures
        
        Returns:
            Dict với phân tích failure patterns
        """
        failures = {
            "no_hits_at_1": [],      # Không có hit trong top-1
            "no_hits_at_3": [],      # Không có hit trong top-3
            "no_hits_at_5": [],      # Không có hit trong top-5
            "low_mrr": [],            # MRR < 0.5
            "missing_docs_analysis": defaultdict(int),  # Documents thường bị miss
            "failure_by_category": defaultdict(int),     # Failure theo category
            "failure_by_difficulty": defaultdict(int)    # Failure theo difficulty
        }
        
        for idx, result in enumerate(results):
            # Check hits at different k
            if result.get("hit_rate@1", 0) == 0:
                failures["no_hits_at_1"].append(idx)
            if result.get("hit_rate@3", 0) == 0:
                failures["no_hits_at_3"].append(idx)
            if result.get("hit_rate@5", 0) == 0:
                failures["no_hits_at_5"].append(idx)
            
            # Check MRR
            if result.get("mrr", 0) < 0.5:
                failures["low_mrr"].append(idx)
            
            # Analyze missing documents
            for doc_id in result.get("missing_documents", []):
                failures["missing_docs_analysis"][doc_id] += 1
            
            # Analyze by metadata
            metadata = result.get("metadata", {})
            category = metadata.get("category", "unknown")
            difficulty = metadata.get("difficulty", "unknown")
            
            if result.get("hit_rate@3", 0) == 0:
                failures["failure_by_category"][category] += 1
                failures["failure_by_difficulty"][difficulty] += 1
        
        # Convert defaultdict to dict
        failures["missing_docs_analysis"] = dict(failures["missing_docs_analysis"])
        failures["failure_by_category"] = dict(failures["failure_by_category"])
        failures["failure_by_difficulty"] = dict(failures["failure_by_difficulty"])
        
        # Tính tỷ lệ failure
        total = len(results)
        failures["failure_rates"] = {
            "no_hits_at_1_rate": len(failures["no_hits_at_1"]) / total if total > 0 else 0,
            "no_hits_at_3_rate": len(failures["no_hits_at_3"]) / total if total > 0 else 0,
            "no_hits_at_5_rate": len(failures["no_hits_at_5"]) / total if total > 0 else 0,
            "low_mrr_rate": len(failures["low_mrr"]) / total if total > 0 else 0
        }
        
        # Top missing documents
        missing_sorted = sorted(
            failures["missing_docs_analysis"].items(), 
            key=lambda x: x[1], 
            reverse=True
        )[:10]  # Top 10 documents bị miss nhiều nhất
        failures["top_missing_documents"] = missing_sorted
        
        return failures


# ========================= HELPER FUNCTIONS =========================

def print_retrieval_report(evaluation_result: Dict[str, Any]) -> None:
    """
    In báo cáo retrieval evaluation đẹp mắt
    """
    print("\n" + "="*60)
    print("📊 RETRIEVAL EVALUATION REPORT")
    print("="*60)
    
    overall = evaluation_result.get("overall_metrics", {})
    
    print(f"\n📈 Overall Statistics:")
    print(f"   Total queries: {evaluation_result.get('total_queries', 0)}")
    print(f"   Total expected docs: {evaluation_result.get('total_expected_docs', 0)}")
    print(f"   Total retrieved docs: {evaluation_result.get('total_retrieved_docs', 0)}")
    
    print(f"\n🎯 Key Metrics:")
    print(f"   MRR: {overall.get('mrr', 0):.3f} ± {overall.get('mrr_std', 0):.3f}")
    print(f"   Hit Rate@1: {overall.get('hit_rate@1', 0):.3f} ± {overall.get('hit_rate@1_std', 0):.3f}")
    print(f"   Hit Rate@3: {overall.get('hit_rate@3', 0):.3f} ± {overall.get('hit_rate@3_std', 0):.3f}")
    print(f"   Hit Rate@5: {overall.get('hit_rate@5', 0):.3f} ± {overall.get('hit_rate@5_std', 0):.3f}")
    print(f"   Recall@3: {overall.get('recall@3', 0):.3f} ± {overall.get('recall@3_std', 0):.3f}")
    print(f"   Precision@3: {overall.get('precision@3', 0):.3f} ± {overall.get('precision@3_std', 0):.3f}")
    print(f"   nDCG@3: {overall.get('ndcg@3', 0):.3f} ± {overall.get('ndcg@3_std', 0):.3f}")
    
    failure = evaluation_result.get("failure_analysis", {})
    failure_rates = failure.get("failure_rates", {})
    
    print(f"\n⚠️ Failure Analysis:")
    print(f"   No hit@1 rate: {failure_rates.get('no_hits_at_1_rate', 0):.2%}")
    print(f"   No hit@3 rate: {failure_rates.get('no_hits_at_3_rate', 0):.2%}")
    print(f"   Low MRR rate: {failure_rates.get('low_mrr_rate', 0):.2%}")
    
    print(f"\n📚 Top Missing Documents:")
    for doc_id, count in failure.get("top_missing_documents", [])[:5]:
        print(f"   {doc_id}: missing in {count} queries")
    
    print("\n" + "="*60)