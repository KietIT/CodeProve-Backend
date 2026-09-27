# Duyệt phản hồi P1.5: 23 loại nhận xét và nội dung mẫu (bản sửa 2026-09-27)

Mỗi báo cáo hiện tối đa **3 điểm cần cải thiện** (mức nghiêm trọng cao trước) và **2 điểm mạnh**. Bản này đã sửa theo góp ý của Trung và Phát ở vòng 1 (xem `feedback-review-results-2026-09-27.md`): bỏ các câu khẳng định tuyệt đối, bỏ ví dụ chỉ hợp một loại bài, chỉ nói điều hệ thống quan sát được.

Câu **"Chuyện gì đã xảy ra"** do AI viết riêng cho lượt làm bài **chỉ với 4 mã** có ✍️ (dựa trên chính lời học sinh viết); các mã còn lại luôn dùng đúng câu mẫu dưới đây. Ba phần sau ("Vì sao quan trọng", "Cách cải thiện", "Thử tiếp") luôn là mẫu. Ví dụ đang gợi ý bài tiếp theo là CP-105; con số và tên test trong câu là ví dụ.

Khi đọc, ghi ý kiến vào cột cuối: **(1) loại nhận xét này có đáng nói với học sinh không, (2) mức nghiêm trọng có hợp lý không, (3) câu chữ có dễ hiểu, đúng giọng không.**


## Bảng tóm tắt

| Mã | Trục | Loại | Nghiêm trọng | Xuất hiện khi | Góp ý |
|---|---|---|---|---|---|
| `explain_missing` ✍️ | Thấu hiểu | Cần cải thiện | Cao | Explain-back mức 0 | |
| `explain_shallow` ✍️ | Thấu hiểu | Cần cải thiện | Vừa | Explain-back mức 1–2 (mơ hồ, hoặc chỉ nói làm gì) | |
| `explain_strong` | Thấu hiểu | Điểm mạnh | — | Explain-back mức 3 | |
| `no_hypothesis` | Giả thuyết | Cần cải thiện | Vừa | Không ghi giả thuyết | |
| `hypothesis_vague` ✍️ | Giả thuyết | Cần cải thiện | Thấp | Giả thuyết mức 1 | |
| `hypothesis_after_code` | Giả thuyết | Cần cải thiện | Thấp | Giả thuyết tốt nhưng ghi sau khi đã code | |
| `hypothesis_strong` | Giả thuyết | Điểm mạnh | — | Giả thuyết mức 3, ghi trước khi code | |
| `asked_for_solution` | Prompting | Cần cải thiện | Cao | Có câu hỏi xin Ciel viết lời giải | |
| `prompts_vague` ✍️ | Prompting | Cần cải thiện | Vừa | Câu hỏi Ciel mức 0–1 (không xin lời giải) | |
| `prompts_strong` | Prompting | Điểm mạnh | — | Câu hỏi Ciel mức 3 | |
| `pasted_ai_failing` | Kiểm chứng | Cần cải thiện | Cao | Dán nguyên code AI, nộp vẫn fail | |
| `pasted_ai_unchecked` | Kiểm chứng | Cần cải thiện | Vừa | Dán nguyên code AI, nộp pass | |
| `adapted_ai_code` | Kiểm chứng | Điểm mạnh | — | Dán rồi sửa code AI, nộp pass | |
| `questioned_ai_code` | Kiểm chứng | Điểm mạnh | — | Không dùng code AI và hỏi nghi ngờ đoạn đó | |
| `never_ran_tests` | Testing | Cần cải thiện | Cao | Nộp mà chưa chạy test lần nào | |
| `submitted_failing` | Testing | Cần cải thiện | Cao | Nộp khi còn test fail (bài implement) | |
| `hidden_edge_failed` | Testing | Cần cải thiện | Vừa | Test hiển thị pass, test ẩn fail | |
| `all_tests_passed` | Testing | Điểm mạnh | — | Pass toàn bộ test kể cả test ẩn | |
| `bug_not_fixed` | Debug | Cần cải thiện | Cao | Nộp khi còn test fail (bài debug) | |
| `partial_fix` | Debug | Cần cải thiện | Vừa | Bài debug: test hiển thị pass, test ẩn còn fail | |
| `trial_and_error` | Debug | Cần cải thiện | Vừa | Sửa được sau ≥ 4 lần chạy fail | |
| `quick_fix` | Debug | Điểm mạnh | — | Sửa được, tối đa 1 lần chạy fail | |
| `integrity_flags` | Chung | Cần cải thiện | Cao | Có dán từ ngoài hoặc rời trang (điểm bị giảm) | |

