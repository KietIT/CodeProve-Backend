# Duyệt dữ liệu bài debug (P2.2)

Ở 9 bài debug, học sinh sẽ **bấm vào dòng lỗi** và viết một câu giải thích trước khi được sửa code. Sau khi nộp, trang Feedback hiện **vùng lỗi thật** và **lời giải thích** dưới đây. Học sinh có thể mua 2 gợi ý: gợi ý 1 là câu dưới đây (loại lỗi), gợi ý 2 là khoảng dòng (tự tính: vùng lỗi mở rộng 1 dòng mỗi bên).

**Cần duyệt cho từng bài:** (1) vùng lỗi có đúng chỗ lỗi không, (2) lời giải thích có đúng và dễ hiểu không, (3) gợi ý 1 có giúp mà không lộ dòng lỗi không. Ghi ý kiến vào bảng cuối phiếu.

## CP-004 Fix the Off-By-One Loop

Code học sinh thấy (dòng đánh dấu ◀ là vùng lỗi):

```python
 1 def sum_to_n(n):
 2     total = 0
 3     for i in range(1, n):   ◀
 4         total += i
 5     return total
```

- **Vùng lỗi:** dòng 3 *(tự tính)*
- **Gợi ý 1:** Lỗi nằm ở biên của một vòng lặp (off-by-one).
- **Gợi ý 2:** Xem kỹ các dòng 2–4.
- **Giải thích (hiện sau khi nộp):** Dòng 3: range(1, n) dừng trước n nên n không bao giờ được cộng vào (sum_to_n(3) trả 3 thay vì 6). Cận trên phải là n + 1.

## CP-008 Debug the Null Reference

Code học sinh thấy (dòng đánh dấu ◀ là vùng lỗi):

```python
 1 def display_name(user):
 2     return user["profile"]["name"]   ◀
```

- **Vùng lỗi:** dòng 2 *(tự tính)*
- **Gợi ý 1:** Hàm lỗi khi dữ liệu vào thiếu một khoá.
- **Gợi ý 2:** Xem kỹ các dòng 1–2.
- **Giải thích (hiện sau khi nộp):** Dòng 2 truy cập thẳng user["profile"]["name"], nên user không có "profile" (hoặc profile là None) gây lỗi thay vì trả "Unknown". Cần .get() với giá trị mặc định.

## CP-012 Trace the Race Condition

Code học sinh thấy (dòng đánh dấu ◀ là vùng lỗi):

```python
 1 counter = 0
 2 
 3 def increment():
 4     global counter
 5     counter += 1   ◀
```

- **Vùng lỗi:** dòng 5 *(chỉnh tay)*
- **Gợi ý 1:** Lỗi chỉ lộ ra khi nhiều luồng chạy cùng lúc.
- **Gợi ý 2:** Xem kỹ các dòng 4–5.
- **Giải thích (hiện sau khi nộp):** Dòng 5: counter += 1 gồm đọc, cộng rồi ghi; hai luồng có thể cùng đọc một giá trị và một lần tăng bị mất. Phải cập nhật khi đang giữ một threading.Lock dùng chung.

## CP-102 Debug the Memory Leak

Code học sinh thấy (dòng đánh dấu ◀ là vùng lỗi):

```python
 1 _cache = {}   ◀
 2 
 3 def memoize(key, compute):
 4     if key not in _cache:   ◀
 5         _cache[key] = compute()   ◀
 6     return _cache[key]
```

- **Vùng lỗi:** dòng 1, 4, 5 *(chỉnh tay)*
- **Gợi ý 1:** Kết quả vẫn đúng, nhưng bộ nhớ tăng mãi theo thời gian.
- **Gợi ý 2:** Xem kỹ các dòng 1–6.
- **Giải thích (hiện sau khi nộp):** Cache ở dòng 1 là dict thường và dòng 4–5 chỉ thêm phần tử, không bao giờ xoá, nên nó lớn vô hạn. Cần giới hạn kích thước và một quy tắc loại bỏ, ví dụ OrderedDict bỏ phần tử lâu không dùng nhất.

## CP-106 Patch the SQL Injection

Code học sinh thấy (dòng đánh dấu ◀ là vùng lỗi):

```python
 1 def find_user(db, name):
 2     return db.execute(
 3         "SELECT * FROM users WHERE name = '" + name + "'"   ◀
 4     )
```

- **Vùng lỗi:** dòng 3 *(tự tính)*
- **Gợi ý 1:** Lỗi bảo mật nằm ở cách dựng câu truy vấn.
- **Gợi ý 2:** Xem kỹ các dòng 2–4.
- **Giải thích (hiện sau khi nộp):** Dòng 3 ghép thẳng name vào câu SQL, nên input như ' OR '1'='1 làm đổi nghĩa câu truy vấn (SQL injection). Phải truyền giá trị bằng tham số: "... WHERE name = ?", (name,).

