"""Build the 40 simulated session scripts and their intended profiles (private).

Run from the backend repo root with its venv:
    python ../calibration-private/build_scripts.py   (paths below are absolute)

Levels follow docs/calibration/huong-dan-cham.md. "NA" = không áp dụng.
Verification is decided after the run (it depends on whether Ciel gave code).
"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
SCRIPTS = OUT / "scripts"


def H(at, text): return {"at": at, "do": "hypothesis", "text": text}
def C(at, ref, code=None): return {"at": at, "do": "code", "ref": ref, **({"code": code} if code else {})}
def R(at): return {"at": at, "do": "run"}
def A(at, text, send_code=False): return {"at": at, "do": "ask", "text": text, "send_code": send_code}
def U(at): return {"at": at, "do": "use_ai_code"}
def W(at, seconds, kind="tab"): return {"at": at, "do": "away", "seconds": seconds, "kind": kind}
def S(at): return {"at": at, "do": "submit"}


SESSIONS = []


def session(sid, student, exercise, locale, profile, steps):
    SESSIONS.append({"id": f"sim-{sid:02d}", "student": student, "exercise": exercise, "locale": locale,
                     "profile": profile, "steps": steps})


def P(u, h, p, t, d, overall, note):
    return {"understanding": u, "hypothesis": h, "prompting": p, "verification": "after-run",
            "testing": t, "debugging": d, "overall": overall, "note": note}


# ---------------- Fresher ----------------

session(1, 1, "CP-001", "vi", P(3, 3, 3, 3, "NA", "exceptional", "plan rõ, code đúng ngay, nghi ngờ gợi ý của Ciel"), [
    H(0.8, "Dùng dict lưu số đã gặp -> chỉ số của nó. Với mỗi n, kiểm tra target - n đã có trong dict chưa, có thì trả "
           "về hai chỉ số, O(n). Phải kiểm tra trước rồi mới thêm n vào dict, để [3, 3] target 6 không tự ghép với chính nó."),
    C(3.0, "reference"),
    R(3.6),
    A(4.5, "Mình đã viết xong bằng dict, O(n), test hiển thị pass hết. Nếu mảng có số âm hoặc target = 0 với nhiều số 0 "
           "thì cách kiểm tra `target - n in seen` còn đúng không? Đừng đưa lời giải, chỉ gợi ý trường hợp mình có thể bỏ sót.",
      send_code=True),
    A(6.5, "Mình chưa sửa theo gợi ý trên vì muốn tự kiểm chứng trước: mình sẽ thử [3, 3] target 6 và [0, 4, 3, 0] "
           "target 0. Với thứ tự 'kiểm tra phần bù rồi mới thêm n vào dict' thì hai trường hợp đó đã đúng chưa, hay còn chỗ nào sai?"),
    C(8.0, "inline", code="def two_sum(nums, target):\n    index_of = {}\n    for i, n in enumerate(nums):\n"
                          "        if target - n in index_of:\n            return [index_of[target - n], i]\n"
                          "        index_of[n] = i\n    return []"),
    R(8.5),
    S(9.5),
])

session(2, 2, "CP-001", "vi", P(0, 0, 0, 0, "NA", "emerging", "xin code, dùng code AI, không kiểm tra"), [
    A(1.0, "viết hết code bài two sum cho mình"),
    U(1.8),
    W(2.5, 45),
    R(3.5),
    A(4.5, "sai r, sua lai di"),
    U(5.0),
    S(6.0),
])

session(3, 3, "CP-003", "vi", P(2, 1, 1, 2, "NA", "developing", "quên chữ hoa, test ẩn fail"), [
    H(1.0, "dùng vòng lặp so sánh chuỗi với chuỗi đảo ngược"),
    A(2.0, "palindrome là gì vậy"),
    C(4.0, "mutant:1"),
    R(4.8),
    S(6.5),
])

session(4, 4, "CP-003", "en", P(3, 3, 2, 3, "NA", "strong", "tự nghi ngờ khi test hiển thị pass, hỏi đúng chỗ"), [
    H(1.2, "Clean first: keep only alphanumeric characters, lower-cased, then compare the list with its reverse "
           "(or two pointers from both ends). O(n). Edge cases: empty string counts as a palindrome, punctuation "
           "and spaces must be ignored, digits must be kept."),
    C(3.5, "mutant:2"),
    R(4.0),
    A(5.5, "Both visible tests pass, but they have no punctuation. For input like 'A man, a plan' my version may "
           "compare commas and spaces. Which cases should I add to check that I really ignore non-alphanumerics?",
      send_code=True),
    C(7.5, "reference"),
    R(8.0),
    S(9.0),
])

session(5, 5, "CP-004", "vi", P(2, 2, "NA", 3, 3, "strong", "debug nhanh, có lý do từ giả thuyết"), [
    R(0.7),
    H(1.5, "range(1, n) dừng trước n nên thiếu số n, phải sửa thành range(1, n + 1)"),
    C(2.5, "reference"),
    R(3.0),
    S(4.5),
])

session(6, 6, "CP-004", "vi", P(0, 0, 1, 1, 0, "emerging", "thử-sai, không sửa được, nộp khi còn fail"), [
    A(0.8, "bai nay sai o dau"),
    U(1.5),
    R(2.2),
    A(3.0, "van sai"),
    C(4.0, "mutant:2"),
    R(4.5),
    C(5.5, "mutant:3"),
    R(6.0),
    S(7.0),
])

session(7, 7, "CP-006", "en", P(1, 2, 1, 2, "NA", "developing", "split(' ') lỗi với nhiều khoảng trắng"), [
    H(0.8, "Lower-case the text, split into words and count each word in a dict."),
    C(3.0, "mutant:3"),
    R(3.5),
    A(4.5, "what's wrong with my code?", send_code=True),
    S(6.0),
])

session(8, 8, "CP-007", "vi", P(1, 1, "NA", 1, 0, "emerging", "thử-sai nhiều lần, bỏ cuộc khi vẫn fail"), [
    H(1.0, "gộp hai mảng lại"),
    C(3.0, "mutant:3"),
    R(3.4),
    C(4.5, "mutant:1"),
    R(4.9),
    C(6.0, "mutant:4"),
    R(6.4),
    S(8.0),
])

session(9, 1, "CP-008", "vi", P(3, 3, 3, 3, 3, "exceptional", "sửa đúng ngay, hỏi Ciel về trường hợp biên"), [
    H(0.7, "user['profile'] lỗi khi không có khoá profile hoặc profile là None. Lấy profile bằng user.get('profile') or {} "
           "rồi profile.get('name', 'Unknown'), như vậy xử lý được cả thiếu khoá, None và profile không có tên."),
    C(2.0, "reference"),
    R(2.5),
    A(3.5, "Mình sửa bằng user.get('profile') or {} để xử lý cả trường hợp profile là None. Nếu name tồn tại nhưng là "
           "chuỗi rỗng thì có nên trả 'Unknown' không, hay đề chỉ yêu cầu khi thiếu tên? Gợi ý giúp mình, đừng viết code.",
      send_code=True),
    C(5.5, "inline", code="def display_name(user):\n    # profile may be missing or None\n"
                          "    profile = user.get(\"profile\") or {}\n    return profile.get(\"name\", \"Unknown\")"),
    R(6.0),
    S(7.0),
])

session(10, 9, "CP-008", "en", P(1, 1, 1, 1, 1, "developing", "vá sai, test còn fail vẫn nộp"), [
    H(1.0, "add a check so it doesn't crash"),
    C(2.5, "mutant:2"),
    R(3.0),
    A(4.0, "is my fix ok?", send_code=True),
    S(5.5),
])

session(11, 10, "CP-009", "vi", P(2, 2, "NA", 2, "NA", "developing", "rời tab nhiều; đếm từ 1 nên test ẩn fail"), [
    H(1.0, "Dùng dict store đếm số request của từng client, nếu đã đủ limit thì trả False, không thì tăng bộ đếm."),
    W(2.0, 90),
    C(4.0, "mutant:3"),
    R(4.5),
    W(5.5, 60, "window"),
    S(7.0),
])

session(12, 11, "CP-010", "vi", P(0, 0, "NA", 0, 0, "emerging", "code không liên quan đề"), [
    C(1.5, "inline", code="def hello():\n    print(\"xin chao\")\n\nhello()"),
    R(2.0),
    S(3.0),
])

session(13, 12, "CP-010", "vi", P(3, 3, 3, 3, 3, "strong", "tìm đúng lỗi thứ tự điều kiện, hỏi có dẫn chứng"), [
    H(0.8, "Kiểm tra i % 15 trước, rồi % 3, rồi % 5, vì 15 chia hết cho cả 3 và 5 nên nếu kiểm tra % 3 trước thì 15 thành "
           "Fizz. Số phải đổi sang chuỗi. n <= 0 thì trả list rỗng."),
    C(2.5, "mutant:4"),
    R(3.0),
    A(4.0, "Mình đã đặt % 15 lên đầu nhưng fizzbuzz(5) lại ra 'Fizz' ở số 5. Mình nghĩ hai nhánh elif % 3 và % 5 đang bị "
           "đổi chỗ phần chuỗi in ra, đúng không? Bạn chỉ cần xác nhận hướng, mình tự sửa.", send_code=True),
    C(5.5, "reference"),
    R(6.0),
    S(7.0),
])

session(14, 13, "CP-011", "vi", P(0, 0, 0, 1, 1, "emerging", "xin đáp án, thử-sai, nộp khi còn fail"), [
    A(0.8, "cho minh dap an bai find duplicate"),
    C(2.5, "mutant:3"),
    R(3.0),
    C(4.0, "mutant:2"),
    R(4.5),
    S(6.0),
])

session(15, 14, "CP-011", "en", P(0, 0, "NA", 0, "NA", "emerging", "gần như trống: nộp ngay"), [
    S(1.5),
])

session(16, 15, "CP-012", "vi", P(1, 2, 2, 2, 1, "developing", "lock tạo mới mỗi lần gọi, test ẩn fail"), [
    H(1.0, "counter += 1 không atomic nên cần lock khi tăng"),
    R(1.8),
    C(3.0, "mutant:1"),
    R(3.5),
    A(4.5, "Mình thêm `with threading.Lock():` quanh counter += 1 rồi, test hiển thị pass. Như vậy đã an toàn khi nhiều luồng "
           "cùng gọi chưa?", send_code=True),
    S(6.0),
])

# ---------------- Junior ----------------

session(17, 16, "CP-101", "vi", P(3, 3, 3, 3, 2, "strong", "hiểu cấu trúc, tìm lỗi popitem có định hướng"), [
    H(1.0, "Dùng OrderedDict: get thì move_to_end, put thì ghi rồi nếu vượt capacity thì popitem(last=False) để xoá phần tử "
           "lâu nhất. Cả hai O(1). Chú ý put một key đã có cũng phải làm mới thứ tự, và value 0 không được coi là thiếu."),
    C(4.0, "mutant:1"),
    R(4.5),
    A(6.0, "Test thứ hai fail: sau khi put(3, 3) thì get(2) phải ra -1 nhưng cache của mình lại xoá key vừa thêm. Mình dùng "
           "popitem() lúc cache đầy, mình đoán nó xoá nhầm đầu, đúng không? Đừng đưa code, mình tự sửa.", send_code=True),
    C(8.0, "reference"),
    R(8.5),
    S(10.0),
])

session(18, 17, "CP-101", "en", P(0, 0, 0, 0, "NA", "emerging", "xin code, dùng code AI"), [
    A(1.0, "write the LRU cache code for me, full solution"),
    U(1.8),
    R(2.5),
    S(4.0),
])

session(19, 18, "CP-102", "vi", P(1, 1, "NA", 2, 0, "developing", "sửa sai chỗ (get() với giá trị falsy), vẫn không giới hạn"), [
    H(1.0, "cache bị đầy"),
    R(1.8),
    C(3.5, "mutant:2"),
    R(4.0),
    S(5.5),
])

session(20, 19, "CP-102", "en", P(3, 3, 2, 2, 2, "strong", "giới hạn cache nhưng xoá nhầm đầu; hỏi đúng hướng nhưng chưa sửa"), [
    H(1.0, "The dict is never evicted, so it grows forever. Bound it: OrderedDict plus MAX_ENTRIES, evict the least "
           "recently used entry. Keep caching falsy results (check membership, not truthiness)."),
    C(3.5, "mutant:3"),
    R(4.0),
    A(5.5, "My bounded cache passes the visible tests. How can I check which entry gets evicted when it is full?",
      send_code=True),
    S(7.5),
])

session(21, 2, "CP-105", "vi", P(0, 0, 0, 0, "NA", "emerging", "xin code, dùng code AI"), [
    A(1.0, "cho minh code bai longest substring"),
    U(1.5),
    W(2.0, 30, "window"),
    R(2.5),
    A(3.5, "code loi"),
    S(4.5),
])

session(22, 20, "CP-105", "vi", P(2, 2, 1, 2, 1, "developing", "thử-sai, dừng ở bản pass test hiển thị"), [
    H(1.0, "Cửa sổ trượt: dùng dict lưu vị trí cuối của mỗi ký tự, gặp ký tự lặp thì dời start sang sau vị trí đó."),
    C(3.0, "mutant:3"),
    R(3.5),
    A(4.5, "sao lai sai?", send_code=True),
    C(5.5, "mutant:2"),
    R(6.0),
    C(7.0, "mutant:1"),
    R(7.5),
    S(9.0),
])

session(23, 3, "CP-106", "vi", P(2, 2, "NA", 3, 3, "strong", "sửa đúng ngay, chỉ nói làm gì"), [
    H(1.2, "Không nối chuỗi vào câu SQL nữa mà dùng tham số ? và truyền (name,) cho execute."),
    C(2.5, "reference"),
    R(3.0),
    S(4.0),
])

session(24, 4, "CP-106", "en", P(1, 1, "NA", 2, 0, "developing", "đổi sang f-string, vẫn injection"), [
    H(1.0, "escape the quotes in the name"),
    W(2.0, 20),
    C(3.0, "mutant:2"),
    R(3.5),
    S(5.0),
])

session(25, 5, "CP-107", "vi", P(3, 3, "NA", 3, 3, "exceptional", "DFS 3 trạng thái, sửa nhanh lỗi quên đánh dấu"), [
    H(1.0, "DFS với trạng thái: đang thăm và đã xong. Gặp lại nút đang thăm là có chu trình; nút đã xong thì bỏ qua (đồ thị "
           "kim cương không phải chu trình). Duyệt từ mọi nút để bắt chu trình ở thành phần khác. O(V + E)."),
    C(3.0, "mutant:1"),
    R(3.5),
    C(4.5, "reference"),
    R(5.0),
    S(6.5),
])

session(26, 6, "CP-108", "vi", P(2, 2, 2, 2, "NA", "developing", "lock mới mỗi lần gọi"), [
    H(1.0, "dùng Lock khi tăng biến đếm"),
    C(3.0, "mutant:1"),
    R(3.5),
    A(4.5, "Mình dùng with Lock(): trong increment. Có cần khoá cả khi đọc value không, và vì sao?", send_code=True),
    U(5.5),
    R(6.0),
    S(7.0),
])

session(27, 7, "CP-108", "en", P(3, 3, 3, 3, "NA", "exceptional", "đúng ngay, hỏi sâu về đọc có khoá"), [
    H(1.0, "One Lock per Counter created in __init__, taken around the increment. A shared lock is essential: a new "
           "Lock() per call would never block. Also lock the read so value never sees a half-finished update."),
    C(3.0, "reference"),
    R(3.5),
    A(4.5, "I used one Lock per Counter and also lock the read in value. Is locking the getter necessary in CPython, or "
           "only for consistency across implementations? Please explain, no code.", send_code=True),
    C(6.5, "inline", code="from threading import Lock\n\nclass Counter:\n    def __init__(self):\n        self._n = 0\n"
                          "        self._lock = Lock()  # one shared lock per counter\n\n    def increment(self):\n"
                          "        with self._lock:\n            self._n += 1\n\n    @property\n    def value(self):\n"
                          "        with self._lock:\n            return self._n"),
    R(7.0),
    S(8.0),
])

session(28, 8, "CP-109", "vi", P(2, 1, "NA", 2, 1, "developing", "chép thông báo lỗi, không nối nguyên nhân"), [
    H(1.0, "sửa exception cho rõ hơn"),
    C(2.5, "mutant:3"),
    R(3.0),
    S(4.5),
])

session(29, 9, "CP-110", "vi", P(2, 2, 2, 3, "NA", "strong", "deque đơn điệu; nghi ngờ điều kiện cửa sổ"), [
    H(1.2, "Dùng deque giữ chỉ số theo giá trị giảm dần, đầu deque luôn là max của cửa sổ."),
    C(4.0, "mutant:1"),
    R(4.5),
    A(6.0, "Test hiển thị pass nhưng mình không chắc điều kiện bỏ phần tử cũ: dq[0] < i - k hay <= ? Gợi ý cách kiểm tra.",
      send_code=True),
    C(8.0, "reference"),
    R(8.5),
    S(10.0),
])

session(30, 10, "CP-110", "vi", P(1, 1, "NA", 2, "NA", "developing", "O(n*k), fail test hiệu năng"), [
    H(1.0, "duyệt từng cửa sổ rồi lấy max"),
    C(2.5, "inline", code="from collections import deque\n\ndef max_sliding_window(nums, k):\n"
                          "    return [max(nums[i:i + k]) for i in range(len(nums) - k + 1)]"),
    R(3.0),
    S(4.5),
])

# ---------------- Senior ----------------

session(31, 11, "CP-201", "vi", P(2, 2, 1, 3, "NA", "strong", "INCR rồi EXPIRE, biết có race"), [
    H(1.5, "INCR key, nếu là lần đầu (giá trị 1) thì EXPIRE key window. Trả về count <= limit."),
    C(4.0, "inline", code="def is_allowed(redis, key, limit, window):\n    count = redis.incr(key)\n    if count == 1:\n"
                          "        redis.expire(key, window)\n    return count <= limit"),
    R(4.5),
    A(6.0, "race INCR EXPIRE la gi?"),
    S(8.0),
])

session(32, 12, "CP-202", "vi", P(3, 3, 2, 3, 2, "strong", "chia phân hoạch, tìm lỗi chia nguyên"), [
    H(1.5, "Tìm nhị phân trên mảng ngắn hơn: chọn i phần tử từ a và j = half - i từ b sao cho max bên trái <= min bên phải. "
           "O(log(min(m, n))). Mảng rỗng thì dùng -inf / +inf ở biên; tổng chẵn lấy trung bình hai giá trị giữa."),
    C(5.0, "mutant:2"),
    R(5.5),
    A(7.0, "find_median([1, 2], [3, 4]) ra 2 thay vì 2.5. Có phải do phép chia không?", send_code=True),
    C(9.0, "reference"),
    R(9.5),
    S(11.0),
])

session(33, 13, "CP-202", "vi", P(1, 1, "NA", 3, "NA", "developing", "gộp rồi sort: đúng nhưng không đạt O(log)"), [
    H(1.0, "gộp hai mảng rồi lấy phần tử ở giữa"),
    C(3.0, "inline", code="def find_median(a, b):\n    merged = sorted(a + b)\n    n = len(merged)\n    mid = n // 2\n"
                          "    if n % 2:\n        return float(merged[mid])\n    return (merged[mid - 1] + merged[mid]) / 2"),
    W(3.5, 60),
    R(4.0),
    S(5.0),
])

session(34, 14, "CP-203", "vi", P(1, 1, 1, 1, 1, "developing", "thử-sai, nộp khi còn fail"), [
    H(1.0, "có token là cho qua là sai"),
    C(2.5, "mutant:2"),
    R(3.0),
    A(4.0, "van fail", send_code=True),
    C(5.0, "mutant:1"),
    R(5.5),
    S(7.0),
])

session(35, 15, "CP-203", "en", P(3, 3, 3, 3, 3, "exceptional", "đúng ngay, hỏi Ciel về trường hợp biên"), [
    H(1.0, "The check only tests that a token is present; it must call verify(token). Missing header and empty token must "
           "be denied, and the handler must never run for a forged token."),
    C(2.5, "reference"),
    R(3.0),
    A(4.0, "I changed it to `if token and verify(token)`. Could an empty-string token or a missing header still reach the "
           "handler? Just point me to cases to test.", send_code=True),
    C(6.0, "inline", code="VALID_TOKENS = {\"valid-token\"}\n\ndef deny():\n    return \"401 Unauthorized\"\n\n"
                          "def verify(token):\n    return token in VALID_TOKENS\n\ndef require_auth(request, handler):\n"
                          "    token = request.headers.get(\"Authorization\")\n    # both present and valid, or deny\n"
                          "    if token and verify(token):\n        return handler(request)\n    return deny()"),
    R(6.5),
    S(7.5),
])

session(36, 16, "CP-205", "vi", P(1, 0, 0, 2, 1, "developing", "xin code, thử-sai tới khi pass test hiển thị"), [
    A(1.0, "viết giúp mình hàm is_match"),
    C(4.0, "mutant:1"),
    R(4.5),
    C(6.0, "mutant:2"),
    R(6.5),
    C(8.0, "mutant:3"),
    R(8.5),
    S(10.0),
])

session(37, 17, "CP-206", "vi", P(2, 2, 2, 2, 2, "strong", "khoá theo số dư: có hướng nhưng chưa ổn định"), [
    H(1.0, "Deadlock vì hai luồng khoá theo thứ tự ngược nhau; phải khoá theo một thứ tự cố định."),
    R(1.8),
    C(3.5, "mutant:2"),
    R(4.0),
    A(5.5, "Mình sort hai tài khoản theo balance để khoá theo thứ tự. Có vấn đề gì khi balance thay đổi giữa hai lần chuyển "
           "không?", send_code=True),
    S(7.5),
])

session(38, 18, "CP-207", "en", P(0, 0, 0, 0, "NA", "emerging", "xin code, rời tab nhiều"), [
    A(1.0, "give me the serialize and deserialize code"),
    W(1.5, 120),
    U(4.0),
    W(4.5, 60),
    R(6.0),
    W(6.5, 90, "window"),
    S(9.0),
])

session(39, 19, "CP-207", "vi", P(1, 1, 1, 1, 0, "emerging", "nối bằng dấu cách, test fail vẫn nộp"), [
    H(1.0, "dùng đệ quy"),
    C(4.0, "mutant:3"),
    R(4.5),
    A(5.5, "gợi ý cách test deserialize"),
    S(7.0),
])

session(40, 20, "CP-208", "vi", P(1, 0, 2, 2, 1, "developing", "chỉ tin content_type, chưa kiểm tra byte đầu"), [
    A(1.0, "Mình cần kiểm tra những gì để upload an toàn? Mình định dùng basename cho tên file, còn loại file thì chưa biết "
           "kiểm tra thế nào."),
    C(4.0, "mutant:2"),
    R(4.5),
    S(6.5),
])


# Authored at a brisk pace; real students take longer, so stretch every timeline.
TIME_SCALE = 1.8


def main() -> None:
    SCRIPTS.mkdir(parents=True, exist_ok=True)
    profiles = {}
    for s in SESSIONS:
        steps = [{**step, "at": round(step["at"] * TIME_SCALE, 1)} for step in s["steps"]]
        script = {"id": s["id"], "student": s["student"], "exercise": s["exercise"], "locale": s["locale"],
                  "steps": steps}
        (SCRIPTS / f"{s['id']}.json").write_text(json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8")
        profiles[s["id"]] = {"exercise": s["exercise"], **s["profile"]}
    (OUT / "profiles.json").write_text(json.dumps(profiles, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(SESSIONS)} scripts written")


if __name__ == "__main__":
    main()
