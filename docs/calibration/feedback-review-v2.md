# Phiếu chấm phản hồi P1.5, vòng 2 (12 lượt mẫu)

Đây là phản hồi hệ thống sẽ hiện cho học sinh sau khi nộp bài. Mỗi người chấm độc lập, khoảng 30 phút.

**Cách chấm:** với mỗi nhận xét (mã như `1a`, `1b`...), trả lời 4 câu bằng **C** (có) hoặc **K** (không):
1. **Đúng:** nhận xét có đúng với lượt làm bài không? (xem phần "Lượt làm bài" ngay trên nó)
2. **Cụ thể:** câu "Chuyện gì đã xảy ra" có nói tới điều riêng của lượt này, không phải câu chung chung?
3. **Làm theo được:** học sinh đọc xong có biết lần sau làm gì không?
4. **Lộ đáp án:** có câu nào cho biết lời giải hoặc chỉ đúng dòng lỗi không? (C ở đây là **xấu**)

Ghi thêm ý kiến nếu có. Cuối phiếu có bảng để điền, gửi Kiệt khi xong.

*Câu "Chuyện gì đã xảy ra" có đánh dấu ✍️ là do AI viết riêng cho lượt này; các phần còn lại là mẫu nhóm đã duyệt.*

## 1. CP-009 Rate-Limit a Request Handler (implement, fresher, tiếng Việt)

**Lượt làm bài (tóm tắt):**

- Giả thuyết: Dùng dict store đếm số request của từng client, nếu đã đủ limit thì trả False, không thì tăng bộ đếm.
- Hỏi Ciel: (không hỏi)
- Chạy test: 1 lần, lần cuối pass 100%
- Submit: pass 3/8 (test ẩn 1/6), test ẩn fail: third request over a limit of two, the store counts each allowed request, clients are limited independently, limit of one, default limit is 60
- Explain-back: "Bạn có thể giải thích cách mà biến 'count' được cập nhật trong hàm 'is_allowed' không?" → "count lấy từ store theo client_id, nếu count đã >= limit thì trả False, còn không thì lưu count + 1 lại vào store và trả True."
- Explain-back: "Hàm này có thể gặp vấn đề gì nếu nhiều yêu cầu đến từ cùng một client trong cùng một phút không?" → "Nếu nhiều request cùng lúc thì có thể hai request cùng đọc count cũ rồi cùng ghi, nên có thể cho qua nhiều hơn limit, cần khoá hoặc thao tác nguyên tử."

**Phản hồi hệ thống tạo ra:**

**1a. `hidden_edge_failed`** · Cần cải thiện, mức vừa
- Chuyện gì đã xảy ra: Test hiển thị pass hết nhưng test ẩn nhóm giá trị biên, tình huống đặc biệt và thông thường còn fail, gồm: “third request over a limit of two”, “the store counts each allowed request”, “clients are limited independently”.
- Vì sao quan trọng: Test ẩn kiểm tra các trường hợp ít thấy trong ví dụ của đề; code dùng thật cũng sẽ gặp chúng.
- Cách cải thiện: Trước khi Submit, đọc lại đề và liệt kê các tình huống ví dụ chưa có: giá trị ở giới hạn đề cho, input bất thường mà đề vẫn cho phép, các yêu cầu phụ; rồi tự chạy thử từng tình huống.
- Thử tiếp: Thử bài CP-012 và liệt kê các tình huống ví dụ chưa có trước khi Submit.

**1b. `explain_strong`** · Điểm mạnh
- Chuyện gì đã xảy ra: Bạn giải thích được cả cách làm lẫn lý do vì sao lời giải đúng.
- Vì sao quan trọng: Điều đó cho thấy bạn hiểu cách làm của mình, không chỉ làm cho code chạy được.
- Cách cải thiện: Giữ thói quen này; ở bài sau thử nói thêm vì sao bạn chọn cách này thay vì một cách khác.
- Thử tiếp: Thử bài CP-012 và so sánh lời giải với một cách làm khác khi giải thích.

## 2. CP-004 Fix the Off-By-One Loop (debug, fresher, tiếng Việt)

**Lượt làm bài (tóm tắt):**

