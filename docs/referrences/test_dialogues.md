# Bộ hội thoại test 

Mỗi đoạn: câu gốc + bản dịch tham chiếu (đáp án chuẩn).
Format: mỗi block cách nhau bằng dòng `---`, script eval_harness.py đọc tự động bằng regex hoặc json parse.
LANG = vi2en nghĩa là người nói tiếng Việt trước, cần dịch sang tiếng Anh.

## Đoạn 01 — Giới thiệu công ty (VN nói trước)
LANG: vi2en
DOMAIN: Giới thiệu Doanh nghiệp
NOISE_LEVEL: Low (Clean)
S1_SRC: Xin chào, tôi là Minh, đại diện cho công ty TechViet Solutions.
S1_REF: Hello, I'm Minh, representing TechViet Solutions.
S2_SRC: Chúng tôi chuyên cung cấp giải pháp phần mềm cho ngành logistics.
S2_REF: We specialize in providing software solutions for the logistics industry.
S3_SRC: Công ty được thành lập năm 2018, hiện có hơn 120 nhân viên.
S3_REF: The company was founded in 2018 and currently has more than 120 employees.
S4_SRC: Doanh thu năm ngoái của chúng tôi đạt khoảng 50 tỷ đồng.
S4_REF: Our revenue last year reached approximately 50 billion VND.
S5_SRC: Chúng tôi đang tìm kiếm đối tác chiến lược ở khu vực Đông Nam Á.
S5_REF: We are looking for strategic partners in the Southeast Asia region.
S6_SRC: Rất mong được hợp tác lâu dài với quý công ty.
S6_REF: We look forward to a long-term partnership with your company.
GLOSSARY_EVAL: {"TechViet Solutions": "TechViet Solutions", "2018": "2018", "120 nhân viên": "120 employees", "50 tỷ đồng": "50 billion VND"}
---

## Đoạn 02 — Giới thiệu công ty (EN nói trước)
LANG: en2vi
DOMAIN: Giới thiệu Doanh nghiệp
NOISE_LEVEL: Medium (Filler words)
S1_SRC: Good morning, my name is... ah, Sarah, I represent Aurora Tech Singapore.
S1_REF: Chào buổi sáng, tôi tên là Sarah, tôi đại diện cho Aurora Tech Singapore.
S2_SRC: We provide AI-powered supply chain platforms for enterprise clients.
S2_REF: Chúng tôi cung cấp nền tảng chuỗi cung ứng ứng dụng AI cho khách hàng doanh nghiệp.
S3_SRC: We currently serve over 40 clients across 6 countries in the region.
S3_REF: Hiện tại chúng tôi phục vụ hơn 40 khách hàng tại 6 quốc gia trong khu vực.
S4_SRC: Last quarter, our platform processed, you know, more than 2 million transactions.
S4_REF: Quý trước, nền tảng của chúng tôi đã xử lý hơn 2 triệu giao dịch.
S5_SRC: We're excited about the possibility of expanding into the Vietnamese market.
S5_REF: Chúng tôi rất hào hứng với khả năng mở rộng vào thị trường Việt Nam.
S6_SRC: Thank you for taking the time to meet with us today.
S6_REF: Cảm ơn quý vị đã dành thời gian gặp gỡ chúng tôi hôm nay.
GLOSSARY_EVAL: {"Aurora Tech Singapore": "Aurora Tech Singapore", "40 clients": "40 khách hàng", "6 countries": "6 quốc gia", "2 million transactions": "2 triệu giao dịch"}
---

## Đoạn 03 — Đàm phán giá (VN nói trước)
LANG: vi2en
DOMAIN: Đàm phán Tài chính
NOISE_LEVEL: Medium (Code-switching)
S1_SRC: Chúng tôi đã review báo giá của quý công ty, mức giá hơi cao so với budget ban đầu.
S1_REF: We have reviewed your quotation, and the price is a bit high compared to our initial budget.
S2_SRC: Ngân sách của chúng tôi cho project này là khoảng 200 nghìn đô la Mỹ.
S2_REF: Our budget for this project is approximately 200 thousand US dollars.
S3_SRC: Nếu ký hợp đồng 2 năm, quý vị có thể offer giảm giá 10% được không?
S3_REF: If we sign a 2-year contract, could you offer a 10% discount?
S4_SRC: Chúng tôi cũng cần thời gian bảo hành tối thiểu 18 tháng.
S4_REF: We also need a minimum warranty period of 18 months.
S5_SRC: Vậy chúng ta có thể chốt lại các action items vào cuộc họp tuần sau không?
S5_REF: So can we finalize the action items at next week's meeting?
GLOSSARY_EVAL: {"review": "reviewed", "budget": "budget", "project": "project", "200 nghìn đô la Mỹ": "200 thousand US dollars", "2 năm": "2-year", "10%": "10%", "18 tháng": "18 months", "action items": "action items"}
---

