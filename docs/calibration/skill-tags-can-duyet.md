# Duyệt thẻ kỹ năng cho 30 bài (P3.2)

Mỗi bài được gắn 1–3 **thẻ kỹ năng**. Từ P3.3, hệ thống tính một điểm Elo cho *mỗi kỹ năng* của học sinh dựa trên kết quả các bài có thẻ đó, rồi dùng điểm này để gợi ý bài tiếp theo (P3.4) và cho Ciel biết học sinh còn yếu ở đâu (P3.5). Thẻ sai thì điểm kỹ năng sai và gợi ý sai, nên cần cả nhóm duyệt một lần.

**Cần duyệt:** (1) danh sách thẻ có thiếu/thừa không, tên tiếng Việt có dễ hiểu không; (2) thẻ của từng bài có đúng kỹ năng chính mà bài luyện không (không gắn kỹ năng chỉ xuất hiện thoáng qua). Ghi ý kiến vào cột *Ý kiến*; đồng ý thì ghi ✔ vào cột *OK*.

## Danh sách thẻ (17)

| Thẻ | Tiếng Việt | English | Số bài |
|---|---|---|---|
| `hash-map` | Bảng băm (dict) | Hash map | 6 |
| `two-pointers` | Hai con trỏ | Two pointers | 3 |
| `sliding-window` | Cửa sổ trượt | Sliding window | 2 |
| `binary-search` | Tìm kiếm nhị phân | Binary search | 1 |
| `recursion` | Đệ quy | Recursion | 3 |
| `dynamic-programming` | Quy hoạch động | Dynamic programming | 1 |
| `graph` | Đồ thị | Graphs | 1 |
| `linked-structures` | Danh sách liên kết, cây | Linked lists and trees | 3 |
| `string-processing` | Xử lý chuỗi | String processing | 6 |
| `control-flow` | Vòng lặp và điều kiện | Loops and conditions | 2 |
| `null-handling` | Xử lý dữ liệu thiếu | Missing data | 1 |
| `error-handling` | Xử lý ngoại lệ | Error handling | 1 |
| `concurrency` | Đồng thời, đa luồng | Concurrency | 6 |
| `input-validation` | Kiểm tra dữ liệu vào | Input validation | 4 |
| `security` | Bảo mật | Security | 5 |
| `caching` | Bộ nhớ đệm | Caching | 2 |
| `data-structure-design` | Thiết kế cấu trúc dữ liệu | Data structure design | 5 |

Thẻ ít bài (1–2 bài) thì điểm Elo của kỹ năng đó sẽ ít dữ liệu; nhóm có thể đề xuất gộp thẻ.

## Thẻ của từng bài

| Bài | Tên | Level | Loại | Thẻ | OK | Ý kiến |
|---|---|---|---|---|---|---|
| CP-001 | Two-Sum Variations | fresher | implement | `hash-map` | | |
| CP-002 | Reverse a Linked List | fresher | implement | `linked-structures` | | |
| CP-003 | Validate Palindrome | fresher | implement | `two-pointers`, `string-processing` | | |
| CP-004 | Fix the Off-By-One Loop | fresher | debug | `control-flow` | | |
| CP-005 | Sanitise User Input | fresher | implement | `input-validation`, `string-processing`, `security` | | |
| CP-006 | Count Word Frequency | fresher | implement | `hash-map`, `string-processing` | | |
| CP-007 | Merge Two Sorted Arrays | fresher | implement | `two-pointers` | | |
| CP-008 | Debug the Null Reference | fresher | debug | `null-handling` | | |
| CP-009 | Rate-Limit a Request Handler | fresher | implement | `hash-map`, `data-structure-design` | | |
| CP-010 | FizzBuzz, Explained | fresher | implement | `control-flow` | | |
| CP-011 | Find the Duplicate | fresher | implement | `hash-map`, `two-pointers` | | |
| CP-012 | Trace the Race Condition | fresher | debug | `concurrency` | | |
| CP-101 | LRU Cache Design | junior | implement | `hash-map`, `linked-structures`, `caching` | | |
| CP-102 | Debug the Memory Leak | junior | debug | `caching`, `data-structure-design` | | |
| CP-103 | Validate a JWT Flow | junior | implement | `security`, `input-validation` | | |
| CP-104 | Producer–Consumer Queue | junior | implement | `concurrency` | | |
| CP-105 | Longest Substring No Repeat | junior | implement | `sliding-window`, `hash-map`, `string-processing` | | |
| CP-106 | Patch the SQL Injection | junior | debug | `security`, `input-validation` | | |
| CP-107 | Detect Cycle in Graph | junior | implement | `graph`, `recursion` | | |
| CP-108 | Thread-Safe Counter | junior | implement | `concurrency` | | |
| CP-109 | Reconstruct the Stack Trace | junior | debug | `error-handling` | | |
| CP-110 | Sliding Window Maximum | junior | implement | `sliding-window`, `data-structure-design` | | |
| CP-201 | Distributed Rate Limiter | senior | implement | `concurrency`, `data-structure-design` | | |
| CP-202 | Median of Two Sorted Arrays | senior | implement | `binary-search` | | |
| CP-203 | Audit the Auth Middleware | senior | debug | `security` | | |
| CP-204 | Lock-Free Ring Buffer | senior | implement | `concurrency`, `data-structure-design` | | |
| CP-205 | Regular Expression Matching | senior | implement | `dynamic-programming`, `recursion`, `string-processing` | | |
| CP-206 | Diagnose the Deadlock | senior | debug | `concurrency` | | |
| CP-207 | Serialize a Binary Tree | senior | implement | `recursion`, `linked-structures`, `string-processing` | | |
| CP-208 | Harden the Upload Endpoint | senior | debug | `security`, `input-validation` | | |