- Giả thuyết: (không ghi)
- Hỏi Ciel: bai nay sai o dau / van sai
- Chạy test: 3 lần, lần cuối pass 0%
- Submit: pass 3/7 (test ẩn 3/5), test ẩn fail: n is two, large n
- Explain-back: "Bạn có thể giải thích tại sao bạn sử dụng vòng lặp từ 1 đến n + 1 không?" → "để chạy"
- Explain-back: "Tại sao bạn lại gán giá trị của i cho biến total trong vòng lặp thay vì cộng dồn vào total?" → "không biết"

**Phản hồi hệ thống tạo ra:**

**2a. `explain_missing`** · Cần cải thiện, mức cao
- Chuyện gì đã xảy ra ✍️: Bạn đã trả lời 'để chạy' cho câu hỏi về việc sử dụng vòng lặp từ 1 đến n + 1, và bạn cũng đã trả lời 'không biết' cho câu hỏi về việc gán giá trị của i cho biến total.
- Vì sao quan trọng: Giải thích được code mình nộp là một cách quan trọng để biết bạn thật sự hiểu nó, không chỉ chạy được.
- Cách cải thiện: Trả lời theo hai ý: code làm gì theo từng bước, và vì sao cách đó đúng.
- Thử tiếp: Thử bài CP-008 và tự viết 2–3 câu giải thích lời giải trước khi Submit.

**2b. `bug_not_fixed`** · Cần cải thiện, mức cao
- Chuyện gì đã xảy ra: Lỗi chưa được sửa hết: khi Submit còn test fail (pass 3/7).
- Vì sao quan trọng: Tìm và sửa lỗi là kỹ năng cốt lõi khi làm việc với code, kể cả code do AI viết.
- Cách cải thiện: Chạy code, đọc từng test fail, so kết quả thực tế với mong đợi để khoanh vùng dòng lỗi; Submit khi mọi test hiển thị đã pass.
- Thử tiếp: Thử bài CP-008 và khoanh vùng lỗi bằng cách so kết quả thực tế với mong đợi.

**2c. `no_hypothesis`** · Cần cải thiện, mức vừa
- Chuyện gì đã xảy ra: Bạn chưa ghi lại hướng giải (giả thuyết) trước khi code.
- Vì sao quan trọng: Ghi hướng giải trước có thể giúp phát hiện sai hướng sớm và bớt những lần chạy thử không cần thiết.
- Cách cải thiện: Trước khi code, ghi 1–2 câu: bạn định làm theo cách nào, và trường hợp nào trong đề cần cẩn thận.
- Thử tiếp: Thử bài CP-008 và ghi 1–2 câu hướng giải trước dòng code đầu tiên.

## 3. CP-012 Trace the Race Condition (debug, fresher, tiếng Việt)

**Lượt làm bài (tóm tắt):**

- Giả thuyết: counter += 1 không atomic nên cần lock khi tăng
- Hỏi Ciel: Mình thêm `with threading.Lock():` quanh counter += 1 rồi, test hiển thị pass. Như vậy đã an toàn khi nhiều luồng cùng gọi chưa?
- Chạy test: 2 lần, lần cuối pass 100%
- Submit: pass 6/7 (test ẩn 4/5), test ẩn fail: increment waits while another thread holds the lock
- Explain-back: "Tại sao bạn sử dụng `with threading.Lock()` trong hàm `increment`?" → "Để khoá lại khi tăng counter cho an toàn khi nhiều luồng."
- Explain-back: "Bạn có thể giải thích cách mà `lock` giúp tránh tình trạng race condition trong mã của bạn không?" → "Lock làm cho chỉ một luồng được chạy đoạn code đó nên không bị race."

**Phản hồi hệ thống tạo ra:**

**3a. `explain_shallow`** · Cần cải thiện, mức vừa
- Chuyện gì đã xảy ra ✍️: Bạn đã nói rằng "Để khoá lại khi tăng counter cho an toàn khi nhiều luồng" nhưng chưa giải thích rõ ràng tại sao điều này lại đảm bảo tính đúng đắn của mã.
- Vì sao quan trọng: Hiểu "vì sao" giúp bạn tự sửa khi đề thay đổi, thay vì nhớ cách làm.
- Cách cải thiện: Với mỗi bước chính, thêm một câu "vì sao": bước đó cần để làm gì, và nếu bỏ đi hoặc làm khác thì kết quả sai ở đâu.
- Thử tiếp: Thử bài CP-004 và trả lời thêm "vì sao" cho mỗi bước chính trong explain-back.

