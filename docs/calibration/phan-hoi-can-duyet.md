# Duyệt phản hồi P1.5: 23 loại nhận xét và nội dung mẫu

Mỗi báo cáo hiện tối đa **3 điểm cần cải thiện** (mức nghiêm trọng cao trước) và **2 điểm mạnh**. Nội dung dưới đây là **mẫu dự phòng** (dùng khi LLM lỗi) và cũng là giọng văn LLM bắt chước. Ví dụ đang gợi ý bài tiếp theo là CP-105; con số trong ngoặc là ví dụ.

Khi đọc, mỗi người ghi ý kiến vào cột cuối hoặc nhắn Kiệt: **(1) loại nhận xét này có đáng nói với học sinh không, (2) mức nghiêm trọng có hợp lý không, (3) câu chữ có dễ hiểu, đúng giọng không.**

## Bảng tóm tắt

| Mã | Trục | Loại | Nghiêm trọng | Xuất hiện khi | Góp ý |
|---|---|---|---|---|---|
| `explain_missing` | Thấu hiểu | Cần cải thiện | Cao | Explain-back mức 0 | |
| `explain_shallow` | Thấu hiểu | Cần cải thiện | Vừa | Explain-back mức 1–2 (mơ hồ, hoặc chỉ nói làm gì) | |
| `explain_strong` | Thấu hiểu | Điểm mạnh | — | Explain-back mức 3 | |
| `no_hypothesis` | Giả thuyết | Cần cải thiện | Vừa | Không ghi giả thuyết | |
| `hypothesis_vague` | Giả thuyết | Cần cải thiện | Thấp | Giả thuyết mức 1 | |
| `hypothesis_after_code` | Giả thuyết | Cần cải thiện | Thấp | Giả thuyết tốt nhưng ghi sau khi đã code | |
| `hypothesis_strong` | Giả thuyết | Điểm mạnh | — | Giả thuyết mức 3, ghi trước khi code | |
| `asked_for_solution` | Prompting | Cần cải thiện | Cao | Có câu hỏi xin Ciel viết lời giải | |
| `prompts_vague` | Prompting | Cần cải thiện | Vừa | Câu hỏi Ciel mức 0–1 (không xin lời giải) | |
| `prompts_strong` | Prompting | Điểm mạnh | — | Câu hỏi Ciel mức 3 | |
| `pasted_ai_failing` | Kiểm chứng | Cần cải thiện | Cao | Dán nguyên code AI, nộp vẫn fail | |
| `pasted_ai_unchecked` | Kiểm chứng | Cần cải thiện | Vừa | Dán nguyên code AI, nộp pass | |
| `adapted_ai_code` | Kiểm chứng | Điểm mạnh | — | Dán rồi sửa code AI, nộp pass | |
| `questioned_ai_code` | Kiểm chứng | Điểm mạnh | — | Không dùng code AI và hỏi nghi ngờ đoạn đó | |
| `never_ran_tests` | Testing | Cần cải thiện | Cao | Nộp mà chưa chạy test lần nào | |
| `submitted_failing` | Testing | Cần cải thiện | Cao | Nộp khi còn test hiển thị fail | |
| `hidden_edge_failed` | Testing | Cần cải thiện | Vừa | Test hiển thị pass, test ẩn fail | |
| `all_tests_passed` | Testing | Điểm mạnh | — | Pass toàn bộ test kể cả test ẩn | |
| `bug_not_fixed` | Debug | Cần cải thiện | Cao | Chưa sửa được lỗi (còn test hiển thị fail) | |
| `partial_fix` | Debug | Cần cải thiện | Vừa | Sửa được lỗi thấy được, còn fail test ẩn | |
| `trial_and_error` | Debug | Cần cải thiện | Vừa | Sửa được sau ≥ 4 lần chạy fail | |
| `quick_fix` | Debug | Điểm mạnh | — | Sửa được, tối đa 1 lần chạy fail | |
| `integrity_flags` | Chung | Cần cải thiện | Cao | Có dán từ ngoài hoặc rời trang (điểm bị giảm) | |

