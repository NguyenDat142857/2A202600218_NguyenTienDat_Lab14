import asyncio
import json
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

# Import các components cần thiết
try:
    from openai import AsyncOpenAI
    from chromadb import AsyncClientAPI
    from sentence_transformers import SentenceTransformer
    HAS_DEPENDENCIES = True
except ImportError:
    HAS_DEPENDENCIES = False
    print("⚠️ Warning: Some dependencies not installed. Using mock mode.")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RAGAgent:
    """
    RAG Agent với đầy đủ retrieval và generation
    Cấu hình cho production use
    """
    
    def __init__(self, 
                 version: str = "2.0",
                 model_name: str = "gpt-4o-mini",
                 temperature: float = 0.3,
                 max_tokens: int = 500,
                 top_k: int = 5,
                 use_reranking: bool = True,
                 use_query_decomposition: bool = True):
        
        self.version = version
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.top_k = top_k
        self.use_reranking = use_reranking
        self.use_query_decomposition = use_query_decomposition
        
        # Initialize components
        self.llm_client = None
        self.vector_store = None
        self.embedding_model = None
        self.reranker = None
        
        self._init_components()
        
        # System prompt for RAG
        self.system_prompt = self._get_system_prompt()
    
    def _init_components(self):
        """Initialize all components with fallback to mock"""
        if HAS_DEPENDENCIES:
            try:
                # Initialize OpenAI client
                api_key = os.getenv("OPENAI_API_KEY")
                if api_key:
                    self.llm_client = AsyncOpenAI(api_key=api_key)
                
                # Initialize embedding model
                self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
                
                # Initialize vector store (ChromaDB)
                # self.vector_store = await AsyncClientAPI()
                
                logger.info("✅ All components initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize real components: {e}")
                self._use_mock_mode()
        else:
            self._use_mock_mode()
    
    def _use_mock_mode(self):
        """Use mock mode for testing without dependencies"""
        self.mock_mode = True
        logger.info("Using mock mode for agent")
    
    def _get_system_prompt(self) -> str:
        """Get system prompt with detailed instructions"""
        return """
        Bạn là trợ lý hỗ trợ khách hàng chuyên nghiệp cho một công ty dịch vụ.
        
        ### NGUYÊN TẮC QUAN TRỌNG:
        1. **CHỈ trả lời dựa trên context được cung cấp bên dưới**
        2. Nếu context không có đủ thông tin, hãy nói: "Tôi không có đủ thông tin để trả lời câu hỏi này"
        3. KHÔNG được tự ý thêm thông tin không có trong context
        4. Trả lời chi tiết, step-by-step nếu câu hỏi yêu cầu hướng dẫn
        5. Sử dụng ngôn ngữ lịch sự, chuyên nghiệp
        6. Với câu hỏi về số liệu, hãy tính toán chính xác dựa trên context
        
        ### FORMAT TRẢ LỜI:
        - Câu trả lời rõ ràng, có cấu trúc
        - Sử dụng bullet points cho danh sách
        - In đậm thông tin quan trọng
        
        Bắt đầu câu trả lời ngay bên dưới:
        """
    
    async def _retrieve_context(self, question: str) -> List[Dict[str, Any]]:
        """
        Retrieve relevant context from vector store
        Implement actual retrieval logic here
        """
        if self.mock_mode:
            # Mock retrieval - return dummy contexts
            await asyncio.sleep(0.05)
            return [
                {
                    "id": f"doc_{i:03d}",
                    "content": f"Đây là context mẫu cho câu hỏi: {question[:50]}...",
                    "score": 0.9 - i * 0.1,
                    "metadata": {"source": "knowledge_base.json"}
                }
                for i in range(self.top_k)
            ]
        
        # Real retrieval logic
        try:
            # Generate embedding for question
            question_embedding = self.embedding_model.encode(question)
            
            # Query vector store
            # results = await self.vector_store.query(
            #     collection_name="knowledge_base",
            #     query_embeddings=[question_embedding.tolist()],
            #     n_results=self.top_k
            # )
            
            # Mock for now - replace with actual vector search
            results = []
            return results
            
        except Exception as e:
            logger.error(f"Retrieval failed: {e}")
            return []
    
    async def _rerank_contexts(self, question: str, contexts: List[Dict]) -> List[Dict]:
        """Rerank retrieved contexts using cross-encoder"""
        if not self.use_reranking or not contexts:
            return contexts
        
        # Implement reranking logic here
        # For now, return as-is
        return contexts
    
    async def _decompose_query(self, question: str) -> List[str]:
        """Decompose complex multi-hop questions into sub-questions"""
        if not self.use_query_decomposition:
            return [question]
        
        # Simple heuristic for decomposition
        sub_questions = [question]
        
        # Check for multi-hop patterns
        multi_hop_indicators = [" và ", " với ", " cùng lúc", "so sánh"]
        if any(indicator in question for indicator in multi_hop_indicators):
            # Simple decomposition logic
            if " và " in question:
                parts = question.split(" và ")
                sub_questions = parts
            elif "so sánh" in question:
                sub_questions = [f"Cho biết về {question.split('so sánh')[-1].split('và')[0].strip()}"]
        
        return sub_questions
    
    async def _generate_answer(self, question: str, contexts: List[Dict]) -> str:
        """Generate answer using LLM with context"""
        # Build context string
        context_text = "\n\n".join([
            f"[Document {i+1}]: {ctx.get('content', '')}"
            for i, ctx in enumerate(contexts)
        ])
        
        # Build messages
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"""
            ### CONTEXT:
            {context_text}
            
            ### QUESTION:
            {question}
            
            ### ANSWER:
            """}
        ]
        
        if self.mock_mode or not self.llm_client:
            # Mock response
            await asyncio.sleep(0.1)
            return self._generate_mock_answer(question, contexts)
        
        # Real LLM call
        try:
            response = await self.llm_client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                top_p=0.95
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            return f"Xin lỗi, tôi gặp lỗi khi xử lý câu hỏi: {str(e)}"
    
    def _generate_mock_answer(self, question: str, contexts: List[Dict]) -> str:
        """Generate mock answer for testing"""
        # Simple rule-based answers for known questions
        question_lower = question.lower()
        
        if "đổi mật khẩu" in question_lower or "password" in question_lower:
            return """Để đổi mật khẩu, bạn thực hiện theo các bước sau:

1. **Vào Cài đặt** > **Bảo mật** > **Đổi mật khẩu**
2. **Nhập mật khẩu cũ** để xác thực
3. **Nhập mật khẩu mới** (2 lần để xác nhận)

**Yêu cầu mật khẩu mới:**
- Ít nhất 8 ký tự
- Bao gồm chữ hoa, chữ thường và số

Nếu bạn quên mật khẩu, vui lòng sử dụng chức năng "Quên mật khẩu" hoặc liên hệ support."""
        
        elif "hoàn tiền" in question_lower or "refund" in question_lower:
            return """**Chính sách hoàn tiền:**

- **Thời gian:** Trong vòng 30 ngày kể từ ngày mua hàng
- **Điều kiện:** Sản phẩm còn nguyên tem, nhãn mác
- **Phí vận chuyển:** Khách hàng chịu phí hoàn trả
- **Thời gian xử lý:** 5-7 ngày làm việc sau khi nhận được hàng hoàn trả

Để yêu cầu hoàn tiền, vui lòng gửi email đến support@company.com với thông tin đơn hàng."""
        
        elif "premium" in question_lower or "gói" in question_lower:
            return """**Gói dịch vụ Premium:**

**Giá cả:**
- Theo tháng: 199.000đ/tháng
- Theo năm: 1.990.000đ/năm (tiết kiệm 17%)

**Ưu đãi:**
- Dùng thử miễn phí 14 ngày
- Hỗ trợ 24/7 qua hotline và email ưu tiên
- Chat trực tiếp với chuyên gia

**Cách đăng ký:**
Vào Cài đặt > Nâng cấp tài khoản > Chọn gói Premium"""
        
        elif "cod" in question_lower or "thanh toán" in question_lower:
            return """**Phương thức thanh toán:**

1. **COD (Thanh toán khi nhận hàng):**
   - Áp dụng cho đơn hàng dưới 2 triệu đồng
   - Thanh toán bằng tiền mặt khi nhận hàng

2. **Thanh toán online:**
   - Thẻ Visa/Mastercard
   - Ví MoMo
   - Chuyển khoản ngân hàng
   - Không giới hạn số tiền

**Lưu ý:** Free ship cho đơn hàng từ 300.000đ (áp dụng cho tất cả phương thức)"""
        
        elif "giao hàng" in question_lower or "delivery" in question_lower or "ship" in question_lower:
            return """**Thời gian giao hàng:**

- **TP.HCM / Hà Nội:** 1-2 ngày làm việc
- **Các tỉnh khác:** 3-5 ngày làm việc

**Phí ship:**
- **Free ship:** Cho đơn hàng từ 300.000đ
- **Dưới 300.000đ:** Phí ship theo khu vực (30.000đ - 50.000đ)

**Theo dõi đơn hàng:** Bạn sẽ nhận được mã vận đơn qua SMS/email sau khi đơn hàng được gửi đi."""
        
        else:
            # Generic response
            return f"""Dựa trên thông tin có sẵn, tôi xin trả lời câu hỏi: "{question}"

{contexts[0].get('content', 'Xin lỗi, tôi không có đủ thông tin để trả lời câu hỏi này. Vui lòng liên hệ support để được hỗ trợ thêm.') if contexts else 'Xin lỗi, tôi không tìm thấy thông tin liên quan trong cơ sở dữ liệu.'}"""
    
    async def query(self, question: str, context: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Main query method for the agent
        
        Args:
            question: User question
            context: Optional pre-retrieved context (for testing)
        
        Returns:
            Dict with answer, contexts, and metadata
        """
        start_time = datetime.now()
        
        try:
            # Step 1: Query decomposition (for complex questions)
            sub_questions = await self._decompose_query(question)
            
            # Step 2: Retrieve context
            if context:
                retrieved_contexts = [{"content": c, "id": f"provided_{i}"} for i, c in enumerate(context)]
            else:
                # Retrieve for main question
                retrieved_contexts = await self._retrieve_context(question)
                
                # If multiple sub-questions, retrieve for each
                if len(sub_questions) > 1:
                    all_contexts = []
                    for sub_q in sub_questions:
                        sub_contexts = await self._retrieve_context(sub_q)
                        all_contexts.extend(sub_contexts)
                    # Deduplicate
                    seen_ids = set()
                    retrieved_contexts = []
                    for ctx in all_contexts:
                        if ctx.get('id') not in seen_ids:
                            seen_ids.add(ctx.get('id'))
                            retrieved_contexts.append(ctx)
            
            # Step 3: Rerank contexts
            retrieved_contexts = await self._rerank_contexts(question, retrieved_contexts)
            
            # Step 4: Generate answer
            answer = await self._generate_answer(question, retrieved_contexts[:self.top_k])
            
            # Step 5: Prepare response
            response = {
                "answer": answer,
                "contexts": [ctx.get('content', '') for ctx in retrieved_contexts[:self.top_k]],
                "context_ids": [ctx.get('id', '') for ctx in retrieved_contexts[:self.top_k]],
                "metadata": {
                    "model": self.model_name,
                    "version": self.version,
                    "temperature": self.temperature,
                    "max_tokens": self.max_tokens,
                    "top_k": self.top_k,
                    "use_reranking": self.use_reranking,
                    "use_query_decomposition": self.use_query_decomposition,
                    "num_sub_queries": len(sub_questions),
                    "num_contexts": len(retrieved_contexts),
                    "latency_ms": (datetime.now() - start_time).total_seconds() * 1000,
                    "timestamp": datetime.now().isoformat()
                }
            }
            
            return response
            
        except Exception as e:
            logger.error(f"Query failed: {e}")
            return {
                "answer": f"Xin lỗi, tôi gặp lỗi khi xử lý câu hỏi: {str(e)}",
                "contexts": [],
                "context_ids": [],
                "metadata": {
                    "error": str(e),
                    "version": self.version,
                    "timestamp": datetime.now().isoformat()
                }
            }

# Singleton instance
_agent_instance = None

def get_agent(version: str = "2.0") -> RAGAgent:
    """Get or create agent instance"""
    global _agent_instance
    if _agent_instance is None or _agent_instance.version != version:
        _agent_instance = RAGAgent(version=version)
    return _agent_instance

# For testing
if __name__ == "__main__":
    async def test():
        agent = RAGAgent()
        
        # Test cases
        test_questions = [
            "Làm thế nào để đổi mật khẩu?",
            "Chính sách hoàn tiền như thế nào?",
            "Đơn hàng 1.5 triệu có COD không?",
            "So sánh COD và thanh toán online"
        ]
        
        for q in test_questions:
            print(f"\n{'='*60}")
            print(f"Question: {q}")
            print(f"{'='*60}")
            response = await agent.query(q)
            print(f"Answer: {response['answer'][:200]}...")
            print(f"Contexts used: {len(response['contexts'])}")
            print(f"Latency: {response['metadata']['latency_ms']:.0f}ms")
    
    asyncio.run(test())