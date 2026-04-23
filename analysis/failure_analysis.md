# 🔍 Báo cáo Phân tích Thất bại (Failure Analysis Report)
## AI Evaluation Factory - Expert Version

**Ngày phân tích:** 21/04/2026  
**Người thực hiện:** Nguyễn Tiến Đạt  
**Phiên bản Agent:** SupportAgent-v2.0

---

## 📊 1. Tổng quan Benchmark

### Thống kê cơ bản
| Chỉ số | Giá trị |
|--------|---------|
| **Tổng số cases** | 100 |
| **Số cases Pass** | 78 |
| **Số cases Fail** | 22 |
| **Tỉ lệ Pass/Fail** | 78% / 22% |
| **Tổng thời gian chạy** | 245.3 giây |

### Điểm RAGAS trung bình
| Metric | Score | Target | Status |
|--------|-------|--------|--------|
| **Faithfulness** | 0.74 | 0.85 | ⚠️ Cần cải thiện |
| **Answer Relevancy** | 0.82 | 0.85 | ✅ Tốt |
| **Context Recall** | 0.68 | 0.80 | ❌ Kém |
| **Context Precision** | 0.71 | 0.75 | ⚠️ Trung bình |
| **Answer Similarity** | 0.69 | 0.75 | ⚠️ Trung bình |

### Điểm LLM-Judge trung bình (thang điểm 5)
| Tiêu chí | Score | Target | Status |
|----------|-------|--------|--------|
| **Accuracy** | 3.8 | 4.2 | ⚠️ Cần cải thiện |
| **Professionalism** | 4.2 | 4.0 | ✅ Tốt |
| **Safety** | 4.5 | 4.5 | ✅ Xuất sắc |
| **Helpfulness** | 3.9 | 4.0 | ⚠️ Trung bình |
| **Conciseness** | 3.5 | 4.0 | ❌ Kém |
| **Trung bình** | **3.98** | **4.14** | ⚠️ Dưới target |

### Thống kê Retrieval
| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| **Hit Rate@1** | 0.65 | 0.80 | ❌ Kém |
| **Hit Rate@3** | 0.78 | 0.90 | ⚠️ Trung bình |
| **Hit Rate@5** | 0.85 | 0.95 | ⚠️ Trung bình |
| **MRR** | 0.71 | 0.85 | ❌ Kém |
| **Recall@5** | 0.82 | 0.90 | ⚠️ Trung bình |

---

## 2. Phân nhóm lỗi (Failure Clustering)

### Phân bố lỗi theo category

| Nhóm lỗi | Số lượng | Tỉ lệ | Nguyên nhân dự kiến | Severity |
|----------|----------|-------|---------------------|----------|
| **Hallucination** | 8 | 36.4% | Retriever lấy sai context hoặc context không đủ | 🔴 Critical |
| **Incomplete Answer** | 6 | 27.3% | Prompt quá ngắn, không yêu cầu chi tiết | 🟡 High |
| **Retrieval Failure** | 5 | 22.7% | Chunking không phù hợp, vector search kém | 🔴 Critical |
| **Tone Mismatch** | 2 | 9.1% | Agent trả lời quá suồng sã hoặc quá cứng nhắc | 🟢 Low |
| **Out of Scope** | 1 | 4.5% | Agent không nhận diện được câu hỏi ngoài phạm vi | 🟢 Low |

### Phân bố lỗi theo độ khó

| Difficulty | Total Cases | Fail Cases | Fail Rate | Main Issues |
|------------|-------------|------------|-----------|-------------|
| **Easy** | 30 | 4 | 13.3% | Thiếu chi tiết |
| **Medium** | 35 | 8 | 22.9% | Hallucination, retrieval |
| **Hard** | 20 | 7 | 35.0% | Multi-hop reasoning |
| **Adversarial** | 8 | 2 | 25.0% | Safety từ chối chưa tốt |
| **Edge** | 7 | 1 | 14.3% | Xử lý noise |

### Phân bố lỗi theo category nghiệp vụ

| Category | Fail Rate | Main Issues |
|----------|-----------|-------------|
| **Account** | 10% | Thiếu hướng dẫn chi tiết |
| **Policy** | 25% | Nhầm lẫn điều khoản |
| **Pricing** | 20% | Tính toán sai |
| **Payment** | 30% | Multi-hop COD + shipping |
| **Security** | 15% | Tốt nhất |
| **Multi-hop** | 40% | Kém nhất |

---

## 3. Phân tích 5 Whys (Chi tiết 3 case tệ nhất)

### 🔴 Case #001: Multi-hop Payment + Delivery Failure

**Question:** *"Đơn hàng 1.5 triệu có thể thanh toán COD và được free ship không?"*

**Expected Answer:** *"Có thể COD vì đơn dưới 2 triệu, và được free ship vì đơn trên 300k"*

**Actual Answer:** *"Đơn hàng 1.5 triệu có thể thanh toán COD"* (thiếu thông tin free ship)

**Root Cause Analysis (5 Whys):**

1. **Why 1:** Agent chỉ trả lời về COD, bỏ qua phần free ship
   - *Evidence:* Answer missing shipping information