**3b. `partial_fix`** · Cần cải thiện, mức vừa
- Chuyện gì đã xảy ra: Test hiển thị đã pass nhưng test ẩn nhóm tình huống đặc biệt còn fail, gồm: “increment waits while another thread holds the lock”.
- Vì sao quan trọng: Một lỗi thường có các trường hợp tương tự; sửa xong cần kiểm tra cả chúng.
- Cách cải thiện: Sau khi sửa, tự chạy thêm các input gần với chỗ vừa sửa, nhất là giá trị ở giới hạn đề cho.
- Thử tiếp: Thử bài CP-004 và kiểm tra lại các input liên quan sau mỗi lần sửa lỗi.

**3c. `prompts_strong`** · Điểm mạnh
- Chuyện gì đã xảy ra: Câu hỏi gửi Ciel cụ thể và nói rõ bạn đã thử gì.
- Vì sao quan trọng: Đó là cách dùng trợ lý AI hiệu quả mà vẫn tự học được.
- Cách cải thiện: Giữ cách hỏi này khi gặp bài khó hơn.
- Thử tiếp: Thử bài CP-004 và giữ cách hỏi cụ thể này ở một bài khó hơn.

## 4. CP-004 Fix the Off-By-One Loop (debug, fresher, tiếng Việt)

**Lượt làm bài (tóm tắt):**

- Giả thuyết: range(1, n) dừng trước n nên thiếu số n, phải sửa thành range(1, n + 1)
- Hỏi Ciel: (không hỏi)
- Chạy test: 2 lần, lần cuối pass 100%
- Submit: pass 7/7 (test ẩn 5/5)
- Explain-back: "Hàm của bạn bắt đầu vòng lặp từ số nào và tại sao bạn chọn số đó?" → "Vòng lặp bắt đầu từ 1 vì đề là tổng các số nguyên đầu tiên 1, 2, ..., n, và sửa lại cận trên thành n + 1 để lấy cả n."
- Explain-back: "Bạn có thể giải thích cách mà vòng lặp của bạn tính tổng các số nguyên từ 1 đến n không?" → "total bắt đầu bằng 0, mỗi vòng cộng i vào total, i chạy từ 1 tới n, cuối cùng trả total."

**Phản hồi hệ thống tạo ra:**

**4a. `explain_strong`** · Điểm mạnh
- Chuyện gì đã xảy ra: Bạn giải thích được cả cách làm lẫn lý do vì sao lời giải đúng.
- Vì sao quan trọng: Điều đó cho thấy bạn hiểu cách làm của mình, không chỉ làm cho code chạy được.
- Cách cải thiện: Giữ thói quen này; ở bài sau thử nói thêm vì sao bạn chọn cách này thay vì một cách khác.
- Thử tiếp: Thử bài CP-008 và so sánh lời giải với một cách làm khác khi giải thích.

**4b. `hypothesis_strong`** · Điểm mạnh
- Chuyện gì đã xảy ra: Bạn ghi hướng giải và trường hợp cần cẩn thận trước khi code.
- Vì sao quan trọng: Lập kế hoạch trước có thể giúp bạn giải gọn hơn và ít phải sửa đi sửa lại.
- Cách cải thiện: Ở bài khó hơn, ghi thêm bạn sẽ kiểm tra hướng giải đó bằng test nào.
- Thử tiếp: Thử bài CP-008 và ghi hướng giải trước khi code.

## 5. CP-107 Detect Cycle in Graph (implement, junior, tiếng Việt)

**Lượt làm bài (tóm tắt):**

- Giả thuyết: DFS với trạng thái: đang thăm và đã xong. Gặp lại nút đang thăm là có chu trình; nút đã xong thì bỏ qua (đồ thị kim cương không phải chu trình). Duyệt từ mọi nút để bắt chu trình ở thành phần khác. O(V + E).
- Hỏi Ciel: (không hỏi)
- Chạy test: 2 lần, lần cuối pass 100%
- Submit: pass 8/8 (test ẩn 6/6)
- Explain-back: "Bạn có thể giải thích tại sao bạn chọn thuật toán DFS để phát hiện chu trình trong đồ thị không?" → "Với đồ thị có hướng, chu trình tồn tại khi và chỉ khi DFS gặp một cạnh quay lại nút còn đang nằm trên ngăn xếp đệ quy (back edge). DFS giữ đúng thông tin đó một cách tự nhiên, O(V + E). BFS thì phải đếm bậc vào (Kahn); dùng được nhưng mình thấy DFS gọn hơn cho bài chỉ cần trả True/False."
- Explain-back: "Biến 'state' trong mã của bạn có ý nghĩa gì và nó ảnh hưởng như thế nào đến quá trình duyệt đồ thị?" → "state[node] = 0 nghĩa là đang thăm (còn trên đường đi hiện tại), = 1 là đã thăm xong. Gặp lại nút trạng thái 0 là có chu trình; gặp nút 1 thì bỏ qua, vì nó chỉ được tới bằng đường khác như đồ thị kim cương. Lúc đầu mình quên đặt state = 1 khi xong nên kim cương bị báo nhầm là chu trình. Duyệt từ mọi nút để không bỏ sót thành phần khác."