## Nội dung mẫu (tiếng Việt)

### `explain_missing` · Thấu hiểu · Cần cải thiện
*Xuất hiện khi: Explain-back mức 0.*

- **Chuyện gì đã xảy ra (AI viết riêng, đây là câu dự phòng):** Câu trả lời explain-back chưa cho thấy bạn hiểu lời giải đang nộp.
- **Vì sao quan trọng:** Giải thích được code mình nộp là một cách quan trọng để biết bạn thật sự hiểu nó, không chỉ chạy được.
- **Cách cải thiện:** Trả lời theo hai ý: code làm gì theo từng bước, và vì sao cách đó đúng.
- **Thử tiếp:** Thử bài CP-105 và tự viết 2–3 câu giải thích lời giải trước khi Submit.

### `explain_shallow` · Thấu hiểu · Cần cải thiện
*Xuất hiện khi: Explain-back mức 1–2 (mơ hồ, hoặc chỉ nói làm gì).*

- **Chuyện gì đã xảy ra (AI viết riêng, đây là câu dự phòng):** Bạn nói được code làm gì nhưng chưa nói rõ vì sao nó đúng.
- **Vì sao quan trọng:** Hiểu "vì sao" giúp bạn tự sửa khi đề thay đổi, thay vì nhớ cách làm.
- **Cách cải thiện:** Với mỗi bước chính, thêm một câu "vì sao": bước đó cần để làm gì, và nếu bỏ đi hoặc làm khác thì kết quả sai ở đâu.
- **Thử tiếp:** Thử bài CP-105 và trả lời thêm "vì sao" cho mỗi bước chính trong explain-back.

### `explain_strong` · Thấu hiểu · Điểm mạnh
*Xuất hiện khi: Explain-back mức 3.*

- **Chuyện gì đã xảy ra:** Bạn giải thích được cả cách làm lẫn lý do vì sao lời giải đúng.
- **Vì sao quan trọng:** Điều đó cho thấy bạn hiểu cách làm của mình, không chỉ làm cho code chạy được.
- **Cách cải thiện:** Giữ thói quen này; ở bài sau thử nói thêm vì sao bạn chọn cách này thay vì một cách khác.
- **Thử tiếp:** Thử bài CP-105 và so sánh lời giải với một cách làm khác khi giải thích.

### `no_hypothesis` · Giả thuyết · Cần cải thiện
*Xuất hiện khi: Không ghi giả thuyết.*

- **Chuyện gì đã xảy ra:** Bạn chưa ghi lại hướng giải (giả thuyết) trước khi code.
- **Vì sao quan trọng:** Ghi hướng giải trước có thể giúp phát hiện sai hướng sớm và bớt những lần chạy thử không cần thiết.
- **Cách cải thiện:** Trước khi code, ghi 1–2 câu: bạn định làm theo cách nào, và trường hợp nào trong đề cần cẩn thận.
- **Thử tiếp:** Thử bài CP-105 và ghi 1–2 câu hướng giải trước dòng code đầu tiên.

### `hypothesis_vague` · Giả thuyết · Cần cải thiện
*Xuất hiện khi: Giả thuyết mức 1.*

- **Chuyện gì đã xảy ra (AI viết riêng, đây là câu dự phòng):** Giả thuyết của bạn còn chung chung, chưa chỉ ra hướng giải cụ thể.
- **Vì sao quan trọng:** Giả thuyết hữu ích nhất khi nó định hướng được lời giải.
- **Cách cải thiện:** Nêu rõ bạn định dùng cấu trúc dữ liệu hoặc cách làm nào, và một trường hợp trong đề cần cẩn thận.
- **Thử tiếp:** Thử bài CP-105 và ghi giả thuyết nêu rõ cách làm và một trường hợp cần cẩn thận.

### `hypothesis_after_code` · Giả thuyết · Cần cải thiện
*Xuất hiện khi: Giả thuyết tốt nhưng ghi sau khi đã code.*