2. **Why 2:** Context retrieved chỉ có doc_008 (payment), không có doc_009 (delivery)
   - *Evidence:* Retrieved chunks: ["doc_008"], Expected: ["doc_008", "doc_009"]

3. **Why 3:** Vector search không retrieve được doc_009 cho câu hỏi này
   - *Evidence:* Similarity score doc_009 = 0.32 (threshold 0.7)

4. **Why 4:** Chunking strategy tách rời payment và delivery info thành 2 chunks riêng
   - *Evidence:* doc_008 và doc_009 là 2 documents độc lập

5. **Why 5 (Root Cause):** **Thiết kế Chunking đơn giản (fixed-size) không hỗ trợ multi-hop reasoning**
   - *Recommendation:* Implement semantic chunking với overlap và query decomposition

**Action Items:**
- [ ] Implement query decomposition để tách câu hỏi phức tạp
- [ ] Tăng chunk size từ 512 lên 1024 tokens
- [ ] Thêm overlap 20% giữa các chunks
- [ ] Fine-tune embedding cho domain-specific terms

---

### 🔴 Case #002: Hallucination về Policy

**Question:** *"Sản phẩm bị lỗi sau 25 ngày có được hoàn tiền không?"*

**Expected Answer:** *"Được, vì chính sách hoàn tiền trong vòng 30 ngày"*

**Actual Answer:** *"Không, chính sách hoàn tiền chỉ áp dụng trong 14 ngày"* (Hallucination)

**Root Cause Analysis (5 Whys):**

1. **Why 1:** LLM tự sinh thông tin không có trong context
   - *Evidence:* "14 ngày" không xuất hiện trong knowledge base

2. **Why 2:** Context retrieved không đủ thông tin về thời gian hoàn tiền
   - *Evidence:* Retrieved chunk thiếu chi tiết "30 ngày"

3. **Why 3:** Câu hỏi có "25 ngày" làm nhiễu embedding search
   - *Evidence:* Similarity score giảm do con số cụ thể

4. **Why 4:** LLM được prompt không yêu cầu "chỉ trả lời dựa trên context"
   - *Evidence:* System prompt thiếu instruction về faithfulness

5. **Why 5 (Root Cause):** **Prompt Engineering thiếu ràng buộc về hallucination prevention**
   - *Recommendation:* Thêm instruction "Nếu không có thông tin, hãy nói 'Tôi không biết'"

**Action Items:**
- [ ] Cập nhật system prompt: "Chỉ trả lời dựa trên context được cung cấp"
- [ ] Thêm confidence threshold: từ chối trả lời nếu confidence < 0.7
- [ ] Implement RAGAS faithfulness check trong production
- [ ] Fine-tune model với dữ liệu domain-specific

---

### 🟡 Case #003: Incomplete Answer - Thiếu chi tiết

**Question:** *"Làm thế nào để đổi mật khẩu?"*

**Expected Answer:** *"Vào Cài đặt > Bảo mật > Đổi mật khẩu. Nhập mật khẩu cũ, sau đó nhập mật khẩu mới 2 lần. Mật khẩu phải có ít nhất 8 ký tự, bao gồm chữ hoa, chữ thường và số."*

**Actual Answer:** *"Vào phần cài đặt để đổi mật khẩu"* (thiếu 80% thông tin)

**Root Cause Analysis (5 Whys):**

1. **Why 1:** Agent chỉ đưa ra hướng dẫn sơ sài
   - *Evidence:* Missing steps and password requirements

2. **Why 2:** Prompt không yêu cầu trả lời chi tiết, step-by-step
   - *Evidence:* Prompt template quá ngắn gọn

3. **Why 3:** Context retrieved có đủ thông tin nhưng LLM không sử dụng hết
   - *Evidence:* Retrieved doc_001 đầy đủ nhưng answer thiếu

4. **Why 4:** LLM được optimize cho response ngắn (giảm token, giảm cost)
   - *Evidence:* Model config: max_tokens=100 (quá thấp)

5. **Why 5 (Root Cause):** **Configuration không phù hợp với use case hỗ trợ khách hàng**
   - *Recommendation:* Tăng max_tokens và thêm instruction về độ chi tiết

**Action Items:**
- [ ] Tăng max_tokens từ 100 lên 500
- [ ] Thêm instruction: "Trả lời chi tiết, step-by-step"
- [ ] Implement few-shot examples trong prompt
- [ ] A/B test với different prompt templates

---

## 4. Phân tích sâu về Retrieval Failures

### Thống kê chi tiết Retrieval Errors

| Document ID | Times Missed | Queries affected | Reason |
|-------------|--------------|------------------|--------|
| doc_009 | 12 | Delivery questions | Semantic similarity thấp |
| doc_008 | 8 | Payment + COD | Bị overshadow bởi keywords |
| doc_003 | 5 | Pricing calculation | Number confusion |
| doc_002 | 4 | Policy edge cases | Temporal reasoning |

### Vector Search Analysis

```python
# Example of failed retrieval
Query: "Đơn 1.5 triệu có COD không?"
Top 3 retrieved:
1. doc_008 (score: 0.85) - Payment methods ✅
2. doc_007 (score: 0.62) - Promotion ❌
3. doc_003 (score: 0.45) - Premium ❌

Missing: doc_009 (score: 0.32) - Delivery info ❌