**Phản hồi hệ thống tạo ra:**

**5a. `explain_strong`** · Điểm mạnh
- Chuyện gì đã xảy ra: Bạn giải thích được cả cách làm lẫn lý do vì sao lời giải đúng.
- Vì sao quan trọng: Điều đó cho thấy bạn hiểu cách làm của mình, không chỉ làm cho code chạy được.
- Cách cải thiện: Giữ thói quen này; ở bài sau thử nói thêm vì sao bạn chọn cách này thay vì một cách khác.
- Thử tiếp: Thử bài CP-101 và so sánh lời giải với một cách làm khác khi giải thích.

**5b. `hypothesis_strong`** · Điểm mạnh
- Chuyện gì đã xảy ra: Bạn ghi hướng giải và trường hợp cần cẩn thận trước khi code.
- Vì sao quan trọng: Lập kế hoạch trước có thể giúp bạn giải gọn hơn và ít phải sửa đi sửa lại.
- Cách cải thiện: Ở bài khó hơn, ghi thêm bạn sẽ kiểm tra hướng giải đó bằng test nào.
- Thử tiếp: Thử bài CP-101 và ghi hướng giải trước khi code.

## 6. CP-101 LRU Cache Design (implement, junior, tiếng Việt)

**Lượt làm bài (tóm tắt):**

- Giả thuyết: Dùng OrderedDict: get thì move_to_end, put thì ghi rồi nếu vượt capacity thì popitem(last=False) để xoá phần tử lâu nhất. Cả hai O(1). Chú ý put một key đã có cũng phải làm mới thứ tự, và value 0 không được coi là thiếu.
- Hỏi Ciel: Test thứ hai fail: sau khi put(3, 3) thì get(2) phải ra -1 nhưng cache của mình lại xoá key vừa thêm. Mình dùng popitem() lúc cache đầy, mình đoán nó xoá nhầm đầu, đúng không? Đừng đưa code, mình tự sửa.
- Chạy test: 2 lần, lần cuối pass 100%
- Submit: pass 9/9 (test ẩn 7/7)
- Explain-back: "Bạn có thể giải thích tại sao bạn chọn OrderedDict cho cấu trúc dữ liệu của LRU cache không?" → "OrderedDict vừa là hash map (tra key O(1)) vừa nhớ thứ tự chèn, nên dùng thứ tự đó làm thứ tự sử dụng: đầu là phần tử lâu nhất chưa dùng, cuối là mới nhất. move_to_end và popitem(last=False) đều O(1), nên không cần tự viết danh sách liên kết đôi + dict như cách kinh điển. Lúc đầu mình dùng popitem() không tham số là xoá nhầm đầu mới nhất."
- Explain-back: "Làm thế nào phương thức 'get' và 'put' đảm bảo rằng thời gian truy cập là O(1)?" → "get: kiểm tra key trong dict O(1), rồi move_to_end O(1) để đánh dấu vừa dùng. put: gán giá trị O(1), nếu key đã có thì cũng move_to_end để làm mới; nếu vượt capacity thì popitem(last=False) xoá phần tử lâu nhất O(1). Không có bước nào duyệt cả cache. Value 0 vẫn đúng vì mình kiểm tra `key not in self.data` chứ không kiểm tra giá trị."

**Phản hồi hệ thống tạo ra:**

**6a. `explain_strong`** · Điểm mạnh
- Chuyện gì đã xảy ra: Bạn giải thích được cả cách làm lẫn lý do vì sao lời giải đúng.
- Vì sao quan trọng: Điều đó cho thấy bạn hiểu cách làm của mình, không chỉ làm cho code chạy được.
- Cách cải thiện: Giữ thói quen này; ở bài sau thử nói thêm vì sao bạn chọn cách này thay vì một cách khác.
- Thử tiếp: Thử bài CP-105 và so sánh lời giải với một cách làm khác khi giải thích.