## Sau khi duyệt

Người duyệt (khác tác giả) ghi tên vào `skills.review.reviewer` và đổi `status` thành `approved` trong từng file `content/exercises/CP-*.json` (hoặc báo lại để Claude sửa). Sau đó chạy `python -m app.features.content.sync` (dry run sẽ in dòng `skills ... approved by ...`) rồi `--apply`. Thẻ còn là draft sẽ không được ghi vào DB.

## Kết quả duyệt (2026-09-30)

Kiệt, Trung, Phát và Minh đã duyệt. 22/30 bài được cả 4 người đồng ý. Phiếu đã điền được lưu ngoài repo, trong `calibration-private/exports`. Các ý kiến được xử lý dựa trên đề và lời giải tham chiếu:

| Ý kiến | Quyết định |
|---|---|
| `null-handling`: "Xử lý dữ liệu thiếu" quá rộng (Trung, Minh) | Đổi thành **Xử lý giá trị null** / Null handling |
| `error-handling` (Minh) | Đổi thành **Xử lý lỗi và ngoại lệ** |
| CP-011: chỉ giữ thẻ của cách giải chính (Trung, Minh) | Lời giải dùng `set` → **chỉ còn `hash-map`** |
| CP-201: thiếu `distributed-systems` (Minh) | Thêm thẻ mới **`distributed-systems`** (Hệ thống phân tán) thay cho `data-structure-design`, vì bài dùng Redis chung, không thiết kế cấu trúc dữ liệu |
| CP-207: `string-processing` chỉ là định dạng đầu ra (Minh) | **Bỏ `string-processing`** (lời giải chỉ `split`/`join`) |
| CP-005: bỏ `security` nếu đề không nói tới injection (Phát) | **Giữ nguyên**: đề yêu cầu lọc ký tự nguy hiểm trước khi vào tầng database và giải thích mình đang phòng thủ cái gì |
| CP-102: bỏ `caching` nếu lỗi không nằm ở cache (Trung, Minh) | **Giữ nguyên**: đề nói rõ là cache tăng không giới hạn, và cách sửa là thêm cơ chế loại bỏ kiểu LRU |
| CP-110: `data-structure-design` quá rộng (Minh) | **Giữ nguyên**: một thẻ "deque đơn điệu" riêng chỉ có 1 bài nên Elo gần như không có dữ liệu |
| CP-203: thêm `input-validation` (Trung) | **Giữ nguyên**: code gốc đã từ chối token thiếu hoặc rỗng; lỗi thật là không gọi `verify()` (xác thực), không phải kiểm tra dữ liệu vào |

Bộ thẻ cuối cùng có 18 thẻ. Thẻ của cả 30 bài được đánh dấu `approved`.
