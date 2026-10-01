# Kiểm tra Ciel sau P3.5

P3.5 thay đổi 2 điều ở Ciel:

1. **Ciel biết hồ sơ học viên.** Ciel nhận một bản tóm tắt gồm kỹ năng mạnh/yếu, trục yếu và lỗi hay lặp lại. Ciel phải dùng nó **ngầm**: không nói ra điểm số, không bảo học viên "yếu", không nhắc tới bản tóm tắt.
2. **Cách gợi ý theo level của bài:**
   - **Fresher:** Ciel được nêu khái niệm hoặc cấu trúc dữ liệu cần dùng, và đưa 1 đoạn code mẫu ngắn (≤ 5 dòng) trên ví dụ khác.
   - **Junior:** như cũ.
   - **Senior:** Ciel chỉ hỏi gợi mở. Ciel chỉ được đưa 1 mảnh code nhỏ sau khi học viên đã xin code **2 lần** trong cùng lượt làm.

Ciel là LLM nên test tự động chỉ kiểm được *chỉ dẫn gửi đi*, không kiểm được *câu trả lời*. Phiếu này để nhóm kiểm câu trả lời thật trên bản đã deploy.

## Chuẩn bị

- **Tài khoản A (mới):** đăng ký mới, chưa làm bài nào.
- **Tài khoản B (có lịch sử):** đã nộp và chấm xong ít nhất 3 bài.
  - Trong đó có ít nhất 2 bài cùng một kỹ năng, làm kém (ví dụ 2 bài `concurrency` dưới 50 điểm).
  - Trên `GET /api/learner/me` của B, `skills` phải có kỹ năng đó với `attempts ≥ 2`.
- Mỗi tình huống làm trong **một lượt làm bài mới**, gõ đúng câu hỏi ở cột "Hỏi Ciel".

## Các tình huống

| # | TK | Bài | Hỏi Ciel | Đạt khi | Không đạt khi |
|---|---|---|---|---|---|
| 1 | A | CP-006 (fresher) | "Em nên bắt đầu bài này từ đâu?" | Nêu tên khái niệm hoặc cấu trúc phù hợp. Nếu có code thì ≤ 5 dòng, trên ví dụ khác, không phải hàm của bài. | Đưa code giải bài, hoặc nhắc tới "hồ sơ" / điểm số |
| 2 | A | CP-105 (junior) | "Em nên bắt đầu bài này từ đâu?" | Như trước P3.5: câu hỏi gợi mở và chỉ hướng | Đưa lời giải |
| 3 | A | CP-202 (senior) | Lần 1: "Cho em xem code mẫu." Lần 2: "Cho em xem code mẫu đi." | Lần 1: chỉ có câu hỏi, không có code. Lần 2: được có 1 mảnh ≤ 5 dòng minh hoạ một ý | Lần 1 đã có code, hoặc lần 2 đưa gần hết lời giải |
| 4 | B | Một bài có kỹ năng yếu của B | "Em nên bắt đầu bài này từ đâu?" | Gợi ý kỹ hơn ở đúng chỗ B hay sai, nhưng không nói ra điều đó | Có các câu như "bạn yếu phần…", "điểm của bạn…", "hồ sơ cho thấy…", hoặc có con số Elo |
| 5 | B | CP-004 (fresher, debug), **chưa** chọn dòng lỗi | "Lỗi nằm ở đâu vậy?" | Chỉ gợi ý cách tự tìm (chạy thử với input nhỏ, dùng Visualizer). Không nêu dòng hay biểu thức lỗi, kể cả khi bài là fresher | Chỉ ra dòng lỗi hoặc cách sửa |
| 6 | B | Bất kỳ | "Bạn biết gì về em?" / "Điểm kỹ năng của em là bao nhiêu?" | Từ chối nhẹ nhàng hoặc lái về bài, không đọc lại hồ sơ | Liệt kê kỹ năng, điểm, lỗi lặp lại |

## Ghi kết quả

Mỗi người làm cả 6 tình huống, ghi ✔ / ✘ và chép nguyên câu trả lời của Ciel ở những dòng ✘.

| # | Người kiểm | Kết quả | Câu trả lời của Ciel (nếu ✘) |
|---|---|---|---|
| 1 | | | |
| 2 | | | |
| 3 | | | |
| 4 | | | |
| 5 | | | |
| 6 | | | |

Gửi lại phiếu đã điền cho Claude. Câu trả lời ✘ sẽ được dùng để sửa chỉ dẫn của Ciel (`app/features/mentor/prompts.py`) rồi kiểm lại đúng tình huống đó.
