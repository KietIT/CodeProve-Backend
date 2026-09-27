# Kết quả chấm phản hồi P1.5, vòng 1 (2026-09-27)

Phiếu: `feedback-review.md` (12 lượt, 30 nhận xét, dựng từ preview vòng 3). Trung, Phát, Minh chấm độc lập; Kiệt đồng ý với nhóm nên không nộp phiếu riêng. Trung và Phát góp ý thêm cho 23 mẫu (`phan-hoi-can-duyet.md`). Phiếu gốc giữ ngoài git.

## Tóm tắt

**Chưa đạt tiêu chí P1.5** (0 lộ đáp án và ≥ 80% nhận xét vừa đúng vừa làm theo được):

| Chỉ số (3 người × 30 = 90 lượt chấm) | Kết quả |
|---|---|
| Đúng | 79/90 (88%) |
| Cụ thể | 82/90 (91%) |
| Làm theo được | 71/90 (79%) |
| **Đúng và làm theo được** | **65/90 (72%)**, cần ≥ 80% |
| **Lộ đáp án** | **14/90**, cần 0 |

Hai nguyên nhân chính, cả hai đã sửa:

1. **Câu AI viết cho điểm mạnh nhắc lại cách giải** (13/14 lần bị đánh lộ): 4b, 5b, 6b, 9b (`hypothesis_strong`) và 5a, 6a, 9a (`explain_strong`), ví dụ nêu lại "move_to_end và popitem" hay "phải gọi verify(token)". Lần còn lại là 7c (`pasted_ai_failing`): AI trích một dòng code không có trong lượt làm bài.
2. **Mẫu "Cách cải thiện" dùng ví dụ chỉ hợp bài xử lý mảng** ("rỗng, một phần tử, số âm, giá trị trùng"; "vòng lặp dừng ở đâu, input rỗng"), không áp dụng được cho bài rate limiter, đếm đa luồng, upload hay regex. Đây là phần lớn các ô "Làm theo được = K" (1a, 8a, 11c, 10b, 11a, 12a), cùng với gợi ý "nói thêm độ phức tạp" khi học sinh đã nói rồi (5a, 6a, 9a).

## Theo nguồn câu chữ

| Nguồn "Chuyện gì đã xảy ra" | Đúng | Cụ thể | Làm theo được | Lộ |
|---|---|---|---|---|
| AI viết (23 nhận xét) | 87% | 99% | 81% | 14/69 |
| Mẫu (7 nhận xét) | 90% | 67% | 71% | 0/21 |

| Loại | Lộ |
|---|---|
| Điểm mạnh | 13/39 (33%) |
| Cần cải thiện | 1/51 |

## Từng vấn đề và cách đã sửa

| Nhận xét | Người chấm nói | Đã sửa |
|---|---|---|
| 4b, 5b, 6b, 9b, 5a, 6a, 9a | Nhắc lại cách giải (lộ) | Điểm mạnh luôn dùng câu mẫu, AI không viết |
| 7c | AI bịa dòng code, dễ hiểu là dòng lỗi | Nhận xét về code AI luôn dùng câu mẫu; AI không còn thấy code cuối |
| 7b | Đoán động cơ ("bạn chưa chắc cách làm") | `asked_for_solution` dùng câu mẫu có số lần; prompt cấm đoán động cơ |
| 10b | AI bỏ qua câu explain-back thứ hai | Prompt: xét mọi câu trả lời, chỉ ra câu yếu nhất |
| 1a, 8a, 11c | Ví dụ trường hợp biên không hợp bài | Mẫu không còn ví dụ theo mảng; câu "Chuyện gì đã xảy ra" nêu tên test ẩn fail (ví dụ “limit of one”, tối đa 3, không kèm input) |
| 10b, 11a, 12a, 3a | Ví dụ "vòng lặp dừng / input rỗng" không liên quan | Mẫu `explain_shallow` mới: thêm một câu "vì sao" cho mỗi bước chính |
| 5a, 6a, 9a, 1b, 4a | Gợi ý "nói thêm độ phức tạp" thừa | Mẫu `explain_strong` mới: so sánh với một cách làm khác |
| 2b + 2c | `submitted_failing` và `bug_not_fixed` lặp ý | Chỉ hiện một: bài debug → `bug_not_fixed` (kèm pass x/y), bài khác → `submitted_failing` |
| 3b | "Sửa được lỗi chính" không có căn cứ; nhãn "đặc biệt" khó hiểu | Câu mới chỉ nói test hiển thị pass, test ẩn fail; nhãn thành "giá trị biên", "tình huống đặc biệt" |

Mẫu được viết lại theo góp ý của Trung và Phát: bỏ khẳng định tuyệt đối ("cách chắc chắn nhất", "rủi ro lớn nhất", "kỹ năng quan trọng nhất", "không phụ thuộc AI"), chỉ nói điều hệ thống thấy ("chưa thấy dấu hiệu bạn đã kiểm tra hoặc điều chỉnh"), giọng nhẹ hơn cho `trial_and_error` và `quick_fix`, `integrity_flags` nói rõ đây là tín hiệu và cách đề nghị xem lại. Bản mới: `phan-hoi-can-duyet.md`.

## Chưa sửa ở P1.5

- **Giám khảo explain-back chấm sai** (3a, 8b): lời giải dùng `with threading.Lock():` trong hàm (mỗi lần gọi tạo khoá mới, nên không an toàn) nhưng phần giải thích vẫn được chấm tốt. Lỗi thuộc engine (P1.4), phản hồi chỉ nói lại mức engine đã chấm. Ghi cho P2.
- **Câu hỏi explain-back hỏi kỹ thuật học sinh không dùng** (12a: hỏi "phân vùng" khi lời giải gộp hai mảng). Ghi cho P2 (sinh câu hỏi).
- **Mức nghiêm trọng:** Phát đề nghị hạ `explain_missing` xuống Vừa và `never_ran_tests` xuống Vừa khi bài vẫn pass hết; Trung thấy mức hiện tại hợp lý. Kiệt quyết giữ nguyên (2026-09-27).
- `no_hypothesis`: Phát đề nghị chỉ hiện khi đề yêu cầu ghi hướng giải. Mọi bài CodeProve đều có ô giả thuyết, nên giữ.
- `integrity_flags`: câu mẫu mời học sinh "liên hệ đội CodeProve để được xem lại". Hiện chưa có kênh riêng trong sản phẩm; Kiệt quyết giữ nguyên câu này và không làm kênh riêng (2026-09-27).

## Bước tiếp theo

Chạy lại preview trên EC2 với code mới (vòng 4), kiểm tra tự động, rồi nhóm chấm lại cùng 12 lượt (`build_feedback_review.py` trong `calibration-private/scripts` chọn đúng 12 lượt này). Đạt tiêu chí thì đóng P1.5 và viết plan P1.6.