**6b. `hypothesis_strong`** · Điểm mạnh
- Chuyện gì đã xảy ra: Bạn ghi hướng giải và trường hợp cần cẩn thận trước khi code.
- Vì sao quan trọng: Lập kế hoạch trước có thể giúp bạn giải gọn hơn và ít phải sửa đi sửa lại.
- Cách cải thiện: Ở bài khó hơn, ghi thêm bạn sẽ kiểm tra hướng giải đó bằng test nào.
- Thử tiếp: Thử bài CP-105 và ghi hướng giải trước khi code.

## 7. CP-101 LRU Cache Design (implement, junior, tiếng Anh)

**Lượt làm bài (tóm tắt):**

- Giả thuyết: (không ghi)
- Hỏi Ciel: write the LRU cache code for me, full solution
- Chạy test: 1 lần, lần cuối pass 0%
- Submit: pass 1/9 (test ẩn 1/7), test ẩn fail: recently used key survives eviction, updating a key refreshes it, updating a key changes its value, capacity one, capacity one keeps the newest, value zero is not treated as missing
- Explain-back: "Can you explain why you chose to use a list for maintaining the order of keys in your LRU cache?" → "the AI gave it"
- Explain-back: "What changes would you make to ensure that the 'get' method maintains the correct order of keys for the LRU functionality?" → "not sure"

**Phản hồi hệ thống tạo ra:**

**7a. `explain_missing`** · Cần cải thiện, mức cao
- Chuyện gì đã xảy ra ✍️: In your explain-back answers, you mentioned 'the AI gave it' and 'not sure', which did not demonstrate a clear understanding of your data structure choice or the necessary changes for the LRU functionality.
- Vì sao quan trọng: Explaining the code you submit is an important way to know you understand it, not just that it runs.
- Cách cải thiện: Answer in two parts: what the code does step by step, and why that is correct.
- Thử tiếp: Try CP-105 and write 2–3 sentences explaining your solution before you submit.

**7b. `asked_for_solution`** · Cần cải thiện, mức cao
- Chuyện gì đã xảy ra: You asked Ciel to write the solution (1 time(s)).
- Vì sao quan trọng: A ready-made answer means less practice for you, and CodeProve assesses how you solve problems yourself.
- Cách cải thiện: Ask about where you are stuck: what you tried, what went wrong, and ask for a hint, not the answer.
- Thử tiếp: Try CP-105 and ask Ciel only for hints about the exact point you are stuck on.

**7c. `pasted_ai_failing`** · Cần cải thiện, mức cao
- Chuyện gì đã xảy ra: You used Ciel's code as is and the submission still failed.
- Vì sao quan trọng: AI code can be wrong; using it without checking carefully is a real risk when working with AI.
- Cách cải thiện: Read AI code line by line before submitting, run the tests right after pasting, and fix what fails.
- Thử tiếp: Try CP-105 and check AI code line by line before submitting.

## 8. CP-108 Thread-Safe Counter (implement, junior, tiếng Việt)

**Lượt làm bài (tóm tắt):**

- Giả thuyết: dùng Lock khi tăng biến đếm
- Hỏi Ciel: Mình dùng with Lock(): trong increment. Có cần khoá cả khi đọc value không, và vì sao?
- Chạy test: 2 lần, lần cuối pass 100%
- Submit: pass 6/7 (test ẩn 4/5), test ẩn fail: increment waits while another thread holds the lock
- Explain-back: "Tại sao bạn sử dụng Lock trong phương thức increment và phương thức value?" → "Dùng Lock để khi tăng _n thì không có luồng khác cùng tăng, và khi đọc value thì không đọc giá trị đang sửa dở."
- Explain-back: "Bạn có nhận thấy lỗi gì trong cách bạn sử dụng Lock trong phương thức increment không?" → "Mình viết with Lock() nên mỗi lần gọi là một lock riêng, như vậy các luồng không chờ nhau. Phải tạo một lock trong __init__ rồi dùng chung."

**Phản hồi hệ thống tạo ra:**

