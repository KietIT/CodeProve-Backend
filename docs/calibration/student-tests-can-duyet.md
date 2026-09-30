# Duyệt câu mẫu: tab Tests (P2.3)

Ở 20 bài có tab Tests, học sinh tự viết test (loại, input, kết quả mong đợi, lý do). Sau khi nộp, hệ thống kiểm tra test nào đúng với lời giải chuẩn, test có đủ loại không, và bắt được bao nhiêu bản code có lỗi cài sẵn (3–5 bản mỗi bài). Dưới đây là 5 nhận xét mới trên trang Feedback.

**Cần duyệt:** (1) có đáng nói với học sinh không, (2) mức nghiêm trọng hợp lý không, (3) câu chữ dễ hiểu, đúng giọng không. Con số và loại test trong câu là ví dụ.

## `no_student_tests` · Cần cải thiện · Cao
*Xuất hiện khi: Junior/senior nộp bài mà không viết test nào (fresher không bị nhắc).*

- **Chuyện gì đã xảy ra:** Bạn nộp bài mà chưa viết test nào trong tab Tests.
- **Vì sao quan trọng:** Tự viết test là cách chính để biết code đúng ở những trường hợp đề không cho sẵn.
- **Cách cải thiện:** Viết ít nhất 3 test thuộc các loại khác nhau (thông thường, giá trị biên, tình huống đặc biệt) và kiểm tra từng test trước khi Submit.
- **Thử tiếp:** Thử bài CP-105 và viết ít nhất 3 test thuộc các loại khác nhau trước khi Submit.

## `invalid_tests` · Cần cải thiện · Vừa
*Xuất hiện khi: Có test mà kết quả mong đợi không khớp lời giải đúng.*

- **Chuyện gì đã xảy ra:** 2 test của bạn có kết quả mong đợi chưa đúng với đề.
- **Vì sao quan trọng:** Test có kết quả mong đợi sai sẽ báo lỗi nhầm hoặc bỏ sót lỗi thật.
- **Cách cải thiện:** Tự tính kết quả mong đợi từ đề, không chép từ output của code mình, rồi bấm kiểm tra từng test.
- **Thử tiếp:** Thử bài CP-105 và tự tính kết quả mong đợi từ đề cho mỗi test.

## `missing_test_categories` · Cần cải thiện · Thấp
*Xuất hiện khi: Các test hợp lệ chưa đủ loại mà bài có.*

- **Chuyện gì đã xảy ra:** Bộ test của bạn chưa có loại: tình huống đặc biệt.
- **Vì sao quan trọng:** Mỗi loại test bắt một kiểu lỗi khác nhau; thiếu loại nào thì lỗi kiểu đó dễ lọt qua.
- **Cách cải thiện:** Thêm ít nhất một test cho mỗi loại còn thiếu, dựa vào giới hạn và yêu cầu trong đề.
- **Thử tiếp:** Thử bài CP-105 và viết test đủ các loại trước khi Submit.

## `mutants_survived` · Cần cải thiện · Vừa
*Xuất hiện khi: Test hợp lệ chưa bắt được hết các bản code có lỗi cài sẵn.*

- **Chuyện gì đã xảy ra:** Bộ test của bạn chưa phát hiện 1/4 phiên bản code có lỗi cài sẵn.
- **Vì sao quan trọng:** Test tốt phải làm fail code sai; test chỉ kiểm tra trường hợp dễ thì lỗi tinh vi vẫn lọt.
- **Cách cải thiện:** Xem các loại lỗi mà test chưa bắt trong phần kết quả test, rồi viết test nhắm vào đúng chỗ đó.
- **Thử tiếp:** Thử bài CP-105 và viết test nhắm vào các giá trị biên và điều kiện dễ sai.

## `strong_tests` · Điểm mạnh
*Xuất hiện khi: Đủ test hợp lệ, đủ loại, bắt hết các bản code có lỗi cài sẵn.*

- **Chuyện gì đã xảy ra:** Bộ test của bạn hợp lệ, đủ các loại và bắt được mọi phiên bản code có lỗi cài sẵn.
- **Vì sao quan trọng:** Viết được bộ test như vậy là một kỹ năng quan trọng khi làm việc với code, kể cả code do AI viết.
- **Cách cải thiện:** Ở bài sau, thử viết test trước khi viết code.
- **Thử tiếp:** Thử bài CP-105 và viết bộ test đủ loại ở một bài khó hơn.

## Bảng góp ý

Người duyệt: ________

| Mã | Đáng nói? (C/K) | Mức hợp lý? (C/K) | Câu chữ ổn? (C/K) | Góp ý |
|---|---|---|---|---|
| `no_student_tests` | | | | |
| `invalid_tests` | | | | |
| `missing_test_categories` | | | | |
| `mutants_survived` | | | | |
| `strong_tests` | | | | |