- **Chuyện gì đã xảy ra:** Bạn ghi giả thuyết sau khi đã bắt đầu viết code.
- **Vì sao quan trọng:** Ghi trước khi code giúp định hướng tốt hơn; ghi sau vẫn có ích để kiểm tra lại cách nghĩ.
- **Cách cải thiện:** Lần tới, ghi 1–2 câu hướng giải ngay sau khi đọc đề, trước khi gõ code.
- **Thử tiếp:** Thử bài CP-105 và ghi giả thuyết ngay sau khi đọc đề.

### `hypothesis_strong` · Giả thuyết · Điểm mạnh
*Xuất hiện khi: Giả thuyết mức 3, ghi trước khi code.*

- **Chuyện gì đã xảy ra:** Bạn ghi hướng giải và trường hợp cần cẩn thận trước khi code.
- **Vì sao quan trọng:** Lập kế hoạch trước có thể giúp bạn giải gọn hơn và ít phải sửa đi sửa lại.
- **Cách cải thiện:** Ở bài khó hơn, ghi thêm bạn sẽ kiểm tra hướng giải đó bằng test nào.
- **Thử tiếp:** Thử bài CP-105 và ghi hướng giải trước khi code.

### `asked_for_solution` · Prompting · Cần cải thiện
*Xuất hiện khi: Có câu hỏi xin Ciel viết lời giải.*

- **Chuyện gì đã xảy ra:** Bạn đã xin Ciel viết lời giải (2 lần).
- **Vì sao quan trọng:** Nhận lời giải sẵn làm giảm cơ hội tự luyện, và CodeProve đánh giá cách bạn tự giải quyết vấn đề.
- **Cách cải thiện:** Hỏi về chỗ đang vướng: bạn đã thử gì, kết quả sai thế nào, và xin gợi ý thay vì đáp án.
- **Thử tiếp:** Thử bài CP-105 và chỉ hỏi Ciel gợi ý cho đúng chỗ bạn đang vướng.

### `prompts_vague` · Prompting · Cần cải thiện
*Xuất hiện khi: Câu hỏi Ciel mức 0–1 (không xin lời giải).*

- **Chuyện gì đã xảy ra (AI viết riêng, đây là câu dự phòng):** Câu hỏi gửi Ciel còn ngắn và thiếu ngữ cảnh.
- **Vì sao quan trọng:** Câu hỏi mơ hồ thường nhận câu trả lời chung chung và tốn thêm lượt hỏi.
- **Cách cải thiện:** Nói rõ bạn đang vướng ở đâu và đã thử gì; nếu hỏi về lỗi, kèm input, kết quả mong đợi và kết quả thực tế.
- **Thử tiếp:** Thử bài CP-105 và nói rõ chỗ đang vướng và điều đã thử trong mỗi câu hỏi gửi Ciel.

### `prompts_strong` · Prompting · Điểm mạnh
*Xuất hiện khi: Câu hỏi Ciel mức 3.*

- **Chuyện gì đã xảy ra:** Câu hỏi gửi Ciel cụ thể và nói rõ bạn đã thử gì.
- **Vì sao quan trọng:** Đó là cách dùng trợ lý AI hiệu quả mà vẫn tự học được.
- **Cách cải thiện:** Giữ cách hỏi này khi gặp bài khó hơn.
- **Thử tiếp:** Thử bài CP-105 và giữ cách hỏi cụ thể này ở một bài khó hơn.

### `pasted_ai_failing` · Kiểm chứng · Cần cải thiện
*Xuất hiện khi: Dán nguyên code AI, nộp vẫn fail.*

- **Chuyện gì đã xảy ra:** Bạn dùng nguyên đoạn code Ciel đưa và bài vẫn fail khi Submit.
- **Vì sao quan trọng:** Code AI có thể sai; dùng mà chưa kiểm tra kỹ là một rủi ro lớn khi làm việc với AI.
- **Cách cải thiện:** Đọc từng dòng code AI trước khi nộp, chạy test ngay sau khi dán và sửa chỗ fail.
- **Thử tiếp:** Thử bài CP-105 và kiểm tra từng dòng code AI trước khi nộp.

### `pasted_ai_unchecked` · Kiểm chứng · Cần cải thiện
*Xuất hiện khi: Dán nguyên code AI, nộp pass.*

