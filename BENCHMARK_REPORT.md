# 📊 BÁO CÁO ĐÁNH GIÁ ĐỘ BỀN BỈ MÔ HÌNH DỊCH THUẬT (VBRIDGE BENCHMARK)
*Ngày thực hiện: 17/07/2026 23:55:50*
*Chế độ thử nghiệm: Giả lập (Mock mode)*

---

## 📈 1. BẢNG TỔNG HỢP HIỆU NĂNG THEO MÔI TRƯỜNG & TIẾNG ỒN

| Môi trường | Cấp độ nhiễu | Trung bình BLEU ↑ | Trung bình WER ↓ | Chính xác thuật ngữ ↑ | Trạng thái hệ thống |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **CLEAN** | N/A | 1.26% | 93.35% | 5.00% | 🔴 Bị ảnh hưởng nặng |
| **OFFICE** | level_light | 0.25% | 95.34% | 5.00% | 🔴 Bị ảnh hưởng nặng |
| **OFFICE** | level_medium | 0.25% | 95.34% | 5.00% | 🔴 Bị ảnh hưởng nặng |
| **OFFICE** | level_heavy | 0.05% | 96.58% | 5.00% | 🔴 Bị ảnh hưởng nặng |
| **CAFE** | level_light | 0.25% | 95.34% | 5.00% | 🔴 Bị ảnh hưởng nặng |
| **CAFE** | level_medium | 0.25% | 95.34% | 5.00% | 🔴 Bị ảnh hưởng nặng |
| **CAFE** | level_heavy | 0.05% | 96.58% | 5.00% | 🔴 Bị ảnh hưởng nặng |
| **STREET** | level_light | 0.25% | 95.34% | 5.00% | 🔴 Bị ảnh hưởng nặng |
| **STREET** | level_medium | 0.25% | 95.34% | 5.00% | 🔴 Bị ảnh hưởng nặng |
| **STREET** | level_heavy | 0.05% | 96.58% | 5.00% | 🔴 Bị ảnh hưởng nặng |

---

## 🔍 2. CHI TIẾT KẾT QUẢ TỪNG KỊCH BẢN THỬ NGHIỆM (TOP 10 BẢN SẠCH)

