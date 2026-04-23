import asyncio
import time
import aiohttp
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class RateLimiter:
    """Rate limiter để tránh bị API throttling"""
    max_requests_per_minute: int = 60
    current_requests: int = 0
    last_reset: float = None
    
    def __post_init__(self):
        self.last_reset = time.time()
    
    async def acquire(self):
        """Chờ nếu đã vượt quá rate limit"""
        now = time.time()
        if now - self.last_reset >= 60:
            self.current_requests = 0
            self.last_reset = now
        
        if self.current_requests >= self.max_requests_per_minute:
            wait_time = 60 - (now - self.last_reset)
            logger.warning(f"Rate limit reached, waiting {wait_time:.2f}s")
            await asyncio.sleep(wait_time)
            self.current_requests = 0
            self.last_reset = time.time()
        
        self.current_requests += 1

class MockAgent:
    """Mock Agent - thay thế bằng agent thật của bạn"""
    
    def __init__(self, name: str = "MockAgent"):
        self.name = name
        self.rate_limiter = RateLimiter()
    
    async def query(self, question: str, context: Optional[List[str]] = None) -> Dict[str, Any]:
        """Gọi agent để trả lời câu hỏi"""
        await self.rate_limiter.acquire()
        await asyncio.sleep(0.1)  # Simulate processing time
        
        # Mock response - replace with actual agent call
        answer = f"This is a mock response to: {question[:50]}..."
        
        return {
            "answer": answer,
            "context_used": context or [],
            "model": self.name,
            "timestamp": datetime.now().isoformat()
        }

class MockEvaluator:
    """Mock Evaluator - thay thế bằng RAGAS thật"""
    
    async def score(self, test_case: Dict, response: Dict) -> Dict[str, float]:
        """Đánh giá chất lượng response"""
        await asyncio.sleep(0.05)  # Simulate evaluation
        
        # Simple mock scoring
        expected = test_case.get("expected_answer", "")
        actual = response.get("answer", "")
        
        # Very simple similarity check
        expected_words = set(expected.lower().split())
        actual_words = set(actual.lower().split())
        
        if not expected_words:
            similarity = 0.5
        else:
            similarity = len(expected_words & actual_words) / len(expected_words)
        
        return {
            "answer_relevancy": min(1.0, similarity * 1.2),
            "faithfulness": min(1.0, similarity),
            "context_recall": 0.8 if test_case.get("expected_retrieval_ids") else 0.5,
            "context_precision": 0.7,
            "answer_similarity": similarity
        }

class MultiJudge:
    """Multi-Judge consensus evaluator"""
    
    def __init__(self, models: List[str] = None):
        self.models = models or ["gpt-4o-mini", "claude-3-haiku", "llama3-70b"]
        self.rate_limiter = RateLimiter()
    
    async def evaluate_single_judge(self, model: str, question: str, 
                                    expected: str, actual: str) -> float:
        """Evaluate with single judge model"""
        await self.rate_limiter.acquire()
        await asyncio.sleep(0.1)  # Simulate API call
        
        # Mock scoring - replace with actual LLM judge
        expected_words = set(expected.lower().split())
        actual_words = set(actual.lower().split())
        
        if not expected_words:
            return 5.0
        
        similarity = len(expected_words & actual_words) / len(expected_words)
        return similarity * 10  # Score from 0-10
    
    async def evaluate_multi_judge(self, question: str, actual_answer: str, 
                                   expected_answer: str) -> Dict[str, Any]:
        """Run multi-judge evaluation"""
        tasks = []
        for model in self.models:
            task = self.evaluate_single_judge(model, question, expected_answer, actual_answer)
            tasks.append(task)
        
        scores = await asyncio.gather(*tasks)
        
        # Calculate consensus
        avg_score = sum(scores) / len(scores)
        std_dev = (sum((s - avg_score) ** 2 for s in scores) / len(scores)) ** 0.5
        agreement = 1.0 - min(1.0, std_dev / 10.0)
        
        return {
            "final_score": avg_score,
            "agreement_rate": agreement,
            "individual_scores": dict(zip(self.models, scores)),
            "std_dev": std_dev,
            "conflicts": std_dev > 2.0  # Large disagreement
        }