- **Chuyện gì đã xảy ra:** Bạn dùng nguyên đoạn code Ciel đưa; hệ thống chưa thấy dấu hiệu bạn đã kiểm tra hoặc điều chỉnh nó. Lần này code chạy đúng.
- **Vì sao quan trọng:** Lần sau code AI có thể có lỗi mà test hiển thị không bắt được.
- **Cách cải thiện:** Tự đọc hiểu code AI, chạy thêm một trường hợp biên phù hợp với đề, hoặc hỏi Ciel vì sao đoạn code đó đúng.
- **Thử tiếp:** Thử bài CP-105 và chạy thêm một trường hợp biên cho mỗi đoạn code AI bạn dùng.

### `adapted_ai_code` · Kiểm chứng · Điểm mạnh
*Xuất hiện khi: Dán rồi sửa code AI, nộp pass.*

- **Chuyện gì đã xảy ra:** Bạn sửa lại code Ciel đưa thay vì dùng nguyên, và bài pass.
- **Vì sao quan trọng:** Đọc và chỉnh code AI là một kỹ năng quan trọng khi làm việc cùng AI.
- **Cách cải thiện:** Tiếp tục kiểm tra code AI như vậy, nhất là ở các trường hợp biên.
- **Thử tiếp:** Thử bài CP-105 và tiếp tục kiểm tra kỹ code AI.

### `questioned_ai_code` · Kiểm chứng · Điểm mạnh
*Xuất hiện khi: Không dùng code AI và hỏi nghi ngờ đoạn đó.*

- **Chuyện gì đã xảy ra:** Bạn đặt câu hỏi nghi ngờ đoạn code Ciel đưa thay vì tin ngay.
- **Vì sao quan trọng:** Không tin ngay vào AI là thói quen tốt; test sẽ cho bạn câu trả lời chắc chắn hơn.
- **Cách cải thiện:** Giữ sự hoài nghi này và kiểm chứng bằng test cụ thể.
- **Thử tiếp:** Thử bài CP-105 và kiểm chứng nghi ngờ của bạn bằng một test cụ thể.

### `never_ran_tests` · Testing · Cần cải thiện
*Xuất hiện khi: Nộp mà chưa chạy test lần nào.*

- **Chuyện gì đã xảy ra:** Bạn Submit mà chưa chạy test lần nào.
- **Vì sao quan trọng:** Chạy test giúp bạn phát hiện lỗi trước khi nộp bài.
- **Cách cải thiện:** Chạy test hiển thị, rồi thử thêm ít nhất một trường hợp biên phù hợp với đề trước khi Submit.
- **Thử tiếp:** Thử bài CP-105 và chạy test ít nhất một lần trước khi Submit.

### `submitted_failing` · Testing · Cần cải thiện
*Xuất hiện khi: Nộp khi còn test fail (bài implement).*

- **Chuyện gì đã xảy ra:** Bạn Submit khi còn test fail: pass 5/8.
- **Vì sao quan trọng:** Nộp khi còn test fail nghĩa là lời giải chưa đúng với yêu cầu của đề.
- **Cách cải thiện:** Đọc từng test fail, so kết quả thực tế với mong đợi, sửa cho pass hết test hiển thị rồi mới Submit.
- **Thử tiếp:** Thử bài CP-105 và chỉ Submit khi mọi test hiển thị đã pass.

### `hidden_edge_failed` · Testing · Cần cải thiện
*Xuất hiện khi: Test hiển thị pass, test ẩn fail.*

- **Chuyện gì đã xảy ra:** Test hiển thị pass hết nhưng test ẩn nhóm giá trị biên và tình huống đặc biệt còn fail, gồm: “limit of one”, “clients are limited independently”.
- **Vì sao quan trọng:** Test ẩn kiểm tra các trường hợp ít thấy trong ví dụ của đề; code dùng thật cũng sẽ gặp chúng.
- **Cách cải thiện:** Trước khi Submit, đọc lại đề và liệt kê các tình huống ví dụ chưa có: giá trị ở giới hạn đề cho, input bất thường mà đề vẫn cho phép, các yêu cầu phụ; rồi tự chạy thử từng tình huống.
- **Thử tiếp:** Thử bài CP-105 và liệt kê các tình huống ví dụ chưa có trước khi Submit.

### `all_tests_passed` · Testing · Điểm mạnh
*Xuất hiện khi: Pass toàn bộ test kể cả test ẩn.*