## Đoạn 04 — Đàm phán giá (EN nói trước)
LANG: en2vi
DOMAIN: Đàm phán Tài chính
NOISE_LEVEL: High (Self-correction & Disfluency)
S1_SRC: We would like to discuss the pricing for the next quarter.
S1_REF: Chúng tôi muốn thảo luận về giá cho quý tới.
S2_SRC: Our current offer is... let me check... 15% lower than the market average.
S2_REF: Đề nghị hiện tại của chúng tôi thấp hơn 15% so với mức trung bình thị trường.
S3_SRC: However, we can only guarantee this rate for orders above... sorry, above 500 units.
S3_REF: Tuy nhiên, chúng tôi chỉ có thể đảm bảo mức giá này cho đơn hàng trên 500 đơn vị.
S4_SRC: Can we schedule a follow-up meeting next Monday at 9 AM?
S4_REF: Chúng ta có thể sắp xếp một cuộc họp tiếp theo vào thứ Hai tuần sau lúc 9 giờ sáng không?
S5_SRC: I'll send the revised proposal by email this afternoon.
S5_REF: Tôi sẽ gửi bản đề xuất đã chỉnh sửa qua email vào chiều nay.
GLOSSARY_EVAL: {"15%": "15%", "500 units": "500 đơn vị", "9 AM": "9 giờ sáng", "revised proposal": "bản đề xuất đã chỉnh sửa"}
---

## Đoạn 05 — Thảo luận hợp đồng (VN nói trước)
LANG: vi2en
DOMAIN: Pháp lý & Hợp đồng
NOISE_LEVEL: Medium (Code-switching nhẹ)
S1_SRC: Payment terms trong hợp đồng đang ghi là 30% trước, 70% sau khi nghiệm thu.
S1_REF: The payment terms in the contract state 30% upfront and 70% upon acceptance.
S2_SRC: Chúng tôi muốn điều chỉnh thành 3 đợt thanh toán thay vì 2 đợt.
S2_REF: We would like to adjust this to 3 payment installments instead of 2.
S3_SRC: Về điều khoản phạt vi phạm, mức phạt hiện tại là 0.5% mỗi ngày trễ hạn.
S3_REF: Regarding the penalty clause, the current penalty is 0.5% per day of delay.
S4_SRC: Thời hạn hợp đồng là 12 tháng, có thể gia hạn thêm 6 tháng.
S4_REF: The contract term is 12 months, with a possible 6-month extension.
S5_SRC: Team legal của chúng tôi sẽ xem lại bản dự thảo trước khi ký chính thức.
S5_REF: Our legal team will review the draft before the official signing.
GLOSSARY_EVAL: {"Payment terms": "payment terms", "30%": "30%", "70%": "70%", "0.5%": "0.5%", "12 tháng": "12 months", "6 tháng": "6-month", "Team legal": "legal team"}
---

## Đoạn 06 — Thảo luận hợp đồng (EN nói trước)
LANG: en2vi
DOMAIN: Pháp lý & Hợp đồng
NOISE_LEVEL: Low (Clean - Ngôn ngữ pháp lý chuẩn)
S1_SRC: Let's go over the confidentiality clause in section 4 of the contract.
S1_REF: Hãy cùng xem lại điều khoản bảo mật ở mục 4 của hợp đồng.
S2_SRC: This clause remains valid for 5 years after the contract ends.
S2_REF: Điều khoản này vẫn có hiệu lực trong 5 năm sau khi hợp đồng kết thúc.
S3_SRC: We propose adding an arbitration clause in case of any disputes.
S3_REF: Chúng tôi đề xuất thêm điều khoản trọng tài trong trường hợp có tranh chấp.
S4_SRC: Both parties must give written notice at least 60 days before termination.
S4_REF: Cả hai bên phải thông báo bằng văn bản ít nhất 60 ngày trước khi chấm dứt hợp đồng.
S5_SRC: I believe this covers all the key terms for now.
S5_REF: Tôi nghĩ điều này đã bao quát các điều khoản chính cho hiện tại.
GLOSSARY_EVAL: {"confidentiality clause": "điều khoản bảo mật", "5 years": "5 năm", "arbitration clause": "điều khoản trọng tài", "60 days": "60 ngày"}
---

## Đoạn 07 — Hỏi đáp kỹ thuật sản phẩm (VN nói trước)
LANG: vi2en
DOMAIN: Kỹ thuật (IT)
NOISE_LEVEL: High (Code-switching chuyên ngành)
S1_SRC: Hệ thống của chúng tôi hiện tại support tích hợp qua API REST và webhook.
S1_REF: Our system currently supports integration via REST API and webhooks.
S2_SRC: Thời gian phản hồi trung bình là dưới 200 mili giây.
S2_REF: The average response time is under 200 milliseconds.
S3_SRC: Dữ liệu được mã hóa theo chuẩn AES-256 khi lưu trữ và truyền tải.
S3_REF: Data is encrypted using the AES-256 standard both at rest and in transit.
S4_SRC: Hệ thống có khả năng scale để handle tới 10 nghìn request mỗi giây.
S4_REF: The system can scale to handle up to 10 thousand requests per second.
S5_SRC: Chúng tôi cung cấp tài liệu API đầy đủ và hỗ trợ kỹ thuật 24/7.
S5_REF: We provide full API documentation and 24/7 technical support.
GLOSSARY_EVAL: {"support": "supports", "API REST": "REST API", "webhook": "webhooks", "AES-256": "AES-256", "200 mili giây": "200 milliseconds", "scale": "scale", "handle": "handle", "10 nghìn": "10 thousand", "24/7": "24/7"}
---

