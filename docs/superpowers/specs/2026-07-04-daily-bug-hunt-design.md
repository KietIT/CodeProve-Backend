# Daily Bug Hunt - Design Spec

**Phiên bản:** v1.0
**Phạm vi:** Tính năng mới, full-stack (`codeprove-backend` + `codeprove-web`), độc lập với luồng chấm điểm AI-Fluency chính thức.
**Trạng thái:** Chờ user duyệt trước khi lên plan triển khai.

---

## 1. Bối cảnh & mục tiêu

CodeProve hiện khác biệt với LeetCode/HackerRank/CodeSignal ở việc **chấm quá trình dùng AI** (6 trục: Understanding, Hypothesis, Prompting, Verification, Testing, Debugging - xem `codeprove-backend/app/features/scoring/engine.py`). Trang Community (`codeprove-web/app/community/page.tsx`) đã có UI leaderboard/streak nhưng chỉ là **mock tĩnh** (dữ liệu hardcode, không có backend đứng sau - xem memory `codeprove-ui-fixes-workstream`).

**Mục tiêu:** xây một vòng lặp luyện tập **hàng ngày** dành cho lập trình viên cá nhân (ưu tiên tăng trưởng người dùng mới, B2B là lợi ích phụ đến sau), khác biệt với mọi đối thủ vì nó gamify đúng thứ CodeProve đo: **kỹ năng hoài nghi/kiểm chứng code do AI viết**, không phải kỹ năng thuật toán.

**Không phải mục tiêu (Non-goals):**
- Không thay thế hay sửa đổi hệ thống Exercise/Attempt/FluencyReport hiện có.
- Không ảnh hưởng đến Integrity Score hay 6 trục dùng trong báo cáo B2B cho trường học/nhà tuyển dụng.
- V1 không làm leaderboard công khai, không làm ảnh OG chia sẻ đẹp - chỉ chia sẻ dạng text. Các phần này để V2.
- V1 không hỗ trợ ngôn ngữ nào ngoài Python (khớp phạm vi hiện tại của sandbox).

---

## 2. Cơ chế chơi (Game Loop)

Một challenge cố định cho **tất cả người dùng** trong 1 ngày (giờ Việt Nam, `Asia/Ho_Chi_Minh`), giống mô hình Wordle - mọi người giải cùng 1 câu đố, tạo hiệu ứng "so sánh kết quả hôm nay" khi chia sẻ.

**Các trạng thái của 1 lượt chơi:**

1. **`not_started`** - người dùng vào `/daily`, thấy đề bài ngắn (1-2 câu) + đoạn code Python (10-20 dòng) do Ciel viết, có cài đúng 1 lỗi tinh vi. Đồng hồ bắt đầu chạy khi trang render xong.
2. **`playing`** - người dùng đọc code, click chọn dòng nghi có lỗi, gõ 1 câu giải thích ngắn (≥ 15 ký tự, tái dùng ngưỡng chống câu trả lời rỗng đã có ở `scoring/text_utils.py` cho explain-back).
3. **`hint_requested`** (tuỳ chọn, tối đa 2 lần) - mỗi lần xin gợi ý: hiện 1 gợi ý tăng dần độ rõ (gợi ý 1 = phạm vi/khu vực nghi vấn, gợi ý 2 = loại lỗi). Mỗi lần xin gợi ý hạ 1 bậc xếp hạng (xem mục 4).
4. **`submitted`** - người dùng bấm "Nộp": so dòng đã chọn với `buggy_line` lưu sẵn của challenge hôm đó. Đúng/sai không phụ thuộc câu giải thích (câu giải thích chỉ hiển thị lại cho vui, không chấm điểm bằng AI ở V1 - tránh phụ thuộc thêm 1 lời gọi LLM mỗi lượt chơi).
5. **`revealed`** - hiện đáp án đúng + giải thích ngắn của Ciel về lỗi, hiện kết quả (tier + thời gian + số gợi ý) + nút "Copy kết quả để chia sẻ".

Nếu người dùng rời trang giữa chừng và quay lại **cùng ngày đó**, khôi phục đúng trạng thái đã lưu (không cho chơi lại để đổi kết quả trong ngày).

---

## 3. Nguồn nội dung mỗi ngày

Tái dùng nguyên cơ chế cài lỗi đã có ở `MentorClient.chat(..., inject_error=True)` (`codeprove-backend/app/features/mentor/client.py:18-39`) và prompt suffix `MENTOR_INJECT_SUFFIX` (`codeprove-backend/app/features/mentor/prompts.py`) - **không xây prompt/LLM pipeline mới**.

**Quy trình sinh challenge (chạy 1 lần/ngày, trước nửa đêm giờ VN):**