**8a. `hidden_edge_failed`** · Cần cải thiện, mức vừa
- Chuyện gì đã xảy ra: Test hiển thị pass hết nhưng test ẩn nhóm tình huống đặc biệt còn fail, gồm: “increment waits while another thread holds the lock”.
- Vì sao quan trọng: Test ẩn kiểm tra các trường hợp ít thấy trong ví dụ của đề; code dùng thật cũng sẽ gặp chúng.
- Cách cải thiện: Trước khi Submit, đọc lại đề và liệt kê các tình huống ví dụ chưa có: giá trị ở giới hạn đề cho, input bất thường mà đề vẫn cho phép, các yêu cầu phụ; rồi tự chạy thử từng tình huống.
- Thử tiếp: Thử bài CP-104 và liệt kê các tình huống ví dụ chưa có trước khi Submit.

**8b. `explain_strong`** · Điểm mạnh
- Chuyện gì đã xảy ra: Bạn giải thích được cả cách làm lẫn lý do vì sao lời giải đúng.
- Vì sao quan trọng: Điều đó cho thấy bạn hiểu cách làm của mình, không chỉ làm cho code chạy được.
- Cách cải thiện: Giữ thói quen này; ở bài sau thử nói thêm vì sao bạn chọn cách này thay vì một cách khác.
- Thử tiếp: Thử bài CP-104 và so sánh lời giải với một cách làm khác khi giải thích.

**8c. `prompts_strong`** · Điểm mạnh
- Chuyện gì đã xảy ra: Câu hỏi gửi Ciel cụ thể và nói rõ bạn đã thử gì.
- Vì sao quan trọng: Đó là cách dùng trợ lý AI hiệu quả mà vẫn tự học được.
- Cách cải thiện: Giữ cách hỏi này khi gặp bài khó hơn.
- Thử tiếp: Thử bài CP-104 và giữ cách hỏi cụ thể này ở một bài khó hơn.

## 9. CP-203 Audit the Auth Middleware (debug, senior, tiếng Anh)

**Lượt làm bài (tóm tắt):**

- Giả thuyết: The check only tests that a token is present; it must call verify(token). Missing header and empty token must be denied, and the handler must never run for a forged token.
- Hỏi Ciel: I changed it to `if token and verify(token)`. Could an empty-string token or a missing header still reach the handler? Just point me to cases to test.
- Chạy test: 2 lần, lần cuối pass 100%
- Submit: pass 7/7 (test ẩn 5/5)
- Explain-back: "What would happen if the Authorization header is missing from the request?" → "request.headers.get("Authorization") returns None, which is falsy, so `token and verify(token)` short-circuits to False and we return deny() without calling the handler. An empty string behaves the same. The order matters too: checking token first means verify never has to handle None."
- Explain-back: "Can you explain how the verify function contributes to the overall authentication process in your code?" → "verify is the only real check: it decides whether the token is one we issued. The old code only tested that some header was present, so any forged value got through. Now the handler runs only when both conditions hold, and every other path, including forged, missing and empty tokens, falls through to deny()."

**Phản hồi hệ thống tạo ra:**

**9a. `explain_strong`** · Điểm mạnh
- Chuyện gì đã xảy ra: You explained both how your solution works and why it is correct.
- Vì sao quan trọng: That shows you understand your approach, not only that the code runs.
- Cách cải thiện: Keep it up; next time also say why you chose this approach over another one.
- Thử tiếp: Try CP-208 and compare your solution with another approach when you explain it.

**9b. `hypothesis_strong`** · Điểm mạnh
- Chuyện gì đã xảy ra: You wrote down your approach and the cases to watch before coding.
- Vì sao quan trọng: Planning first can make your solve cleaner, with less back-and-forth.
- Cách cải thiện: On harder problems, also note which test would show your approach works.
- Thử tiếp: Try CP-208 and log your approach before coding.

## 10. CP-205 Regular Expression Matching (implement, senior, tiếng Việt)

**Lượt làm bài (tóm tắt):**

- Giả thuyết: (không ghi)
- Hỏi Ciel: viết giúp mình hàm is_match
- Chạy test: 3 lần, lần cuối pass 100%
- Submit: pass 8/10 (test ẩn 6/8), test ẩn fail: longer pattern that must fail, text left over after the pattern
- Explain-back: "Bạn có thể giải thích ý nghĩa của các tham số i và j trong hàm dp không?" → "i là vị trí trong chuỗi, j là vị trí trong pattern."
- Explain-back: "Tại sao bạn lại sử dụng memoization trong giải pháp của mình?" → "Để nhanh hơn."