## CP-109 Reconstruct the Stack Trace

Code học sinh thấy (dòng đánh dấu ◀ là vùng lỗi):

```python
 1 def load(path):
 2     try:
 3         return open(path).read()
 4     except Exception:   ◀
 5         raise RuntimeError("load failed")   ◀
```

- **Vùng lỗi:** dòng 4, 5 *(tự tính)*
- **Gợi ý 1:** Khi có lỗi, thông tin cần để điều tra bị mất.
- **Gợi ý 2:** Xem kỹ các dòng 3–5.
- **Giải thích (hiện sau khi nộp):** Dòng 4–5 bắt ngoại lệ rồi raise một RuntimeError mới mà không nối với lỗi gốc, nên nguyên nhân thật (ví dụ file nào không có) bị mất. Cần except Exception as exc và raise ... from exc.

## CP-203 Audit the Auth Middleware

Code học sinh thấy (dòng đánh dấu ◀ là vùng lỗi):

```python
 1 VALID_TOKENS = {"valid-token"}
 2 
 3 def deny():
 4     return "401 Unauthorized"
 5 
 6 def verify(token):
 7     return token in VALID_TOKENS
 8 
 9 def require_auth(request, handler):
10     token = request.headers.get("Authorization")
11     if token:   ◀
12         return handler(request)
13     return deny()
```

- **Vùng lỗi:** dòng 11 *(tự tính)*
- **Gợi ý 1:** Một bước kiểm tra bảo mật chưa đủ.
- **Gợi ý 2:** Xem kỹ các dòng 10–12.
- **Giải thích (hiện sau khi nộp):** Dòng 11 chỉ kiểm tra token có tồn tại, nên token giả bất kỳ cũng tới được handler. Token phải qua verify(token) trước khi gọi handler(request).

## CP-206 Diagnose the Deadlock

Code học sinh thấy (dòng đánh dấu ◀ là vùng lỗi):

```python
 1 def transfer(a, b, amount):
 2     with a.lock:   ◀
 3         with b.lock:   ◀
 4             a.balance -= amount
 5             b.balance += amount
```

- **Vùng lỗi:** dòng 2, 3 *(tự tính)*
- **Gợi ý 1:** Lỗi chỉ xảy ra khi hai giao dịch ngược chiều chạy cùng lúc.
- **Gợi ý 2:** Xem kỹ các dòng 1–4.
- **Giải thích (hiện sau khi nộp):** Dòng 2–3 khoá a rồi mới khoá b; giao dịch từ b sang a khoá theo thứ tự ngược lại, nên mỗi luồng giữ một khoá và chờ nhau mãi (deadlock). Luôn khoá hai tài khoản theo một thứ tự cố định, ví dụ sắp theo id.

## CP-208 Harden the Upload Endpoint

Code học sinh thấy (dòng đánh dấu ◀ là vùng lỗi):

```python
 1 import os
 2 
 3 ALLOWED_TYPES = {"image/png": b"\x89PNG", "image/jpeg": b"\xff\xd8\xff"}
 4 MAX_BYTES = 1_000_000
 5 
 6 def save_upload(file, upload_dir):
 7     path = os.path.join(upload_dir, file.filename)   ◀
 8     with open(path, "wb") as out:
 9         out.write(file.read())   ◀
10     return path
```

- **Vùng lỗi:** dòng 7 ; dòng 9 *(tự tính)*
- **Gợi ý 1:** Có hơn một lỗ hổng, đều do tin tưởng dữ liệu người dùng tải lên.
- **Gợi ý 2:** Xem kỹ các dòng 6–10.
- **Giải thích (hiện sau khi nộp):** Dòng 7 ghép tên file của người dùng vào đường dẫn, nên "../" thoát khỏi upload_dir (path traversal). Dòng 9 ghi mọi thứ được gửi: không kiểm tra chữ ký file theo loại và không giới hạn kích thước. Dùng basename, kiểm tra chữ ký, giới hạn kích thước.

## Bảng góp ý

Người duyệt: ________

| Bài | Vùng lỗi đúng? (C/K) | Giải thích đúng, dễ hiểu? (C/K) | Gợi ý 1 ổn? (C/K) | Góp ý |
|---|---|---|---|---|
| CP-004 | | | | |
| CP-008 | | | | |
| CP-012 | | | | |
| CP-102 | | | | |
| CP-106 | | | | |
| CP-109 | | | | |
| CP-203 | | | | |
| CP-206 | | | | |
| CP-208 | | | | |