1. Chọn 1 đề bài từ ngân hàng riêng `daily_prompts` (bảng ngắn, ví dụ 30-60 đề dạng "viết hàm kiểm tra số nguyên tố", xoay vòng không lặp trong 30 ngày gần nhất) - **không dùng chung bảng `exercises`** vì đề dùng cho daily phải rất ngắn (giải trong 10-20 dòng), khác quy mô bài tập chính.
2. Gọi `MentorClient.chat` với `inject_error=True` và system prompt yêu cầu Ciel: viết lời giải cho đề đã chọn, cài đúng 1 lỗi, rồi trả về kèm JSON metadata `{buggy_line, bug_category, hint_1, hint_2, explanation}` (mở rộng `MENTOR_INJECT_SUFFIX` để ép format JSON, tương tự cách `judge_hypothesis` đã ép JSON ở service hiện tại).
3. Lưu kết quả vào bảng `daily_challenges` (mục 6) khoá theo ngày (unique). Nếu job lỗi/không chạy, endpoint `GET /daily/today` tự sinh on-demand cho ngày đó (lazy fallback) để tính năng không bao giờ "gãy" vì cron.
4. Có 1 endpoint admin thủ công (`POST /daily/regenerate`, cần quyền admin) để tạo lại nếu challenge hôm đó bị lỗi/dễ đoán quá.

---

## 4. Chấm điểm - Tier - Streak

**Tier dựa trên thời gian bắt lỗi + số gợi ý** (ngưỡng cụ thể, có thể tinh chỉnh sau khi có dữ liệu thật):

| Tier | Điều kiện |
|---|---|
| 🟩 Xuất sắc | Đúng dòng lỗi, < 60 giây, 0 gợi ý |
| 🟨 Tốt | Đúng dòng lỗi, dùng ≥ 1 gợi ý HOẶC ≥ 60 giây |
| 🟥 Xem đáp án | Sai dòng lỗi hoặc bấm "Xem đáp án" |

**Streak** = số ngày liên tiếp **có tham gia** (không bắt buộc đúng) - cố tình giống Duolingo/Wordle để không tạo áp lực, tăng giữ chân. Reset về 0 nếu bỏ lỡ 1 ngày theo giờ VN. Streak tính theo **ngày lịch của người dùng** dựa trên header timezone gửi từ client (V1 mặc định `Asia/Ho_Chi_Minh` cho mọi người, ghi chú rõ trong code để mở rộng sau).

**Kết quả chia sẻ (text, kiểu Wordle):**
```
CodeProve Bug Hunt #47 🟩
Bắt lỗi trong 47s, 0 gợi ý
Streak: 12 ngày 🔥
https://code-prove.vercel.app/daily
```

---

## 5. Chơi ẩn danh & vòng lặp tăng trưởng

Đây là phần phục vụ trực tiếp mục tiêu "thu hút lập trình viên cá nhân":

- `/daily` truy cập được **không cần đăng nhập** (route mới trong `codeprove-web/app`, không thuộc `(marketing)` cũng không thuộc khu vực app hiện có vì không có middleware chặn auth - xác nhận không có `middleware.ts` trong repo, mọi gate hiện tại là client-side theo từng trang).
- Khách ẩn danh: streak + lịch sử 30 ngày gần nhất lưu ở `localStorage` (key `codeprove-daily-streak`, cùng pattern với `codeprove-community-posts` đã dùng ở Community).
- Đến streak ngày thứ 3, hiện banner nhẹ "Đăng ký để không mất streak" kèm CTA - không chặn chơi tiếp, chỉ nhắc.
- Khi đăng ký/đăng nhập lần đầu sau khi đã có streak ẩn danh: gọi API merge (`POST /daily/claim-streak` với payload lịch sử localStorage) để chuyển vào tài khoản thật, tránh mất động lực đã tích luỹ.

---

## 6. Data model (backend)

Hai bảng mới, **tách biệt hoàn toàn** khỏi `exercises`/`attempts`/`fluency_reports`:

```python
class DailyChallenge(Base):
    __tablename__ = "daily_challenges"

    id: Mapped[int] = mapped_column(primary_key=True)
    challenge_date: Mapped[date] = mapped_column(Date, unique=True, index=True)
    prompt_title: Mapped[str] = mapped_column(String(255))
    buggy_code: Mapped[str] = mapped_column(Text)
    buggy_line: Mapped[int] = mapped_column(Integer)          # 1-indexed line number
    bug_category: Mapped[str] = mapped_column(String(64))
    hint_1: Mapped[str] = mapped_column(Text)
    hint_2: Mapped[str] = mapped_column(Text)
    explanation: Mapped[str] = mapped_column(Text)             # revealed after submit
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DailyAttempt(Base):
    __tablename__ = "daily_attempts"
    __table_args__ = (UniqueConstraint("user_id", "challenge_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    challenge_date: Mapped[date] = mapped_column(Date, index=True)
    selected_line: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hints_used: Mapped[int] = mapped_column(Integer, default=0)
    time_taken_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tier: Mapped[str | None] = mapped_column(String(16), nullable=True)  # green|yellow|red
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

Streak **không lưu như 1 cột riêng** - tính động từ `DailyAttempt` (đếm ngày liên tiếp có bản ghi `submitted_at` không NULL tính lùi từ hôm nay), tránh lệch dữ liệu nếu có sửa/xoá thủ công sau này. `daily_prompts` (ngân hàng đề) là 1 bảng tĩnh đơn giản hoặc file seed, quyết định cụ thể để ở giai đoạn lên plan.

---

## 7. API endpoints (sơ bộ, đúng theo pattern `features/<domain>/router.py` hiện có)

| Method | Path | Auth | Mô tả |
|---|---|---|---|
| GET | `/daily/today` | Không bắt buộc | Trả challenge hôm nay (không kèm `buggy_line`/`explanation` cho tới khi submit), + trạng thái attempt của user nếu đã đăng nhập và đã chơi |
| POST | `/daily/attempt` | Không bắt buộc (user_id null nếu ẩn danh - nhưng ẩn danh không ghi DB, chỉ trả kết quả để client tự lưu localStorage) | Nộp `{selected_line, hints_used, time_taken_seconds}`, trả về `{correct, tier, buggy_line, explanation, streak}`. `time_taken_seconds` do client tự đo (từ lúc render xong đến lúc bấm Nộp) và gửi lên - **không có xác thực phía server**, chấp nhận được vì kết quả này không ảnh hưởng Fluency/Integrity Score chính thức (mục 1), chỉ ảnh hưởng tier hiển thị cho vui. Với request ẩn danh, `streak` trả về `null` (server không có state để tính, client tự tính từ localStorage) |
| POST | `/daily/claim-streak` | Bắt buộc | Nhận lịch sử từ localStorage, ghi nhận vào `daily_attempts` cho các ngày chưa có bản ghi |
| POST | `/daily/regenerate` | Admin | Sinh lại challenge hôm nay (vận hành) |

---

## 8. Frontend (sơ bộ)

- Route mới `codeprove-web/app/daily/page.tsx` (không lồng trong `(marketing)` layout để giữ nhẹ, không lồng trong app-shell hiện có vì không cần `AppTopNav` đầy đủ tính năng workspace).
- Component chính `DailyBugHunt.tsx` quản lý 5 trạng thái ở mục 2 bằng 1 state machine đơn giản (không cần thư viện state machine mới, dùng `useState` như các component hiện có).
- Dùng lại `SolveWorkspace`'s cách hiển thị code có số dòng (line gutter) nếu tái dùng được, nhưng **không tái dùng textarea có thể sửa code** - ở đây code chỉ đọc, người dùng chỉ click chọn dòng.
- i18n: thêm khối `dailyBugHunt` vào `lib/content.ts` (áp dụng đúng bài học từ lỗi trước: dùng `key={i}` chứ không phải key theo text nếu có danh sách locale-dependent trong animation reveal).

---

## 9. Rủi ro & câu hỏi mở (để làm rõ khi lên plan)

- **Chất lượng lỗi do Ciel sinh ra**: cần rào chắn để lỗi không quá hiển nhiên (ai cũng thấy ngay) hoặc quá mơ hồ (không ai bắt được) - cần vài vòng thử nghiệm prompt trước khi launch thật, nên seed sẵn 5-10 challenge "an toàn" viết tay cho tuần đầu tiên trong lúc tinh chỉnh prompt.
- **Chi phí OpenAI**: 1 lần gọi/ngày (không phải mỗi user) nên chi phí không đáng kể, khác hẳn chi phí Ciel chat hiện tại.
- **Giờ reset ngày**: cố định `Asia/Ho_Chi_Minh` ở V1; nếu sau này có user quốc tế cần tính theo timezone riêng, đây là điểm cần sửa đầu tiên.
- **Phạm vi triển khai**: đây là tính năng full-stack 2 repo (`codeprove-backend` + `codeprove-web`). Khi lên plan, nên tách thành **2 plan độc lập** - plan backend (model, migration, job sinh nội dung, 4 endpoint) làm trước và merge trước, plan frontend (route `/daily`, component, i18n) làm sau vì phụ thuộc API contract đã chốt ở plan backend. Mỗi plan vẫn cho ra phần mềm chạy/test được độc lập (backend có thể test qua Swagger/pytest trước khi frontend tồn tại).