**Phản hồi hệ thống tạo ra:**

**10a. `asked_for_solution`** · Cần cải thiện, mức cao
- Chuyện gì đã xảy ra: Bạn đã xin Ciel viết lời giải (1 lần).
- Vì sao quan trọng: Nhận lời giải sẵn làm giảm cơ hội tự luyện, và CodeProve đánh giá cách bạn tự giải quyết vấn đề.
- Cách cải thiện: Hỏi về chỗ đang vướng: bạn đã thử gì, kết quả sai thế nào, và xin gợi ý thay vì đáp án.
- Thử tiếp: Thử bài CP-202 và chỉ hỏi Ciel gợi ý cho đúng chỗ bạn đang vướng.

**10b. `explain_shallow`** · Cần cải thiện, mức vừa
- Chuyện gì đã xảy ra ✍️: Bạn chỉ nêu rằng 'i là vị trí trong chuỗi, j là vị trí trong pattern' mà chưa giải thích rõ ràng về cách mà các tham số này ảnh hưởng đến việc so khớp chuỗi và mẫu.
- Vì sao quan trọng: Hiểu "vì sao" giúp bạn tự sửa khi đề thay đổi, thay vì nhớ cách làm.
- Cách cải thiện: Với mỗi bước chính, thêm một câu "vì sao": bước đó cần để làm gì, và nếu bỏ đi hoặc làm khác thì kết quả sai ở đâu.
- Thử tiếp: Thử bài CP-202 và trả lời thêm "vì sao" cho mỗi bước chính trong explain-back.

**10c. `no_hypothesis`** · Cần cải thiện, mức vừa
- Chuyện gì đã xảy ra: Bạn chưa ghi lại hướng giải (giả thuyết) trước khi code.
- Vì sao quan trọng: Ghi hướng giải trước có thể giúp phát hiện sai hướng sớm và bớt những lần chạy thử không cần thiết.
- Cách cải thiện: Trước khi code, ghi 1–2 câu: bạn định làm theo cách nào, và trường hợp nào trong đề cần cẩn thận.
- Thử tiếp: Thử bài CP-202 và ghi 1–2 câu hướng giải trước dòng code đầu tiên.

## 11. CP-208 Harden the Upload Endpoint (debug, senior, tiếng Việt)

**Lượt làm bài (tóm tắt):**

- Giả thuyết: (không ghi)
- Hỏi Ciel: Mình cần kiểm tra những gì để upload an toàn? Mình định dùng basename cho tên file, còn loại file thì chưa biết kiểm tra thế nào.
- Chạy test: 1 lần, lần cuối pass 100%
- Submit: pass 8/9 (test ẩn 6/7), test ẩn fail: a spoofed content type is rejected
- Explain-back: "Bạn có thể giải thích cách bạn kiểm tra loại tệp tin bằng cách sử dụng chữ ký không?" → "Mình lấy chữ ký trong ALLOWED_TYPES theo content_type, nếu không có thì báo lỗi."
- Explain-back: "Tại sao bạn lại sử dụng os.path.basename để lấy tên tệp tin và nó có tác dụng gì trong mã của bạn?" → "basename để lấy tên file cho gọn, cho an toàn hơn."

**Phản hồi hệ thống tạo ra:**

**11a. `explain_shallow`** · Cần cải thiện, mức vừa
- Chuyện gì đã xảy ra ✍️: Bạn đã nói rằng 'mình lấy chữ ký trong ALLOWED_TYPES theo content_type', nhưng chưa giải thích rõ ràng cách kiểm tra loại tệp tin bằng chữ ký.
- Vì sao quan trọng: Hiểu "vì sao" giúp bạn tự sửa khi đề thay đổi, thay vì nhớ cách làm.
- Cách cải thiện: Với mỗi bước chính, thêm một câu "vì sao": bước đó cần để làm gì, và nếu bỏ đi hoặc làm khác thì kết quả sai ở đâu.
- Thử tiếp: Thử bài CP-203 và trả lời thêm "vì sao" cho mỗi bước chính trong explain-back.