- **Chuyện gì đã xảy ra:** Lời giải pass toàn bộ test, kể cả test ẩn.
- **Vì sao quan trọng:** Lời giải đã xử lý tốt các trường hợp mà bộ test kiểm tra.
- **Cách cải thiện:** Tự viết thêm test cho trường hợp khó nhất bạn nghĩ ra, để tìm những gì bộ test chưa có.
- **Thử tiếp:** Thử bài CP-105 và tự viết thêm một test cho trường hợp khó nhất.

### `bug_not_fixed` · Debug · Cần cải thiện
*Xuất hiện khi: Nộp khi còn test fail (bài debug).*

- **Chuyện gì đã xảy ra:** Lỗi chưa được sửa hết: khi Submit còn test fail (pass 3/7).
- **Vì sao quan trọng:** Tìm và sửa lỗi là kỹ năng cốt lõi khi làm việc với code, kể cả code do AI viết.
- **Cách cải thiện:** Chạy code, đọc từng test fail, so kết quả thực tế với mong đợi để khoanh vùng dòng lỗi; Submit khi mọi test hiển thị đã pass.
- **Thử tiếp:** Thử bài CP-105 và khoanh vùng lỗi bằng cách so kết quả thực tế với mong đợi.

### `partial_fix` · Debug · Cần cải thiện
*Xuất hiện khi: Bài debug: test hiển thị pass, test ẩn còn fail.*

- **Chuyện gì đã xảy ra:** Test hiển thị đã pass nhưng test ẩn nhóm tình huống đặc biệt còn fail, gồm: “window must not jump back”.
- **Vì sao quan trọng:** Một lỗi thường có các trường hợp tương tự; sửa xong cần kiểm tra cả chúng.
- **Cách cải thiện:** Sau khi sửa, tự chạy thêm các input gần với chỗ vừa sửa, nhất là giá trị ở giới hạn đề cho.
- **Thử tiếp:** Thử bài CP-105 và kiểm tra lại các input liên quan sau mỗi lần sửa lỗi.

### `trial_and_error` · Debug · Cần cải thiện
*Xuất hiện khi: Sửa được sau ≥ 4 lần chạy fail.*

- **Chuyện gì đã xảy ra:** Bạn sửa được lỗi sau 5 lần chạy fail.
- **Vì sao quan trọng:** Quá trình sửa cần khá nhiều lượt chạy; nêu giả thuyết trước mỗi lần chạy giúp mỗi lượt có mục đích rõ hơn.
- **Cách cải thiện:** Trước mỗi lần chạy, ghi ngắn bạn nghĩ lỗi nằm ở đâu và chỉ sửa chỗ đó.
- **Thử tiếp:** Thử bài CP-105 và nêu giả thuyết về lỗi trước mỗi lần chạy.

### `quick_fix` · Debug · Điểm mạnh
*Xuất hiện khi: Sửa được, tối đa 1 lần chạy fail.*

- **Chuyện gì đã xảy ra:** Bạn sửa lỗi hiệu quả với ít lượt chạy lại.
- **Vì sao quan trọng:** Sửa đúng chỗ sớm giúp tiết kiệm thời gian và giữ code gọn.
- **Cách cải thiện:** Ở bài khó hơn, ghi lại vì sao bạn nghĩ lỗi nằm ở đó trước khi sửa.
- **Thử tiếp:** Thử bài CP-105 và giữ cách làm này ở một bài debug khó hơn.

### `integrity_flags` · Chung · Cần cải thiện
*Xuất hiện khi: Có dán từ ngoài hoặc rời trang (điểm bị giảm).*

- **Chuyện gì đã xảy ra:** Hệ thống ghi nhận tín hiệu bất thường trong phiên làm bài (dán nội dung từ ngoài 2 lần), nên điểm các trục bị giảm.
- **Vì sao quan trọng:** CodeProve đánh giá cách bạn tự làm bài. Đây là tín hiệu hệ thống ghi nhận, không phải kết luận: có thể có lý do hợp lệ.
- **Cách cải thiện:** Nếu bạn nghĩ hệ thống ghi nhận nhầm, hãy liên hệ đội CodeProve để được xem lại. Lần sau, làm trọn bài trong editor và dùng Ciel ngay trên trang khi cần hỗ trợ.
- **Thử tiếp:** Thử bài CP-105 và làm trọn bài trong editor, dùng Ciel khi cần hỗ trợ.