## Nội dung mẫu (tiếng Việt)

### `explain_missing` · Thấu hiểu · Cần cải thiện
*Xuất hiện khi: Explain-back mức 0.*

- **Chuyện gì đã xảy ra:** Câu trả lời explain-back chưa cho thấy bạn hiểu lời giải của mình.
- **Vì sao quan trọng:** Giải thích được code của chính mình là cách chắc chắn nhất để biết bạn thật sự hiểu, không chỉ chạy được.
- **Cách cải thiện:** Trả lời theo hai ý: code làm gì theo từng bước, và vì sao cách đó đúng.
- **Thử tiếp:** Thử bài CP-105 và tự viết 2–3 câu giải thích lời giải trước khi Submit.

### `explain_shallow` · Thấu hiểu · Cần cải thiện
*Xuất hiện khi: Explain-back mức 1–2 (mơ hồ, hoặc chỉ nói làm gì).*

- **Chuyện gì đã xảy ra:** Bạn nói được code làm gì nhưng chưa nói rõ vì sao nó đúng.
- **Vì sao quan trọng:** Hiểu "vì sao" giúp bạn tự sửa khi đề thay đổi, thay vì nhớ cách làm.
- **Cách cải thiện:** Thêm lý do và một trường hợp đặc biệt, ví dụ: vì sao vòng lặp dừng ở đó, input rỗng thì sao.
- **Thử tiếp:** Thử bài CP-105 và giải thích thêm một trường hợp đặc biệt trong câu trả lời explain-back.

### `explain_strong` · Thấu hiểu · Điểm mạnh
*Xuất hiện khi: Explain-back mức 3.*

- **Chuyện gì đã xảy ra:** Bạn giải thích được cả cách làm lẫn lý do, kèm trường hợp đặc biệt.
- **Vì sao quan trọng:** Đó là dấu hiệu rõ nhất của việc hiểu thật, không phụ thuộc vào AI.
- **Cách cải thiện:** Giữ thói quen này và thử nói thêm về độ phức tạp thời gian.
- **Thử tiếp:** Thử bài CP-105 và thử giải thích cả độ phức tạp của lời giải.

### `no_hypothesis` · Giả thuyết · Cần cải thiện
*Xuất hiện khi: Không ghi giả thuyết.*

- **Chuyện gì đã xảy ra:** Bạn bắt đầu viết code mà không ghi giả thuyết.
- **Vì sao quan trọng:** Nêu hướng giải trước giúp phát hiện sai hướng sớm và bớt những lần chạy thử vô ích.
- **Cách cải thiện:** Trước khi code, ghi 1–2 câu: dùng cấu trúc hay thuật toán gì, trường hợp nào cần cẩn thận.
- **Thử tiếp:** Thử bài CP-105 và ghi giả thuyết trước dòng code đầu tiên.

### `hypothesis_vague` · Giả thuyết · Cần cải thiện
*Xuất hiện khi: Giả thuyết mức 1.*

- **Chuyện gì đã xảy ra:** Giả thuyết của bạn còn chung chung, chưa chỉ ra hướng giải cụ thể.
- **Vì sao quan trọng:** Giả thuyết chỉ hữu ích khi nó định hướng được lời giải.
- **Cách cải thiện:** Nêu tên cách làm (ví dụ: dict lưu phần bù, hai con trỏ) và một trường hợp cần cẩn thận.
- **Thử tiếp:** Thử bài CP-105 và ghi giả thuyết có nêu rõ cấu trúc dữ liệu và một trường hợp biên.

### `hypothesis_after_code` · Giả thuyết · Cần cải thiện
*Xuất hiện khi: Giả thuyết tốt nhưng ghi sau khi đã code.*