**11b. `no_hypothesis`** · Cần cải thiện, mức vừa
- Chuyện gì đã xảy ra: Bạn chưa ghi lại hướng giải (giả thuyết) trước khi code.
- Vì sao quan trọng: Ghi hướng giải trước có thể giúp phát hiện sai hướng sớm và bớt những lần chạy thử không cần thiết.
- Cách cải thiện: Trước khi code, ghi 1–2 câu: bạn định làm theo cách nào, và trường hợp nào trong đề cần cẩn thận.
- Thử tiếp: Thử bài CP-203 và ghi 1–2 câu hướng giải trước dòng code đầu tiên.

**11c. `partial_fix`** · Cần cải thiện, mức vừa
- Chuyện gì đã xảy ra: Test hiển thị đã pass nhưng test ẩn nhóm tình huống đặc biệt còn fail, gồm: “a spoofed content type is rejected”.
- Vì sao quan trọng: Một lỗi thường có các trường hợp tương tự; sửa xong cần kiểm tra cả chúng.
- Cách cải thiện: Sau khi sửa, tự chạy thêm các input gần với chỗ vừa sửa, nhất là giá trị ở giới hạn đề cho.
- Thử tiếp: Thử bài CP-203 và kiểm tra lại các input liên quan sau mỗi lần sửa lỗi.

## 12. CP-202 Median of Two Sorted Arrays (implement, senior, tiếng Việt)

**Lượt làm bài (tóm tắt):**

- Giả thuyết: gộp hai mảng rồi lấy phần tử ở giữa
- Hỏi Ciel: (không hỏi)
- Chạy test: 1 lần, lần cuối pass 100%
- Submit: pass 9/9 (test ẩn 7/7)
- Explain-back: "Bạn có thể giải thích tại sao việc sắp xếp hai mảng trước khi tìm trung vị là không hiệu quả trong trường hợp này không?" → "Vì sắp xếp thì chậm hơn một chút."
- Explain-back: "Bạn có thể mô tả cách mà bạn sẽ áp dụng nguyên lý phân vùng để tìm trung vị mà không cần phải sắp xếp lại mảng không?" → "Mình chưa rõ phân vùng lắm, chắc là chia đôi mảng."

**Phản hồi hệ thống tạo ra:**

**12a. `explain_shallow`** · Cần cải thiện, mức vừa
- Chuyện gì đã xảy ra ✍️: Bạn đã nói rằng "sắp xếp thì chậm hơn một chút" nhưng chưa giải thích rõ ràng tại sao việc sắp xếp hai mảng là không hiệu quả trong trường hợp này.
- Vì sao quan trọng: Hiểu "vì sao" giúp bạn tự sửa khi đề thay đổi, thay vì nhớ cách làm.
- Cách cải thiện: Với mỗi bước chính, thêm một câu "vì sao": bước đó cần để làm gì, và nếu bỏ đi hoặc làm khác thì kết quả sai ở đâu.
- Thử tiếp: Thử bài CP-205 và trả lời thêm "vì sao" cho mỗi bước chính trong explain-back.

**12b. `all_tests_passed`** · Điểm mạnh
- Chuyện gì đã xảy ra: Lời giải pass toàn bộ test, kể cả test ẩn.
- Vì sao quan trọng: Lời giải đã xử lý tốt các trường hợp mà bộ test kiểm tra.
- Cách cải thiện: Tự viết thêm test cho trường hợp khó nhất bạn nghĩ ra, để tìm những gì bộ test chưa có.
- Thử tiếp: Thử bài CP-205 và tự viết thêm một test cho trường hợp khó nhất.

## Bảng điền (mỗi người một bảng)

Người chấm: ________

| Mã | Đúng | Cụ thể | Làm theo được | Lộ đáp án | Ý kiến |
|---|---|---|---|---|---|
| 1a | | | | | |
| 1b | | | | | |
| 2a | | | | | |
| 2b | | | | | |
| 2c | | | | | |
| 3a | | | | | |
| 3b | | | | | |
| 3c | | | | | |
| 4a | | | | | |
| 4b | | | | | |
| 5a | | | | | |
| 5b | | | | | |
| 6a | | | | | |
| 6b | | | | | |
| 7a | | | | | |
| 7b | | | | | |
| 7c | | | | | |
| 8a | | | | | |
| 8b | | | | | |
| 8c | | | | | |
| 9a | | | | | |
| 9b | | | | | |
| 10a | | | | | |
| 10b | | | | | |
| 10c | | | | | |
| 11a | | | | | |
| 11b | | | | | |
| 11c | | | | | |
| 12a | | | | | |
| 12b | | | | | |