## Đoạn 08 — Hỏi đáp kỹ thuật sản phẩm (EN nói trước)
LANG: en2vi
DOMAIN: Kỹ thuật (IT)
NOISE_LEVEL: Medium (Filler words)
S1_SRC: How does your platform handle data backup and disaster recovery?
S1_REF: Nền tảng của quý vị xử lý sao lưu dữ liệu và khôi phục sau sự cố như thế nào?
S2_SRC: We perform automatic backups every 6 hours with a 99.9% uptime guarantee.
S2_REF: Chúng tôi thực hiện sao lưu tự động mỗi 6 giờ với cam kết thời gian hoạt động 99.9%.
S3_SRC: Is the system compatible with, um, on-premise deployment for sensitive data?
S3_REF: Hệ thống có tương thích với triển khai tại chỗ cho dữ liệu nhạy cảm không?
S4_SRC: Yes, we offer both cloud and on-premise deployment options.
S4_REF: Có, chúng tôi cung cấp cả tùy chọn triển khai trên đám mây và tại chỗ.
S5_SRC: What is the estimated onboarding time for a new client?
S5_REF: Thời gian dự kiến để triển khai cho một khách hàng mới là bao lâu?
GLOSSARY_EVAL: {"disaster recovery": "khôi phục sau sự cố", "6 hours": "6 giờ", "99.9% uptime": "thời gian hoạt động 99.9%", "on-premise": "tại chỗ"}
---

## Đoạn 09 — Chốt thời gian giao hàng (VN nói trước)
LANG: vi2en
DOMAIN: Vận hành & Logistics
NOISE_LEVEL: High (Self-correction)
S1_SRC: Đơn hàng lần này gồm 500 sản phẩm, cần giao trước ngày 15 tháng 8.
S1_REF: This order consists of 500 units and needs to be delivered before August 15th.
S2_SRC: Thời gian sản xuất tiêu chuẩn của chúng tôi là 3 tuần.
S2_REF: Our standard production time is 3 weeks.
S3_SRC: Nếu đặt hàng gấp... à không, nếu là đơn urgent, chúng tôi có thể rút ngắn xuống còn 10 ngày với phụ phí 5%.
S3_REF: For urgent orders, we can shorten it to 10 days with a 5% surcharge.
S4_SRC: Hàng sẽ được vận chuyển bằng đường biển, dự kiến mất thêm 2 tuần.
S4_REF: The goods will be shipped by sea, which takes an additional 2 weeks.
S5_SRC: Chúng tôi sẽ gửi mã tracking đơn hàng ngay sau khi xuất kho.
S5_REF: We will send the tracking number right after the shipment leaves the warehouse.
GLOSSARY_EVAL: {"500 sản phẩm": "500 units", "15 tháng 8": "August 15th", "3 tuần": "3 weeks", "urgent": "urgent", "10 ngày": "10 days", "phụ phí 5%": "5% surcharge", "mã tracking": "tracking number"}
---

## Đoạn 10 — Chốt thời gian giao hàng (EN nói trước)
LANG: en2vi
DOMAIN: Vận hành & Logistics
NOISE_LEVEL: High (Self-correction & Thay đổi thông tin)
S1_SRC: We need the shipment to arrive by September 1st... actually, no, make it September 5th at the latest.
S1_REF: Chúng tôi cần lô hàng đến nơi chậm nhất là ngày 5 tháng 9.
S2_SRC: That timeline is tight, but we can arrange air freight instead of sea freight.
S2_REF: Thời hạn đó khá gấp, nhưng chúng tôi có thể sắp xếp vận chuyển bằng đường hàng không thay vì đường biển.
S3_SRC: Air freight would increase the cost by approximately 20%.
S3_REF: Vận chuyển đường hàng không sẽ làm tăng chi phí khoảng 20%.
S4_SRC: That's acceptable, given the urgency of this order.
S4_REF: Điều đó chấp nhận được, vì tính cấp bách của đơn hàng này.
S5_SRC: We'll confirm the final delivery date within 24 hours.
S5_REF: Chúng tôi sẽ xác nhận ngày giao hàng cuối cùng trong vòng 24 giờ.
GLOSSARY_EVAL: {"September 5th": "5 tháng 9", "air freight": "đường hàng không", "20%": "20%", "24 hours": "24 giờ"}