- **Chuyện gì đã xảy ra:** Bạn ghi giả thuyết sau khi đã bắt đầu viết code.
- **Vì sao quan trọng:** Giả thuyết có giá trị nhất khi dẫn đường cho code, không phải mô tả lại code đã viết.
- **Cách cải thiện:** Ghi giả thuyết ngay sau khi đọc đề, trước khi gõ code.
- **Thử tiếp:** Thử bài CP-105 và ghi giả thuyết ngay sau khi đọc đề.

### `hypothesis_strong` · Giả thuyết · Điểm mạnh
*Xuất hiện khi: Giả thuyết mức 3, ghi trước khi code.*

- **Chuyện gì đã xảy ra:** Bạn nêu đúng hướng giải và trường hợp cần cẩn thận ngay từ đầu.
- **Vì sao quan trọng:** Lập kế hoạch trước giúp bạn giải gọn và ít phải sửa đi sửa lại.
- **Cách cải thiện:** Tiếp tục giữ thói quen này ở các bài khó hơn.
- **Thử tiếp:** Thử bài CP-105 và giữ thói quen lập kế hoạch ở một bài khó hơn.

### `asked_for_solution` · Prompting · Cần cải thiện
*Xuất hiện khi: Có câu hỏi xin Ciel viết lời giải.*

- **Chuyện gì đã xảy ra:** Bạn đã xin Ciel viết lời giải (2 lần).
- **Vì sao quan trọng:** Nhận lời giải sẵn không rèn được kỹ năng, và CodeProve đánh giá cách bạn tự giải quyết vấn đề.
- **Cách cải thiện:** Hỏi về chỗ đang vướng: bạn đã thử gì, kết quả sai thế nào, và xin gợi ý thay vì đáp án.
- **Thử tiếp:** Thử bài CP-105 và chỉ hỏi Ciel gợi ý cho đúng chỗ bạn đang vướng.

### `prompts_vague` · Prompting · Cần cải thiện
*Xuất hiện khi: Câu hỏi Ciel mức 0–1 (không xin lời giải).*

- **Chuyện gì đã xảy ra:** Câu hỏi gửi Ciel còn ngắn và thiếu ngữ cảnh.
- **Vì sao quan trọng:** Câu hỏi mơ hồ nhận câu trả lời chung chung và tốn thêm lượt hỏi.
- **Cách cải thiện:** Nêu cụ thể: input nào, kết quả mong đợi, kết quả thực tế, và bạn đoán lỗi ở đâu.
- **Thử tiếp:** Thử bài CP-105 và viết mỗi câu hỏi cho Ciel kèm input, kết quả mong đợi và kết quả thực tế.

### `prompts_strong` · Prompting · Điểm mạnh
*Xuất hiện khi: Câu hỏi Ciel mức 3.*

- **Chuyện gì đã xảy ra:** Câu hỏi gửi Ciel cụ thể, nói rõ bạn đã thử gì và xin hướng dẫn thay vì đáp án.
- **Vì sao quan trọng:** Đó là cách dùng trợ lý AI hiệu quả mà vẫn tự học được.
- **Cách cải thiện:** Giữ cách hỏi này khi gặp bài khó hơn.
- **Thử tiếp:** Thử bài CP-105 và giữ cách hỏi cụ thể này ở một bài khó hơn.

### `pasted_ai_failing` · Kiểm chứng · Cần cải thiện
*Xuất hiện khi: Dán nguyên code AI, nộp vẫn fail.*

- **Chuyện gì đã xảy ra:** Bạn dùng nguyên đoạn code Ciel đưa và bài vẫn fail khi Submit.
- **Vì sao quan trọng:** Code AI có thể sai; dùng mà không kiểm tra là rủi ro lớn nhất khi làm việc với AI.
- **Cách cải thiện:** Đọc từng dòng code AI trước khi dùng, chạy test ngay sau khi dán và sửa chỗ fail.
- **Thử tiếp:** Thử bài CP-105 và kiểm tra từng dòng code AI trước khi dùng.

### `pasted_ai_unchecked` · Kiểm chứng · Cần cải thiện
*Xuất hiện khi: Dán nguyên code AI, nộp pass.*

