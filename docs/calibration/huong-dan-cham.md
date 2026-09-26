# Hướng dẫn chấm bộ mẫu chuẩn

Dành cho 4 thành viên: Kiệt, Trung, Minh, Phát. Đọc hết trang này trước khi chấm lượt đầu tiên (khoảng 15 phút).

## Mình đang làm gì và để làm gì?

CodeProve tự chấm mỗi lượt làm bài theo 6 trục (Thấu hiểu, Giả thuyết, Prompting, Kiểm chứng, Testing, Debug). Nhóm chưa từng kiểm tra xem **điểm máy chấm có khớp với đánh giá của con người không**.

Bộ mẫu chuẩn là 40 lượt làm bài mô phỏng: Claude viết kịch bản cho 20 "học sinh" (mỗi bạn 2 bài, đủ mọi mức từ yếu tới rất tốt) và chạy chúng qua hệ thống thật, nên Ciel, test, câu hỏi explain-back và điểm máy chấm đều là kết quả thật. Bạn không được biết kịch bản dự kiến lượt nào ở mức nào: cứ chấm đúng những gì lượt làm bài thể hiện.

Mỗi lượt được **4 người chấm tay độc lập**. Sau đó so sánh:

1. **4 người có chấm giống nhau không?** Nếu không, bảng mô tả mức điểm bên dưới đang mơ hồ, phải sửa.
2. **Máy chấm có giống người không?** Nếu không, trục nào lệch thì sửa cách máy chấm trục đó.

Kết quả này quyết định cách CodeProve chấm điểm sau này, nên hãy chấm cẩn thận và **trung thực với những gì bạn thấy**.

## 4 quy tắc bắt buộc

1. **Chấm một mình.** Không bàn với ai, không xem người khác chấm gì, **cho tới khi cả nhóm chấm xong**. Nếu bàn trước, kết quả "4 người đồng thuận" sẽ vô nghĩa.
2. **Chấm những gì lượt làm bài thể hiện**, không đoán người đó giỏi hay dở. Ví dụ: code đúng nhưng câu giải thích sai thì trục Thấu hiểu vẫn thấp.
3. **Mỗi lượt chỉ chấm một lần**, không quay lại sửa sau khi đã chấm các lượt khác. Chấm lại theo cảm giác sau sẽ làm lệch kết quả.
4. **Chọn "Không áp dụng" khi lượt làm bài không có cơ hội thể hiện trục đó**, theo đúng quy định của từng trục bên dưới. Không cho 0 thay cho "Không áp dụng", và ngược lại.

## Cách đọc một lượt làm bài

Trên trang chấm, mỗi lượt hiện theo thứ tự thời gian:

- **Đề bài** (mã bài, bài implement hay debug).
- **Giả thuyết** user ghi (nếu có), kèm phút ghi.
- **Các câu hỏi gửi Ciel và câu trả lời của Ciel.** Câu trả lời nào có **lỗi cài sẵn** (Ciel cố ý đưa code sai để thử người học) sẽ được đánh dấu.
- **Các lần chạy test** (phút, tỉ lệ pass, có phải chạy code khởi đầu chưa sửa không).
- **Kết quả Submit** (pass bao nhiêu test, kể cả test ẩn).
- **Code cuối cùng.**
- **Câu hỏi và câu trả lời explain-back.**

## Bảng mức điểm cho từng trục

Mỗi trục chọn **0, 1, 2, 3** hoặc **Không áp dụng**.

### Thấu hiểu

Dựa chủ yếu vào **câu trả lời explain-back**: người đó có hiểu lời giải của chính mình không.

| Mức | Mô tả | Ví dụ (bài cộng 1..n) |
|---|---|---|
| 0 | Không trả lời, trả lời lạc đề hoặc sai | "không biết", "vì code chạy được" |
| 1 | Mơ hồ hoặc đúng một phần | "vì cần cộng các số" |
| 2 | Đúng nhưng chỉ nói **làm gì**, chưa nói **vì sao** | "vòng lặp chạy từ 1 tới n rồi cộng dồn" |
| 3 | Đúng và giải thích được **vì sao**, kể cả trường hợp đặc biệt | "range(1, n + 1) vì range dừng trước số cuối; n = 0 thì vòng lặp không chạy nên trả 0" |

Không có "Không áp dụng" cho trục này.

### Giả thuyết

Dựa vào **giả thuyết ghi trước khi code**.

| Mức | Mô tả | Ví dụ |
|---|---|---|
| 0 | Không ghi giả thuyết | — |
| 1 | Chung chung, không định hướng được lời giải | "dùng vòng lặp" |
| 2 | Nêu đúng hướng giải | "dùng dict lưu số đã gặp để tra phần bù" |
| 3 | Đúng hướng và nêu được trường hợp đặc biệt hoặc độ phức tạp, **ghi trước khi code** | "dict lưu số đã gặp, O(n); cẩn thận hai số bằng nhau như [3, 3]" |