class BenchmarkRunner:
    """Async Benchmark Runner với đầy đủ tính năng"""
    
    def __init__(self, agent=None, evaluator=None, judge=None):
        self.agent = agent or MockAgent()
        self.evaluator = evaluator or MockEvaluator()
        self.judge = judge or MultiJudge()
        self.rate_limiter = RateLimiter()
        self.results = []
        self.cost_tracker = CostTracker()
    
    async def run_single_test(self, test_case: Dict, test_id: int) -> Dict:
        """Chạy benchmark cho 1 test case"""
        start_time = time.perf_counter()
        
        try:
            # 1. Gọi Agent
            await self.rate_limiter.acquire()
            response = await self.agent.query(test_case["question"])
            latency = time.perf_counter() - start_time
            
            # Track cost
            self.cost_tracker.add_request("agent", latency)
            
            # 2. Chạy Retrieval Evaluation (nếu có context)
            retrieval_scores = {}
            if test_case.get("expected_retrieval_ids"):
                from engine.retrieval_evaluator import RetrievalEvaluator
                ret_eval = RetrievalEvaluator()
                retrieved_ids = response.get("context_used", [])
                retrieval_scores = ret_eval.evaluate_retrieval(
                    retrieved_ids, 
                    test_case["expected_retrieval_ids"]
                )
            
            # 3. Chạy RAGAS Evaluation
            ragas_scores = await self.evaluator.score(test_case, response)
            
            # 4. Chạy Multi-Judge
            judge_result = await self.judge.evaluate_multi_judge(
                test_case["question"],
                response["answer"],
                test_case["expected_answer"]
            )
            
            # 5. Determine overall status
            score = judge_result["final_score"]
            if score >= 7.0:
                status = "excellent"
            elif score >= 5.0:
                status = "pass"
            elif score >= 3.0:
                status = "needs_improvement"
            else:
                status = "fail"
            
            result = {
                "test_id": test_id,
                "case_id": test_case.get("id", f"case_{test_id}"),
                "question": test_case["question"],
                "expected_answer": test_case["expected_answer"],
                "actual_answer": response["answer"],
                "latency": latency,
                "retrieval_metrics": retrieval_scores,
                "ragas_metrics": ragas_scores,
                "judge_metrics": judge_result,
                "overall_score": score,
                "status": status,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in test {test_id}: {e}")
            result = {
                "test_id": test_id,
                "case_id": test_case.get("id", f"case_{test_id}"),
                "question": test_case.get("question", ""),
                "error": str(e),
                "status": "error",
                "timestamp": datetime.now().isoformat()
            }
        
        return result
    
    async def run_all(self, dataset: List[Dict], batch_size: int = 5, 
                     max_concurrent: int = 3) -> Dict[str, Any]:
        """
        Chạy benchmark với tất cả test cases
        
        Args:
            dataset: List of test cases
            batch_size: Số lượng cases trong 1 batch
            max_concurrent: Số lượng concurrent requests tối đa
        """
        logger.info(f"Starting benchmark with {len(dataset)} test cases")
        start_time = time.perf_counter()
        
        all_results = []
        
        # Process in batches
        for i in range(0, len(dataset), batch_size):
            batch = dataset[i:i + batch_size]
            
            # Run batch with limited concurrency
            semaphore = asyncio.Semaphore(max_concurrent)
            
            async def run_with_limit(test_case, idx):
                async with semaphore:
                    return await self.run_single_test(test_case, i + idx)
            
            tasks = [run_with_limit(case, idx) for idx, case in enumerate(batch)]
            batch_results = await asyncio.gather(*tasks)
            all_results.extend(batch_results)
            
            logger.info(f"Completed batch {i//batch_size + 1}/{(len(dataset)-1)//batch_size + 1}")
        
        total_time = time.perf_counter() - start_time
        
        # Calculate summary statistics
        summary = self._calculate_summary(all_results, total_time)
        
        self.results = all_results
        
        return {
            "summary": summary,
            "detailed_results": all_results,
            "total_time": total_time,
            "total_cases": len(dataset),
            "cost_analysis": self.cost_tracker.get_summary()
        }
    
    def _calculate_summary(self, results: List[Dict], total_time: float) -> Dict[str, Any]:
        """Calculate summary statistics"""
        valid_results = [r for r in results if "error" not in r]
        
        if not valid_results:
            return {"error": "No valid results"}
        
        # Status distribution
        status_counts = {}
        for r in results:
            status = r.get("status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
        
        # Average scores
        avg_score = sum(r.get("overall_score", 0) for r in valid_results) / len(valid_results)
        avg_latency = sum(r.get("latency", 0) for r in valid_results) / len(valid_results)
        
        # Retrieval metrics (if available)
        retrieval_metrics = {}
        for metric in ["hit_rate@1", "hit_rate@3", "hit_rate@5", "mrr"]:
            values = [r["retrieval_metrics"].get(metric, 0) 
                     for r in valid_results if "retrieval_metrics" in r]
            if values:
                retrieval_metrics[metric] = sum(values) / len(values)
        
        # RAGAS metrics
        ragas_metrics = {}
        for metric in ["answer_relevancy", "faithfulness", "context_recall", "answer_similarity"]:
            values = [r["ragas_metrics"].get(metric, 0) 
                     for r in valid_results if "ragas_metrics" in r]
            if values:
                ragas_metrics[metric] = sum(values) / len(values)
        
        return {
            "total_tests": len(results),
            "valid_tests": len(valid_results),
            "error_tests": len(results) - len(valid_results),
            "status_distribution": status_counts,
            "average_overall_score": avg_score,
            "average_latency_seconds": avg_latency,
            "total_time_seconds": total_time,
            "throughput_tps": len(valid_results) / total_time if total_time > 0 else 0,
            "retrieval_metrics": retrieval_metrics,
            "ragas_metrics": ragas_metrics,
            "pass_rate": status_counts.get("pass", 0) / len(valid_results) if valid_results else 0,
            "excellent_rate": status_counts.get("excellent", 0) / len(valid_results) if valid_results else 0
        }

class CostTracker:
    """Theo dõi chi phí API calls"""
    
    def __init__(self):
        self.requests = []
        self.cost_per_request = {
            "agent": 0.001,  # $0.001 per request
            "judge_gpt4": 0.002,
            "judge_claude": 0.0015,
            "judge_llama": 0.0005,
            "evaluator": 0.0005
        }
    
    def add_request(self, request_type: str, duration: float, tokens: int = 1000):
        """Thêm 1 request vào tracker"""
        cost = self.cost_per_request.get(request_type, 0) * (tokens / 1000)
        self.requests.append({
            "type": request_type,
            "duration": duration,
            "tokens": tokens,
            "cost": cost,
            "timestamp": datetime.now().isoformat()
        })
    
    def get_summary(self) -> Dict[str, Any]:
        """Lấy summary chi phí"""
        if not self.requests:
            return {"total_cost": 0, "total_requests": 0}
        
        total_cost = sum(r["cost"] for r in self.requests)
        total_tokens = sum(r["tokens"] for r in self.requests)
        avg_duration = sum(r["duration"] for r in self.requests) / len(self.requests)
        
        # Cost by type
        cost_by_type = {}
        for r in self.requests:
            cost_by_type[r["type"]] = cost_by_type.get(r["type"], 0) + r["cost"]
        
        return {
            "total_cost_usd": total_cost,
            "total_cost_vnd": total_cost * 25000,  # Approx conversion
            "total_requests": len(self.requests),
            "total_tokens": total_tokens,
            "average_duration_seconds": avg_duration,
            "cost_breakdown": cost_by_type,
            "estimated_cost_per_1000_tests": (total_cost / len(self.requests)) * 1000 if self.requests else 0
        }