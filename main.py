"""
Main Entry Point - AI Evaluation Factory (Expert Complete Version)
Tích hợp Retrieval Evaluation, Multi-Judge Consensus, Regression Gate
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from engine.async_runner import BenchmarkRunner, MockAgent, MockEvaluator, CostTracker
from engine.retrieval_evaluator import RetrievalEvaluator
from engine.llm_judge import LLMJudge, get_llm_judge

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ExpertEvaluator:
    """Expert Evaluator tích hợp Retrieval + Generation metrics"""
    
    def __init__(self):
        self.retrieval_evaluator = RetrievalEvaluator()
    
    async def score(self, test_case: Dict, response: Dict) -> Dict[str, Any]:
        """Đánh giá toàn diện response bao gồm retrieval metrics"""
        # Retrieval metrics
        retrieval_metrics = {}
        if test_case.get("expected_retrieval_ids"):
            retrieved_ids = response.get("context_used", [])
            retrieval_metrics = self.retrieval_evaluator.evaluate_retrieval(
                retrieved_ids, 
                test_case["expected_retrieval_ids"]
            )
        
        # Generation quality (simplified - có thể dùng RAGAS thật)
        expected = test_case.get("expected_answer", "")
        actual = response.get("answer", "")
        
        # Simple similarity
        expected_words = set(expected.lower().split())
        actual_words = set(actual.lower().split())
        
        if expected_words:
            similarity = len(expected_words & actual_words) / len(expected_words)
        else:
            similarity = 0.5
        
        return {
            "retrieval": retrieval_metrics,
            "generation": {
                "answer_similarity": similarity,
                "answer_relevancy": min(1.0, similarity * 1.2),
                "faithfulness": min(1.0, similarity * 0.9)
            }
        }

class MainAgent:
    """Main Agent - Replace with your actual agent implementation"""
    
    def __init__(self, version: str = "1.0"):
        self.version = version
        self.name = f"MainAgent_v{version}"
    
    async def query(self, question: str, context: Optional[List[str]] = None) -> Dict[str, Any]:
        """Process user query and return answer"""
        # Simulate processing
        await asyncio.sleep(0.05)
        
        # Mock response - replace with actual agent logic
        answer = f"[Agent v{self.version}] Trả lời: {question[:100]}..."
        
        return {
            "answer": answer,
            "context_used": context or [],
            "model": self.name,
            "version": self.version,
            "timestamp": datetime.now().isoformat()
        }

class MultiModelJudge:
    """Wrapper cho LLMJudge để tương thích với BenchmarkRunner"""
    
    def __init__(self):
        self.llm_judge = get_llm_judge()
    
    async def evaluate_multi_judge(self, question: str, answer: str, ground_truth: str) -> Dict[str, Any]:
        """Wrapper method cho multi-judge evaluation"""
        return await self.llm_judge.evaluate_multi_judge(question, answer, ground_truth)

async def load_dataset() -> List[Dict]:
    """Load golden dataset từ file"""
    dataset_path = Path(__file__).parent / "data" / "golden_set.jsonl"
    
    if not dataset_path.exists():
        logger.error("Dataset not found! Please run: python data/synthetic_gen.py")
        return []
    
    dataset = []
    with open(dataset_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            if line.strip():
                try:
                    case = json.loads(line)
                    # Ensure case has id
                    if "id" not in case:
                        case["id"] = f"case_{line_num:03d}"
                    dataset.append(case)
                except json.JSONDecodeError as e:
                    logger.warning(f"Line {line_num}: Invalid JSON - {e}")
    
    logger.info(f"Loaded {len(dataset)} test cases")
    return dataset

async def run_benchmark_with_results(agent_version: str, dataset: List[Dict]) -> tuple:
    """
    Chạy benchmark cho một phiên bản agent
    
    Returns:
        (results, summary): Danh sách kết quả chi tiết và summary
    """
    logger.info(f"🚀 Starting benchmark for Agent v{agent_version}...")
    
    if not dataset:
        logger.error("No dataset provided")
        return None, None
    
    # Initialize components
    agent = MainAgent(version=agent_version)
    evaluator = ExpertEvaluator()
    judge = MultiModelJudge()
    
    runner = BenchmarkRunner(agent=agent, evaluator=evaluator, judge=judge)
    
    # Run benchmark
    results = await runner.run_all(dataset, batch_size=5, max_concurrent=3)
    
    # Extract summary
    summary = {
        "metadata": {
            "version": agent_version,
            "total_cases": len(dataset),
            "timestamp": datetime.now().isoformat()
        },
        "metrics": results.get("summary", {}),
        "cost_analysis": results.get("cost_analysis", {})
    }
    
    # Add retrieval metrics if available
    if "retrieval_metrics" in summary["metrics"]:
        summary["metrics"]["retrieval"] = summary["metrics"]["retrieval_metrics"]
    
    # Add judge consensus metrics
    valid_results = [r for r in results.get("detailed_results", []) if "judge_metrics" in r]
    if valid_results:
        avg_agreement = sum(r["judge_metrics"].get("agreement_rate", 0) for r in valid_results) / len(valid_results)
        summary["metrics"]["avg_judge_agreement"] = avg_agreement
    
    return results, summary

def calculate_regression_gate(v1_summary: Dict, v2_summary: Dict, thresholds: Dict = None) -> Dict:
    """
    Tính toán regression gate decision với các ngưỡng cấu hình được
    
    Args:
        v1_summary: Summary của phiên bản cũ
        v2_summary: Summary của phiên bản mới
        thresholds: Dict chứa các ngưỡng đánh giá
    """
    default_thresholds = {
        "min_score_improvement": 0.0,  # Không được giảm điểm
        "max_latency_increase": 0.3,   # Tăng latency tối đa 30%
        "min_retrieval_hit_rate": 0.7,  # Hit rate tối thiểu
        "min_agreement_rate": 0.6,      # Agreement rate tối thiểu
        "max_cost_increase": 0.2        # Tăng chi phí tối đa 20%
    }
    
    if thresholds:
        default_thresholds.update(thresholds)
    
    # Extract metrics
    v1_score = v1_summary.get("metrics", {}).get("average_overall_score", 0)
    v2_score = v2_summary.get("metrics", {}).get("average_overall_score", 0)
    
    v1_latency = v1_summary.get("metrics", {}).get("average_latency_seconds", 0)
    v2_latency = v2_summary.get("metrics", {}).get("average_latency_seconds", 0)
    
    v1_retrieval = v1_summary.get("metrics", {}).get("retrieval", {}).get("hit_rate@3", 0)
    v2_retrieval = v2_summary.get("metrics", {}).get("retrieval", {}).get("hit_rate@3", 0)
    
    v1_agreement = v1_summary.get("metrics", {}).get("avg_judge_agreement", 0)
    v2_agreement = v2_summary.get("metrics", {}).get("avg_judge_agreement", 0)
    
    v1_cost = v1_summary.get("cost_analysis", {}).get("estimated_cost_per_1000_tests", 0)
    v2_cost = v2_summary.get("cost_analysis", {}).get("estimated_cost_per_1000_tests", 0)
    
    # Calculate deltas
    score_delta = v2_score - v1_score
    latency_delta_pct = (v2_latency - v1_latency) / v1_latency if v1_latency > 0 else 0
    retrieval_delta = v2_retrieval - v1_retrieval
    agreement_delta = v2_agreement - v1_agreement
    cost_delta_pct = (v2_cost - v1_cost) / v1_cost if v1_cost > 0 else 0
    
    # Check each gate
    checks = {
        "quality_gate": {
            "passed": score_delta >= default_thresholds["min_score_improvement"],
            "value": v2_score,
            "baseline": v1_score,
            "delta": score_delta,
            "threshold": default_thresholds["min_score_improvement"]
        },
        "latency_gate": {
            "passed": latency_delta_pct <= default_thresholds["max_latency_increase"],
            "value": v2_latency,
            "baseline": v1_latency,
            "delta_pct": latency_delta_pct,
            "threshold": default_thresholds["max_latency_increase"]
        },
        "retrieval_gate": {
            "passed": v2_retrieval >= default_thresholds["min_retrieval_hit_rate"],
            "value": v2_retrieval,
            "baseline": v1_retrieval,
            "delta": retrieval_delta,
            "threshold": default_thresholds["min_retrieval_hit_rate"]
        },
        "agreement_gate": {
            "passed": v2_agreement >= default_thresholds["min_agreement_rate"],
            "value": v2_agreement,
            "baseline": v1_agreement,
            "delta": agreement_delta,
            "threshold": default_thresholds["min_agreement_rate"]
        },
        "cost_gate": {
            "passed": cost_delta_pct <= default_thresholds["max_cost_increase"],
            "value": v2_cost,
            "baseline": v1_cost,
            "delta_pct": cost_delta_pct,
            "threshold": default_thresholds["max_cost_increase"]
        }
    }
    
    # Overall decision
    all_passed = all(check["passed"] for check in checks.values())
    
    # Generate recommendation
    if all_passed:
        decision = "APPROVE"
        message = "✅ Tất cả các chỉ số đều đáp ứng yêu cầu. Chấp nhận bản cập nhật."
    elif score_delta >= 0 and not checks["latency_gate"]["passed"]:
        decision = "APPROVE_WITH_WARNING"
        message = f"⚠️ Chấp nhận nhưng latency tăng {latency_delta_pct*100:.1f}% (vượt ngưỡng)"
    else:
        decision = "BLOCK"
        failed_gates = [name for name, check in checks.items() if not check["passed"]]
        message = f"❌ Từ chối do các gate thất bại: {', '.join(failed_gates)}"
    
    return {
        "decision": decision,
        "message": message,
        "checks": checks,
        "summary": {
            "score_delta": score_delta,
            "latency_delta_pct": latency_delta_pct,
            "retrieval_delta": retrieval_delta,
            "cost_delta_pct": cost_delta_pct
        },
        "timestamp": datetime.now().isoformat()
    }

async def run_bias_detection(dataset: List[Dict]) -> Dict:
    """Chạy bias detection cho judge models"""
    logger.info("Running bias detection on judge models...")
    
    judge = get_llm_judge()
    
    # Create test cases for bias detection
    bias_test_cases = []
    for case in dataset[:10]:  # Use first 10 cases
        if len(case.get("expected_answer", "")) > 10:
            bias_test_cases.append({
                "question": case["question"],
                "answer": case.get("actual_answer", case["expected_answer"]),
                "alternative_answer": f"[Alternative] {case['expected_answer'][:100]}...",
                "ground_truth": case["expected_answer"]
            })
    
    results = await judge.evaluate_batch(bias_test_cases, with_bias_check=True)
    
    return results

async def main():
    """Main entry point"""
    print("=" * 70)
    print("🚀 AI Evaluation Factory - Expert Complete System")
    print("=" * 70)
    
    # Load dataset
    dataset = await load_dataset()
    if not dataset:
        print("\n❌ No dataset found. Please run: python data/synthetic_gen.py")
        return
    
    print(f"\n📊 Dataset loaded: {len(dataset)} test cases")
    
    # Chạy benchmark cho phiên bản V1 (baseline)
    print("\n" + "=" * 70)
    print("📈 PHASE 1: Baseline Benchmark (Agent V1)")
    print("=" * 70)
    
    v1_results, v1_summary = await run_benchmark_with_results("1.0", dataset)
    
    if not v1_summary:
        print("❌ Failed to run baseline benchmark")
        return
    
    # Giả lập V2 có cải tiến (trong thực tế, đây là agent thật)
    print("\n" + "=" * 70)
    print("📈 PHASE 2: Optimized Benchmark (Agent V2)")
    print("=" * 70)
    
    # Simulate V2 improvements
    v2_results, v2_summary = await run_benchmark_with_results("2.0", dataset)
    
    if not v2_summary:
        print("❌ Failed to run optimized benchmark")
        return
    
    # Bias detection
    print("\n" + "=" * 70)
    print("🔍 PHASE 3: Bias Detection & Calibration")
    print("=" * 70)
    
    bias_results = await run_bias_detection(dataset)
    
    # Regression gate
    print("\n" + "=" * 70)
    print("🚦 PHASE 4: Regression Gate Analysis")
    print("=" * 70)
    
    gate_decision = calculate_regression_gate(v1_summary, v2_summary)
    
    # Save reports
    print("\n💾 Saving reports...")
    
    reports_dir = Path(__file__).parent / "reports"
    reports_dir.mkdir(exist_ok=True)
    

    # Save benchmark results
    benchmark_path = reports_dir / "benchmark_results.json"
    # Ensure v2_results is serializable
    if v2_results:
        # Convert non-serializable objects
        def make_serializable(obj):
            if isinstance(obj, dict):
                return {k: make_serializable(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [make_serializable(i) for i in obj]
            elif hasattr(obj, '__dict__'):
                return str(obj)
            else:
                return obj
        
        serializable_results = make_serializable(v2_results)
        with open(benchmark_path, 'w', encoding='utf-8') as f:
            json.dump(serializable_results, f, ensure_ascii=False, indent=2)
        print(f"   ✅ Benchmark results saved to {benchmark_path}")
    
    # Save summary report
    summary_report = {
        "timestamp": datetime.now().isoformat(),
        "baseline": v1_summary,
        "optimized": v2_summary,
        "gate_decision": gate_decision,
        "bias_analysis": make_serializable(bias_results) if bias_results else None
    }
    
    summary_path = reports_dir / "summary.json"
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summary_report, f, ensure_ascii=False, indent=2)
    print(f"   ✅ Summary report saved to {summary_path}")
    
    # Print detailed results
    print("\n" + "=" * 70)
    print("📊 BENCHMARK RESULTS COMPARISON")
    print("=" * 70)
    
    # Extract metrics
    v1_metrics = v1_summary.get("metrics", {})
    v2_metrics = v2_summary.get("metrics", {})
    
    print(f"\n{'Metric':<30} {'V1 Baseline':<15} {'V2 Optimized':<15} {'Delta':<10}")
    print("-" * 70)
    
    metrics_to_show = [
        ("average_overall_score", "Overall Score (0-10)"),
        ("pass_rate", "Pass Rate (%)"),
        ("average_latency_seconds", "Latency (s)"),
        ("avg_judge_agreement", "Judge Agreement"),
    ]
    
    for key, label in metrics_to_show:
        v1_val = v1_metrics.get(key, 0)
        v2_val = v2_metrics.get(key, 0)
        delta = v2_val - v1_val
        delta_str = f"+{delta:.3f}" if delta >= 0 else f"{delta:.3f}"
        print(f"{label:<30} {v1_val:<15.3f} {v2_val:<15.3f} {delta_str:<10}")
    
    # Retrieval metrics
    v1_ret = v1_metrics.get("retrieval", {})
    v2_ret = v2_metrics.get("retrieval", {})
    
    if v1_ret and v2_ret:
        print(f"\n{'Retrieval Metric':<30} {'V1 Baseline':<15} {'V2 Optimized':<15} {'Delta':<10}")
        print("-" * 70)
        for key in ["hit_rate@1", "hit_rate@3", "mrr"]:
            v1_val = v1_ret.get(key, 0)
            v2_val = v2_ret.get(key, 0)
            delta = v2_val - v1_val
            delta_str = f"+{delta:.3f}" if delta >= 0 else f"{delta:.3f}"
            print(f"{key:<30} {v1_val:<15.3f} {v2_val:<15.3f} {delta_str:<10}")
    
    # Cost analysis
    v1_cost = v1_summary.get("cost_analysis", {})
    v2_cost = v2_summary.get("cost_analysis", {})
    
    print(f"\n{'Cost Metric':<30} {'V1 Baseline':<15} {'V2 Optimized':<15} {'Delta':<10}")
    print("-" * 70)
    print(f"{'Total Cost ($)':<30} {v1_cost.get('total_cost_usd', 0):<15.4f} {v2_cost.get('total_cost_usd', 0):<15.4f} {(v2_cost.get('total_cost_usd', 0) - v1_cost.get('total_cost_usd', 0)):<+10.4f}")
    print(f"{'Cost per 1K tests ($)':<30} {v1_cost.get('estimated_cost_per_1000_tests', 0):<15.2f} {v2_cost.get('estimated_cost_per_1000_tests', 0):<15.2f} {(v2_cost.get('estimated_cost_per_1000_tests', 0) - v1_cost.get('estimated_cost_per_1000_tests', 0)):<+10.2f}")
    
    # Gate decision
    print("\n" + "=" * 70)
    print("🚦 REGRESSION GATE DECISION")
    print("=" * 70)
    
    decision = gate_decision["decision"]
    if decision == "APPROVE":
        print("✅ " + gate_decision["message"])
    elif decision == "APPROVE_WITH_WARNING":
        print("⚠️ " + gate_decision["message"])
    else:
        print("❌ " + gate_decision["message"])
    
    # Print individual gate results
    print("\n📋 Individual Gate Checks:")
    for gate_name, gate_info in gate_decision["checks"].items():
        status = "✅" if gate_info["passed"] else "❌"
        print(f"   {status} {gate_name}: {gate_info['value']:.3f} (baseline: {gate_info['baseline']:.3f}, threshold: {gate_info['threshold']})")
    
    # Bias detection summary
    if bias_results and bias_results.get("summary"):
        print("\n" + "=" * 70)
        print("🔍 BIAS DETECTION RESULTS")
        print("=" * 70)
        bias_summary = bias_results.get("summary", {})
        print(f"   Total cases analyzed: {bias_summary.get('total_cases', 0)}")
        print(f"   Average agreement: {bias_summary.get('average_agreement', 0):.3f}")
        print(f"   Conflict rate: {bias_summary.get('conflict_rate', 0)*100:.1f}%")
        
        if bias_summary.get('conflict_rate', 0) > 0.3:
            print("   ⚠️ High conflict rate detected! Consider calibrating judges.")
    
    # Save failure analysis
    print("\n" + "=" * 70)
    print("📝 GENERATING FAILURE ANALYSIS REPORT")
    print("=" * 70)
    
    # Analyze failures from results
    if v2_results and v2_results.get("detailed_results"):
        failures = []
        for result in v2_results["detailed_results"]:
            if result.get("status") in ["fail", "needs_improvement"]:
                failures.append({
                    "case_id": result.get("case_id"),
                    "question": result.get("question"),
                    "status": result.get("status"),
                    "score": result.get("overall_score", 0),
                    "error": result.get("error", ""),
                    "retrieval_hit": result.get("retrieval_metrics", {}).get("hit_rate@3", 0)
                })
        
        # Save failure analysis
        failure_report = {
            "timestamp": datetime.now().isoformat(),
            "total_failures": len(failures),
            "failures": failures,
            "recommendations": gate_decision.get("message", "")
        }
        
        failure_path = reports_dir / "failure_analysis.json"
        with open(failure_path, 'w', encoding='utf-8') as f:
            json.dump(failure_report, f, ensure_ascii=False, indent=2)
        print(f"   ✅ Failure analysis saved to {failure_path}")
        print(f"   📊 Found {len(failures)} failed cases out of {len(v2_results.get('detailed_results', []))}")
    
    # Final summary
    print("\n" + "=" * 70)
    print("🎉 BENCHMARK COMPLETED SUCCESSFULLY")
    print("=" * 70)
    print("\n📁 Generated files:")
    print(f"   - {reports_dir}/benchmark_results.json")
    print(f"   - {reports_dir}/summary.json")
    print(f"   - {reports_dir}/failure_analysis.json")
    print(f"   - analysis/failure_analysis.md")
    
    print("\n💡 Next Steps:")
    if decision == "APPROVE":
        print("   1. ✅ Ready to deploy Agent v2.0 to production")
        print("   2. 📊 Monitor performance in production")
        print("   3. 🔄 Continue iterative improvements")
    elif decision == "APPROVE_WITH_WARNING":
        print("   1. ⚠️ Address warnings before full deployment")
        print("   2. 🔧 Optimize latency/cost issues")
        print("   3. 🧪 Run A/B test with 10% traffic")
    else:
        print("   1. ❌ DO NOT deploy - fix critical issues first")
        print("   2. 🔧 Address failed gate checks")
        print("   3. 🏃 Rerun benchmark after fixes")
    
    print("\n" + "=" * 70)
    
    return {
        "baseline": v1_summary,
        "optimized": v2_summary,
        "gate_decision": gate_decision,
        "bias_results": bias_results
    }

if __name__ == "__main__":
    asyncio.run(main())
    
   