- **Chuyện gì đã xảy ra:** Bạn dùng nguyên đoạn code Ciel đưa, không sửa hay kiểm tra thêm; lần này nó chạy đúng.
- **Vì sao quan trọng:** Lần sau code AI có thể có lỗi mà test hiển thị không bắt được.
- **Cách cải thiện:** Tự đọc hiểu code AI, thử thêm trường hợp biên, hoặc hỏi Ciel vì sao đoạn code đó đúng.
- **Thử tiếp:** Thử bài CP-105 và thử thêm một trường hợp biên cho mọi đoạn code AI bạn dùng.

### `adapted_ai_code` · Kiểm chứng · Điểm mạnh
*Xuất hiện khi: Dán rồi sửa code AI, nộp pass.*

- **Chuyện gì đã xảy ra:** Bạn sửa lại code Ciel đưa cho đúng thay vì dùng nguyên.
- **Vì sao quan trọng:** Đọc và chỉnh code AI là kỹ năng quan trọng nhất khi làm việc cùng AI.
- **Cách cải thiện:** Tiếp tục kiểm tra code AI như vậy, nhất là ở các trường hợp biên.
- **Thử tiếp:** Thử bài CP-105 và tiếp tục kiểm tra kỹ code AI.

### `questioned_ai_code` · Kiểm chứng · Điểm mạnh
*Xuất hiện khi: Không dùng code AI và hỏi nghi ngờ đoạn đó.*

- **Chuyện gì đã xảy ra:** Bạn đặt câu hỏi nghi ngờ đoạn code Ciel đưa thay vì tin ngay.
- **Vì sao quan trọng:** Không tin mù quáng vào AI là thói quen giúp bạn tránh lỗi tinh vi.
- **Cách cải thiện:** Giữ sự hoài nghi này và kiểm chứng bằng test cụ thể.
- **Thử tiếp:** Thử bài CP-105 và kiểm chứng nghi ngờ của bạn bằng một test cụ thể.

### `never_ran_tests` · Testing · Cần cải thiện
*Xuất hiện khi: Nộp mà chưa chạy test lần nào.*

- **Chuyện gì đã xảy ra:** Bạn Submit mà chưa chạy test lần nào.
- **Vì sao quan trọng:** Chạy test trước khi nộp giúp bắt lỗi khi vẫn còn sửa được.
- **Cách cải thiện:** Chạy test hiển thị, rồi tự thử thêm vài trường hợp biên trước khi Submit.
- **Thử tiếp:** Thử bài CP-105 và chạy test ít nhất một lần trước khi Submit.

### `submitted_failing` · Testing · Cần cải thiện
*Xuất hiện khi: Nộp khi còn test hiển thị fail.*

- **Chuyện gì đã xảy ra:** Bạn Submit khi còn test fail: pass 5/8.
- **Vì sao quan trọng:** Nộp khi còn test fail nghĩa là lời giải chưa đúng với yêu cầu của đề.
- **Cách cải thiện:** Đọc từng test fail, so kết quả thực tế với mong đợi, sửa cho pass hết test hiển thị rồi mới Submit.
- **Thử tiếp:** Thử bài CP-105 và chỉ Submit khi mọi test hiển thị đã pass.

### `hidden_edge_failed` · Testing · Cần cải thiện
*Xuất hiện khi: Test hiển thị pass, test ẩn fail.*

- **Chuyện gì đã xảy ra:** Test hiển thị pass hết nhưng test ẩn nhóm biên và đặc biệt còn fail.
- **Vì sao quan trọng:** Test ẩn kiểm tra các trường hợp đề không nêu rõ; code thật cũng gặp những trường hợp này.
- **Cách cải thiện:** Trước khi Submit, tự liệt kê trường hợp biên: rỗng, một phần tử, số âm, giá trị trùng, giới hạn lớn.
- **Thử tiếp:** Thử bài CP-105 và liệt kê các trường hợp biên trước khi Submit.

### `all_tests_passed` · Testing · Điểm mạnh
*Xuất hiện khi: Pass toàn bộ test kể cả test ẩn.*