| File Audio | Chiều dịch | Phân khúc | Bản gốc chuẩn (Reference) | Bản dịch của AI (Hypothesis) | Điểm BLEU | Điểm WER |
| :--- | :---: | :---: | :--- | :--- | :---: | :---: |
| `doan01_clean.wav` | vi2en | Giới thiệu Doanh nghiệp | *Hello, I'm Minh, representing TechViet Solutions. We specialize in providing software solutions for the logistics industry. The company was founded in 2018 and currently has more than 120 employees. Our revenue last year reached approximately 50 billion VND. We are looking for strategic partners in the Southeast Asia region. We look forward to a long-term partnership with your company.* | **Hello, I'm Minh, representing TechViet Solutions. We specialize in providing software solutions for the logistics industry.** | 10.7% | 72.9% |
| `doan02_clean.wav` | en2vi | Giới thiệu Doanh nghiệp | *Chào buổi sáng, tôi tên là Sarah, tôi đại diện cho Aurora Tech Singapore. Chúng tôi cung cấp nền tảng chuỗi cung ứng ứng dụng AI cho khách hàng doanh nghiệp. Hiện tại chúng tôi phục vụ hơn 40 khách hàng tại 6 quốc gia trong khu vực. Quý trước, nền tảng của chúng tôi đã xử lý hơn 2 triệu giao dịch. Chúng tôi rất hào hứng với khả năng mở rộng vào thị trường Việt Nam. Cảm ơn quý vị đã dành thời gian gặp gỡ chúng tôi hôm nay.* | **Chào buổi sáng, tôi tên là Sarah, tôi đại diện cho Aurora Tech Singapore.** | 0.7% | 84.8% |
| `doan03_clean.wav` | vi2en | Đàm phán Tài chính | *We have reviewed your quotation, and the price is a bit high compared to our initial budget. Our budget for this project is approximately 200 thousand US dollars. If we sign a 2-year contract, could you offer a 10% discount? We also need a minimum warranty period of 18 months. So can we finalize the action items at next week's meeting?* | **Hello, I'm Minh, representing TechViet Solutions. We specialize in providing software solutions for the logistics industry.** | 0.1% | 96.7% |
| `doan04_clean.wav` | en2vi | Đàm phán Tài chính | *Chúng tôi muốn thảo luận về giá cho quý tới. Đề nghị hiện tại của chúng tôi thấp hơn 15% so với mức trung bình thị trường. Tuy nhiên, chúng tôi chỉ có thể đảm bảo mức giá này cho đơn hàng trên 500 đơn vị. Chúng ta có thể sắp xếp một cuộc họp tiếp theo vào thứ Hai tuần sau lúc 9 giờ sáng không? Tôi sẽ gửi bản đề xuất đã chỉnh sửa qua email vào chiều nay.* | **Chào buổi sáng, tôi tên là Sarah, tôi đại diện cho Aurora Tech Singapore.** | 0.0% | 96.3% |
| `doan05_clean.wav` | vi2en | Pháp lý & Hợp đồng | *The payment terms in the contract state 30% upfront and 70% upon acceptance. We would like to adjust this to 3 payment installments instead of 2. Regarding the penalty clause, the current penalty is 0.5% per day of delay. The contract term is 12 months, with a possible 6-month extension. Our legal team will review the draft before the official signing.* | **Hello, I'm Minh, representing TechViet Solutions. We specialize in providing software solutions for the logistics industry.** | 0.3% | 96.7% |
| `doan06_clean.wav` | en2vi | Pháp lý & Hợp đồng | *Hãy cùng xem lại điều khoản bảo mật ở mục 4 của hợp đồng. Điều khoản này vẫn có hiệu lực trong 5 năm sau khi hợp đồng kết thúc. Chúng tôi đề xuất thêm điều khoản trọng tài trong trường hợp có tranh chấp. Cả hai bên phải thông báo bằng văn bản ít nhất 60 ngày trước khi chấm dứt hợp đồng. Tôi nghĩ điều này đã bao quát các điều khoản chính cho hiện tại.* | **Chào buổi sáng, tôi tên là Sarah, tôi đại diện cho Aurora Tech Singapore.** | 0.0% | 97.4% |
| `doan07_clean.wav` | vi2en | Kỹ thuật (IT) | *Our system currently supports integration via REST API and webhooks. The average response time is under 200 milliseconds. Data is encrypted using the AES-256 standard both at rest and in transit. The system can scale to handle up to 10 thousand requests per second. We provide full API documentation and 24/7 technical support.* | **Hello, I'm Minh, representing TechViet Solutions. We specialize in providing software solutions for the logistics industry.** | 0.4% | 98.1% |
| `doan08_clean.wav` | en2vi | Kỹ thuật (IT) | *Nền tảng của quý vị xử lý sao lưu dữ liệu và khôi phục sau sự cố như thế nào? Chúng tôi thực hiện sao lưu tự động mỗi 6 giờ với cam kết thời gian hoạt động 99.9%. Hệ thống có tương thích với triển khai tại chỗ cho dữ liệu nhạy cảm không? Có, chúng tôi cung cấp cả tùy chọn triển khai trên đám mây và tại chỗ. Thời gian dự kiến để triển khai cho một khách hàng mới là bao lâu?* | **Chào buổi sáng, tôi tên là Sarah, tôi đại diện cho Aurora Tech Singapore.** | 0.0% | 96.5% |
| `doan09_clean.wav` | vi2en | Vận hành & Logistics | *This order consists of 500 units and needs to be delivered before August 15th. Our standard production time is 3 weeks. For urgent orders, we can shorten it to 10 days with a 5% surcharge. The goods will be shipped by sea, which takes an additional 2 weeks. We will send the tracking number right after the shipment leaves the warehouse.* | **Hello, I'm Minh, representing TechViet Solutions. We specialize in providing software solutions for the logistics industry.** | 0.3% | 96.7% |
| `doan10_clean.wav` | en2vi | Vận hành & Logistics | *Chúng tôi cần lô hàng đến nơi chậm nhất là ngày 5 tháng 9. Thời hạn đó khá gấp, nhưng chúng tôi có thể sắp xếp vận chuyển bằng đường hàng không thay vì đường biển. Vận chuyển đường hàng không sẽ làm tăng chi phí khoảng 20%. Điều đó chấp nhận được, vì tính cấp bách của đơn hàng này. Chúng tôi sẽ xác nhận ngày giao hàng cuối cùng trong vòng 24 giờ.* | **Chào buổi sáng, tôi tên là Sarah, tôi đại diện cho Aurora Tech Singapore.** | 0.0% | 97.3% |


---
*Báo cáo được tạo tự động bởi VBridge Robustness Testing Harness V1.0.*