Không có "Không áp dụng": ô giả thuyết luôn có sẵn. Nếu lượt làm bài cũ hiện "(không lưu nội dung)", dựa vào đánh giá đúng/sai đi kèm và cho **tối đa mức 2**.

### Prompting (cách hỏi Ciel)

**Không áp dụng** nếu người đó **không hỏi Ciel lần nào**.

| Mức | Mô tả | Ví dụ |
|---|---|---|
| 0 | Xin thẳng lời giải, hoặc hỏi lạc đề | "viết code cho tôi", "cho đáp án" |
| 1 | Câu hỏi ngắn, mơ hồ | "sửa giúp", "sai chỗ nào?" |
| 2 | Câu hỏi cụ thể, có ngữ cảnh | "Vì sao test với n = 0 fail?" |
| 3 | Cụ thể, nói rõ đã thử gì và sai ở đâu, xin **hướng dẫn** chứ không xin đáp án | "Mình dùng range(1, n) thì n = 3 ra 3 thay vì 6, mình đoán vòng lặp thiếu một số, đúng không?" |

Nếu có nhiều câu hỏi, chấm theo **mức đại diện cho đa số**, không theo câu hay nhất hay câu tệ nhất.

### Kiểm chứng (với code AI đưa ra)

**Không áp dụng** nếu **Ciel không đưa đoạn code nào**.

| Mức | Mô tả |
|---|---|
| 0 | Dùng code AI mà không kiểm tra; nếu có lỗi cài sẵn thì lỗi đó **vẫn còn** trong code cuối |
| 1 | Có dùng code AI, kiểm tra qua loa |
| 2 | Chạy test sau khi nhận code AI |
| 3 | Phát hiện và sửa lỗi trong code AI, hoặc đặt câu hỏi nghi ngờ đoạn code đó |

Ciel đưa code nhưng người học **không dùng** đoạn đó (tự viết, tự kiểm tra): chấm **mức 2**; nếu còn đặt câu hỏi nghi ngờ đoạn code đó thì **mức 3**.

### Testing

Dựa vào **các lần chạy test và kết quả Submit**.

| Mức | Mô tả |
|---|---|
| 0 | Không chạy test lần nào, hoặc Submit khi còn fail gần hết |
| 1 | Có chạy nhưng bỏ qua test fail rồi Submit |
| 2 | Test hiển thị pass hết, nhưng còn fail test ẩn khi Submit |
| 3 | Pass toàn bộ, kể cả test ẩn |

Không có "Không áp dụng" cho trục này.

### Debug

- **Bài debug** (có sẵn code lỗi): luôn chấm.
- **Bài implement**: **Không áp dụng** nếu code **chưa từng chạy fail**. Chạy code khởi đầu chưa sửa thì không tính là fail.

| Mức | Mô tả |
|---|---|
| 0 | Không sửa được lỗi (còn test hiển thị fail khi Submit) |
| 1 | Sửa được bằng cách thử-sai: chạy rất nhiều lần, thay đổi lung tung |
| 2 | Sửa được sau vài lần thử có định hướng; **hoặc** sửa được lỗi thấy được (test hiển thị pass hết) nhưng còn sót trường hợp biên (test ẩn fail) |
| 3 | Tìm đúng chỗ và sửa nhanh, có lý do rõ ràng (thể hiện qua giả thuyết, câu hỏi Ciel hoặc explain-back) |

## Mức tổng thể

Sau 6 trục, chọn **một mức tổng thể** theo ấn tượng chung. Không cần cộng điểm các trục.

| Mức | Mô tả |
|---|---|
| **Emerging** | Chưa giải được, hoặc giải được mà không hiểu mình làm gì |
| **Developing** | Giải được một phần, hiểu một phần, còn phụ thuộc AI hoặc thử-sai |
| **Strong** | Giải được, hiểu và giải thích được, làm việc với AI có kiểm soát |
| **Exceptional** | Giải gọn, lập luận rõ từ đầu, xử lý cả trường hợp đặc biệt, dùng AI như người hỗ trợ chứ không dựa dẫm |

## Mẹo khi chấm

- Mỗi lượt mất khoảng **4–6 phút**. 40 lượt nên chia thành **4–5 buổi**, mỗi buổi khoảng 45 phút; chấm liền mạch lâu quá dễ mệt và chấm ẩu.
- Phân vân giữa hai mức thì **chọn mức thấp hơn**, và ghi lý do vào ô ghi chú.
- Thấy dữ liệu lạ (lượt làm bài trống, code không liên quan đề) thì vẫn chấm, và ghi chú lại.
- Thấy lượt nào hiển thị lỗi (thiếu dữ liệu, chữ bị cắt) thì vẫn chấm và ghi chú lại.