- **Chuyện gì đã xảy ra:** Lời giải pass toàn bộ test, kể cả test ẩn.
- **Vì sao quan trọng:** Bạn đã xử lý được cả những trường hợp đề không nêu rõ.
- **Cách cải thiện:** Thử tự viết thêm test cho trường hợp khó nhất bạn nghĩ ra.
- **Thử tiếp:** Thử bài CP-105 và tự viết thêm một test cho trường hợp khó nhất.

### `bug_not_fixed` · Debug · Cần cải thiện
*Xuất hiện khi: Chưa sửa được lỗi (còn test hiển thị fail).*

- **Chuyện gì đã xảy ra:** Lỗi chưa được sửa: còn test hiển thị fail khi Submit.
- **Vì sao quan trọng:** Tìm và sửa lỗi là kỹ năng cốt lõi khi làm việc với code, kể cả code do AI viết.
- **Cách cải thiện:** Chạy code, đọc test fail, so kết quả thực tế với mong đợi để khoanh vùng dòng lỗi.
- **Thử tiếp:** Thử bài CP-105 và khoanh vùng lỗi bằng cách so kết quả thực tế với mong đợi.

### `partial_fix` · Debug · Cần cải thiện
*Xuất hiện khi: Sửa được lỗi thấy được, còn fail test ẩn.*

- **Chuyện gì đã xảy ra:** Bạn sửa được lỗi chính (test hiển thị pass) nhưng test ẩn nhóm đặc biệt còn fail.
- **Vì sao quan trọng:** Một lỗi thường kéo theo các trường hợp tương tự; sửa xong cần kiểm tra cả chúng.
- **Cách cải thiện:** Sau khi sửa, thử lại với các input biên liên quan đến chỗ vừa sửa.
- **Thử tiếp:** Thử bài CP-105 và thử lại các input biên liên quan sau mỗi lần sửa lỗi.

### `trial_and_error` · Debug · Cần cải thiện
*Xuất hiện khi: Sửa được sau ≥ 4 lần chạy fail.*

- **Chuyện gì đã xảy ra:** Bạn sửa được lỗi sau 5 lần chạy fail.
- **Vì sao quan trọng:** Thử-sai tốn thời gian và dễ sửa đúng mà không hiểu vì sao.
- **Cách cải thiện:** Trước mỗi lần chạy, nêu giả thuyết lỗi nằm ở đâu và chỉ sửa đúng chỗ đó.
- **Thử tiếp:** Thử bài CP-105 và nêu giả thuyết về lỗi trước mỗi lần chạy.

### `quick_fix` · Debug · Điểm mạnh
*Xuất hiện khi: Sửa được, tối đa 1 lần chạy fail.*

- **Chuyện gì đã xảy ra:** Bạn tìm đúng chỗ lỗi và sửa gọn, gần như không phải thử lại.
- **Vì sao quan trọng:** Đó là dấu hiệu bạn đọc và hiểu code trước khi sửa.
- **Cách cải thiện:** Giữ cách làm này ở các bài debug khó hơn.
- **Thử tiếp:** Thử bài CP-105 và giữ cách làm này ở một bài debug khó hơn.

### `integrity_flags` · Chung · Cần cải thiện
*Xuất hiện khi: Có dán từ ngoài hoặc rời trang (điểm bị giảm).*

- **Chuyện gì đã xảy ra:** Phiên làm bài có tín hiệu bất thường (dán nội dung từ ngoài hoặc rời trang), nên điểm các trục bị giảm.
- **Vì sao quan trọng:** CodeProve đánh giá cách bạn tự làm; nội dung đưa vào từ nơi khác không cho thấy kỹ năng của bạn.
- **Cách cải thiện:** Làm trọn bài trong editor và dùng Ciel ngay trên trang khi cần hỗ trợ.
- **Thử tiếp:** Thử bài CP-105 và làm trọn bài trong editor, dùng Ciel khi cần hỗ trợ.
