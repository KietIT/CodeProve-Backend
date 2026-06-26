# CodeProve Backend — Design Spec

**Phiên bản:** v1.0 (build-ready) · **Ngày:** 2026-06-26
**Phạm vi:** Backend cho website CodeProve + nối dây frontend `codeprove-web` để mọi nút chạy thật end-to-end.
**Nguồn:** `feat/CodeProve - Build Specification.docx` (v2.0), `feat/ERD.png` + `feat/ERD.txt`, frontend hiện có trong `codeprove-web`.

Quy ước: prose tiếng Việt; mọi code/identifier/tên bảng/endpoint bằng tiếng Anh.

---

## 0. Quyết định đã chốt

| Hạng mục | Lựa chọn |
|---|---|
| AI Mentor | **OpenAI GPT** (LLM thật), model mặc định `gpt-4o-mini`, cấu hình qua env |
| Code execution | **Subprocess sandbox** (timeout + giới hạn), chừa interface nâng lên Docker sau |
| Database | **PostgreSQL local/Docker** + SQLAlchemy 2.0 (async) + Alembic |
| Phạm vi | **Phase 1 đầy đủ 6 trục**, auth JWT thật, event stream thật, anti-cheat mức cơ bản |
| Backend stack | **FastAPI** (async) + Pydantic v2 |
| Rule Engine | **Pragmatic YAML rules** (editable, no redeploy) — KHÔNG full DSL lexer/parser ở Phase 1 |
| Editor frontend | Textarea nâng cao (line-number + overlay tokenizer sẵn có), không thêm CodeMirror |
| Login | bằng `email` + `password` |

Out of scope Phase 1 (đẩy sang Phase 2): full DSL lexer/parser/interpreter + safe-regex + hot-reload Rule Editor; SSO Google/GitHub (ẩn/disable, không để nút chết); Docker execution sandbox; ngôn ngữ ngoài Python; cổng B2B trường/nhà tuyển dụng; biến thể động (dynamic variants) của đề bài.

---

## 1. Mục tiêu & nguyên tắc

- Người dùng **đăng ký/đăng nhập thật**, làm bài trong workspace, **hỏi đáp với AI Mentor thật**, **chạy test thật**, **được chấm 6 trục thật**, xem **feedback + dashboard dữ liệu thật**.
- **Nguyên tắc sống còn (spec):** điểm gắn với **QUÁ TRÌNH quan sát được** (event stream), không gắn với kết quả code. Vì vậy "hỏi AI ngoài rồi dán code" vô nghĩa.
- **Event stream append-only là nguồn sự thật duy nhất** cho cả chấm điểm lẫn chống gian lận (spec §3, NFR-4). Scoring Engine là **hàm thuần** đọc từ event stream → có thể replay/chạy lại bất kỳ lúc nào.

---

## 2. Tech stack & cấu trúc thư mục

Thư viện: `fastapi`, `uvicorn[standard]`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `pydantic`, `pydantic-settings`, `python-jose[cryptography]`, `passlib[bcrypt]`, `openai`, `httpx`, `pyyaml`, `python-multipart`; dev: `pytest`, `pytest-asyncio`.

```
codeprove-backend/
├── app/
│   ├── main.py                    # FastAPI app, CORS, mount routers, startup seed
│   ├── core/
│   │   ├── config.py              # Settings (.env qua pydantic-settings)
│   │   ├── db.py                  # async engine + session, Base
│   │   ├── security.py            # hash password, create/verify JWT
│   │   └── deps.py                # get_db, get_current_user
│   ├── models/                    # SQLAlchemy models (1 file / bảng)
│   ├── schemas/                   # Pydantic request/response (theo feature)
│   ├── features/
│   │   ├── auth/router.py service.py
│   │   ├── exercises/router.py service.py
│   │   ├── attempts/router.py service.py     # attempt, events, snapshots
│   │   ├── mentor/router.py service.py client.py   # OpenAI + guardrail
│   │   ├── scoring/engine.py rules_loader.py features.py   # Scoring + Rule Engine
│   │   ├── sandbox/runner.py      # subprocess execution
│   │   └── dashboard/router.py service.py
│   ├── rules/                     # *.yaml — 1 file / trục
│   │   ├── understanding.yaml hypothesis.yaml prompting.yaml
│   │   └── verification.yaml testing.yaml debugging.yaml
│   └── seed/exercises_seed.py     # đề bài + testcases (từ lib/exercises.ts)
├── tests/                         # pytest: scoring engine, sandbox, rule loader
├── alembic/  alembic.ini
├── docker-compose.yml             # chỉ Postgres
├── .env.example  requirements.txt  README.md
```

---

## 3. Mô hình dữ liệu

Giữ nguyên 8 bảng ERD, bổ sung cột + 1 bảng mới `events`. Kiểu cột PostgreSQL.

### 3.1 `users`
`id (PK)`, `full_name`, `email (unique, index)`, `password_hash`, `created_at`.

### 3.2 `exercises`
ERD: `id, title, difficulty, category, description, learning_objective`.
Thêm: `level` (`fresher|junior|senior`), `language` (default `python`), `acceptance` (float, hiển thị UI), `summary`, `starter_code`, `hint`, `domain_keywords` (JSONB — cho luật P3), `reference_solution` (nullable), `buggy_location` (nullable — bài debug), `verification_trap` (bool, default false — bật injected-error cho Verification), `created_at`.

### 3.3 `test_cases`
ERD: `id, exercise_id (FK), input_data, expected_output, weight, description`.
Thêm: `is_hidden` (bool, default true), `order_index` (int).

### 3.4 `attempts`  *(= "session" của spec)*
ERD: `id, user_id (FK), exercise_id (FK), score`.
Thêm: `status` (`in_progress|submitted|scored`), `integrity_status` (`green|yellow|red`, nullable), `started_at`, `submitted_at` (nullable), `created_at`.

### 3.5 `events`  *(MỚI — telemetry append-only, spec §3)*
`id (PK)`, `attempt_id (FK, index)`, `type` (enum text), `ts` (bigint, epoch ms), `payload` (JSONB), `integrity_flags` (JSONB, default `[]`), `created_at`.
`type` ∈ `OPEN | PROMPT | AI_REPLY | CODE_EDIT | RUN | TEST_RUN | PASTE | FOCUS_LOST | HYPOTHESIS | EXPLAIN_BACK | SUBMIT`.
`payload` theo `CPEvent.payload` của spec (messageText, messageLength, keywordsMatched, promptTokens, completionTokens, aiCode, userCode, injectedError, editedFiles, charsAdded, charsDeleted, keystrokeGaps, passed, testCount, coverage, proposedBy, correct, explainScore, totalElapsed). **Append-only** — không update/delete.

### 3.6 `code_snapshots`
ERD: `id, attempt_id (FK), version, source_code, created_at`. Lưu mỗi lần user save/run.

### 3.7 `prompt_logs`
ERD: `id, attempt_id (FK), prompt, response, model, tokens, created_at`. Lưu mỗi lượt chat AI Mentor.

### 3.8 `verification_answers`
ERD: `id, attempt_id (FK), question, answer, score`. Lưu Q&A explain-back/verification trap.

### 3.9 `fluency_reports`
ERD: `id, attempt_id (FK, unique), understanding_score, prompt_score, verification_score, debugging_score, testing_score, explanation_score, overall_score, feedback, created_at`.
Thêm: **`hypothesis_score`** (ERD thiếu trục Hypothesis). Mapping 6 trục (mỗi trục lưu thang **0–20**):
- `understanding_score` → Understanding
- `hypothesis_score` → Hypothesis *(mới)*
- `prompt_score` → Prompting
- `verification_score` → Verification
- `testing_score` → Testing (nullable nếu trục tắt)
- `debugging_score` → Debugging (nullable nếu trục tắt)
- `explanation_score` → giữ lại = điểm explain-back thô (0–20, đầu vào của Understanding)
- `overall_score` → 0–100
- `feedback` (JSONB) → `{ strengths:[], risks:[], per_axis:{axis:{score,notes[]}} , tier }`

---

## 4. Telemetry — frontend bắn gì

Frontend (`/workspace/solve`) phát event về `POST /attempts/{id}/events` (batch, debounce) hoặc qua endpoint chuyên biệt:

| Hành vi user | Event | Field chính | Phục vụ trục |
|---|---|---|---|
| Mở bài | `OPEN` | ts | Understanding (firstPromptDelay) |
| Gõ code | `CODE_EDIT` | charsAdded/Deleted, keystrokeGaps | Debugging, anti-cheat |
| Paste | `PASTE` | length, speed → `integrity_flags:[BURST_PASTE]` | anti-cheat |
| Rời tab/blur | `FOCUS_LOST` | duration → `[TAB_SWITCH]` | anti-cheat |
| Gửi prompt | `PROMPT` | messageText, messageLength, keywordsMatched, promptTokens | Prompting |
| AI trả lời | `AI_REPLY` | completionTokens, aiCode[{loc}], injectedError | Verification, Understanding (U2) |
| Log hypothesis | `HYPOTHESIS` | proposedBy, correct (LLM chấm) | Hypothesis |
| Run/Test | `RUN`/`TEST_RUN` | passed, testCount, coverage | Debugging, Testing, Verification |
| Submit | `SUBMIT` | ts | mốc khoá phiên |
| Explain-back | `EXPLAIN_BACK` | explainScore (LLM chấm 0–20) | Understanding (U3) |

`firstPromptDelay` = ts(PROMPT đầu) − ts(OPEN). `problemReadRatio` ước lượng từ thời gian active trước prompt đầu (frontend gửi kèm). `totalElapsed` = khoảng cách ms tới event kế tiếp (tính server-side khi cần).

---

## 5. Scoring Engine — 6 trục (công thức đã chốt)

Pipeline: `events[] → aggregate features → áp rules (YAML) → axis_i ∈ [0,20] → Score = 5·Σ(weight_i·axis_i)`.

Weights (chốt): Understanding **0.25** · Hypothesis **0.22** · Prompting **0.18** · Verification **0.15** · Testing **0.10** · Debugging **0.10** (Σ=1.00). Nếu Testing/Debugging = null → chuẩn hoá lại 4 trục còn lại để Σ=1.

### 5.1 Understanding
Rules: `U1 rushed-start` (firstPromptDelay<20s AND problemReadRatio<0.6 → −3); `U2 explain-again` (mỗi AI_REPLY giải thích khái niệm cơ bản → −2, trần tổng −8); `U3 explain-back` (explainScore 0–20 sau SUBMIT).
```
Understanding = clamp(0, 20, 0.6*explainScore + 0.4*(20 - (U1_pen + U2_pen)))
```

### 5.2 Hypothesis
Rules: `H1 user-correct` (HYPOTHESIS.proposedBy=='user' AND correct → +4/giả thuyết, trần 20); `H2 ai-rescue` (AI phải tự nêu vì user không nêu được → −4/lần); `H3 no-plan` (SUBMIT mà không có HYPOTHESIS nào trước CODE_EDIT đầu tiên → trần trục = 10).
```
base = 8
Hypothesis = clamp(0, H3 ? 10 : 20, base + 4*count(H1) - 4*count(H2))
```

### 5.3 Prompting
Rules: `P1 lazy-prompt` (0<messageLength<30 → −2/prompt; nếu ratio>0.3 → trần 12); `P2 repeated` (near-duplicate ≥3 lần, fuzzy ngưỡng 0.85 → −3/cụm); `P3 keyword-fit` (count(keywordsMatched)≥2 cho prompt trọng tâm → +2/prompt tốt, trần +8); `P4 no-constraint` (prompt không nêu ràng buộc/định dạng → −1).
```
Prompting = clamp(0, P1_ratio>0.3 ? 12 : 20,
                  14 + 2*count(P3) - 2*count(P1) - 3*count(P2) - 1*count(P4))
```
Near-duplicate: dùng similarity (vd `difflib.SequenceMatcher` ratio ≥ 0.85).

### 5.4 Verification
Rules: `V1 trap-caught` (AI_REPLY.injectedError==true VÀ user sửa trước SUBMIT → +8); `V1b trap-missed` (injectedError nhưng RUN/SUBMIT thẳng không sửa → −8); `V2 speed-accept` (aiCode.loc≥20 VÀ event kế tiếp <15s → −4/lần); `V3 paste-blind` (tổng aiCode.loc≥50 mà không có CODE_EDIT/refine theo sau → −5).
```
Verification = clamp(0, 20, 12 + 8*hasV1 - 8*hasV1b - 4*count(V2) - 5*hasV3)
```

### 5.5 Testing  (enabled ở Phase 1)
Rules: `T1 has-tests` (mỗi test hợp lệ user viết → +4, trần 20); `T2 coverage` (coverage≥0.7 trên bài có nhánh → +4); `T0 none` (không TEST_RUN nào trước SUBMIT → trục=0).
```
Testing = enabled ? clamp(0, 20, 4*count(T1) + (coverage>=0.7 ? 4 : 0)) : null
```

### 5.6 Debugging  (enabled ở Phase 1)
Rules: `D1 fix-success` (sau passed=false user tự sửa đạt passed=true → +6/vòng, trần 20); `D2 ai-dependent` (mỗi lỗi đều nhờ AI sửa hộ hoàn toàn → −4).
```
Debugging = enabled ? clamp(0, 20, 8 + 6*count(D1) - 4*count(D2)) : null
```

### 5.7 Thời điểm chấm
Chấm **đồng bộ khi `POST /explain-back`** (sau SUBMIT + explain-back): đọc toàn bộ events của attempt → tính 6 trục → ghi `fluency_reports` + cập nhật `attempts.score`, `status='scored'`, `integrity_status`. Vì là hàm thuần trên event stream nên thoả "async/replayable" của spec (có thể re-run).

---

## 6. Rule Engine (pragmatic, YAML)

Mỗi trục có 1 file `app/rules/<axis>.yaml`. Loader đọc tại startup (và reload khi gọi tay) → đổi ngưỡng/effect **không sửa code lõi**. Engine cài sẵn các "detector" tương ứng từng rule id; YAML chỉ cấp **thresholds + effect**, không phải ngôn ngữ tổng quát.

Ví dụ `prompting.yaml`:
```yaml
- id: P1-lazy-prompt
  axis: prompting
  severity: medium
  thresholds: { minChars: 30, maxRatio: 0.3 }
  effect: { perHit: -2, capScoreIfRatio: 12 }
- id: P3-keyword-fit
  axis: prompting
  thresholds: { minKeywords: 2 }
  effect: { perHit: 2, cap: 8 }
```
Engine: `load_rules() -> dict[axis, list[Rule]]`; mỗi axis có hàm `score_axis(features, rules) -> float`. Đây là điểm để Phase 2 thay bằng full DSL mà không đổi interface.

---

## 7. AI Mentor (OpenAI)

- Client `features/mentor/client.py` gọi OpenAI Chat Completions (model env `OPENAI_MODEL`, default `gpt-4o-mini`). Timeout đảm bảo NFR-3 (<3s p95); fallback message khi lỗi/timeout.
- **System prompt — ràng buộc cứng** (spec §7, §11): xưng "Ciel"; trả lời theo locale (vi/en); chỉ gợi ý tư duy/đặt câu hỏi ngược; **không bao giờ trả về lời giải hoàn chỉnh chạy được**, kể cả khi bị prompt mồi (T5) → từ chối lịch sự + hướng từng bước; gắn cờ Integrity khi phát hiện prompt mồi.
- **Injected error (verification trap, V1/V1b):** đề bài có cờ `verification_trap` (cột trên `exercises`). Khi bật, lần đầu user xin gợi ý dạng code, mentor trả snippet **có lỗi tinh vi cố ý** (qua một tham số system prompt) và backend set `injectedError=true` trong event AI_REPLY + lưu prompt_logs. Mỗi attempt tối đa 1 lần injected để dễ kiểm chứng (V1/V1b xác định, không ngẫu nhiên).
- **Hypothesis check:** `POST /hypothesis` → LLM trả JSON `{correct: bool, note}` → ghi event HYPOTHESIS{proposedBy:'user', correct}.
- **Explain-back scoring:** `POST /submit` → LLM sinh 1–2 câu hỏi explain-back dựa trên code + lịch sử → user trả lời ở `POST /explain-back` → LLM chấm JSON `{score: 0..20, reason}` → event EXPLAIN_BACK{explainScore} + verification_answers.
- Mọi lượt sinh event PROMPT/AI_REPLY kèm `messageLength, keywordsMatched (so khớp domain_keywords của đề), promptTokens, completionTokens`.

---

## 8. Sandbox — subprocess runner

- `features/sandbox/runner.py`: nhận `source_code` + danh sách `test_cases`; chạy code user trong **subprocess Python riêng** với `timeout` (env `SANDBOX_TIMEOUT`, default 5s), giới hạn output, chặn import nguy hiểm cơ bản (block-list: `os.system`, `subprocess`, `socket`, `open` ghi tuỳ chọn) ở mức MVP.
- Chấm từng test case: so `stdout`/giá trị trả về với `expected_output` (weight tính coverage). Trả `{passed, total, coverage, cases:[{name, passed, stdout, error}]}`.
- Ghi event RUN (chạy thường) / TEST_RUN (có testCount, coverage, passed) + tạo `code_snapshots`.
- Interface tách biệt để Phase 2 thay bằng Docker mà không đổi caller.

---

## 9. API surface (`/api`)

Auth header: `Authorization: Bearer <jwt>` cho mọi endpoint trừ signup/login.

| Method | Path | Body → Response | Nút frontend |
|---|---|---|---|
| POST | `/auth/signup` | `{full_name,email,password}` → `{user, access_token}` | AuthPanel signup |
| POST | `/auth/login` | `{email,password}` → `{user, access_token}` | AuthPanel login |
| GET | `/auth/me` | → `{user}` | guard app |
| GET | `/exercises` | `?level=` → `[{level, exercises:[summary fields]}]` | level picker |
| GET | `/exercises/{id}` | → exercise detail (summary, starter, hint, tests, topics, difficulty, rubric) | solve brief |
| POST | `/attempts` | `{exercise_id}` → `{attempt_id, started_at}` (+event OPEN) | vào solve |
| GET | `/attempts/{id}` | → attempt state + latest snapshot | resume |
| POST | `/attempts/{id}/events` | `{events:[CPEvent]}` → `{ok}` | telemetry batch |
| POST | `/attempts/{id}/snapshots` | `{version, source_code}` → `{ok}` | save |
| POST | `/attempts/{id}/run` | `{source_code, run_tests:bool}` → run result | "Run tests" |
| POST | `/attempts/{id}/hypothesis` | `{text}` → `{correct, note}` | "Log hypothesis" |
| POST | `/attempts/{id}/mentor` | `{message}` → `{reply, injected_error}` | chat Ciel |
| POST | `/attempts/{id}/submit` | → `{explain_back: {questions:[]}}` | "Submit" (mở modal) |
| POST | `/attempts/{id}/explain-back` | `{answers:[{question,answer}]}` → `{report}` | modal explain-back |
| GET | `/attempts/{id}/report` | → FluencyReport (6 trục, feedback, integrity, timeline) | trang Feedback |
| GET | `/dashboard` | → `{kpis, radar[6], trend[], recent_attempts[]}` | trang Dashboard |

---

## 10. Nối dây frontend (`codeprove-web`)

- `lib/api.ts`: fetch wrapper đọc `NEXT_PUBLIC_API_URL`, đính JWT; helper cho từng endpoint. JWT lưu cookie/localStorage; auth context (`lib/auth.tsx`) cung cấp user + guard route app.
- `AuthPanel.tsx`: thay `setTimeout` giả bằng gọi `/auth/signup|login`, lưu token, điều hướng `/dashboard`; hiển thị lỗi server.
- `/workspace/solve/page.tsx` → tách phần tương tác thành **client component**:
  - Editor **gõ được** (controlled textarea + line-number + overlay tokenizer `tokenizeLine` sẵn có).
  - `POST /attempts` khi mở; theo dõi CODE_EDIT (debounce), PASTE (clipboard event + flag), FOCUS_LOST (`visibilitychange`/`blur`).
  - "Run tests" → `/run`, render kết quả thật ở Test runner.
  - "Log hypothesis" → `/hypothesis`, hiển thị xác nhận đúng/sai.
  - Chat Ciel + prompt suggestions → `/mentor`, render hội thoại; đánh dấu khi có injected_error.
  - "Submit" → `/submit` → modal explain-back → `/explain-back` → điều hướng `/feedback?attempt=<id>`.
- `/feedback/page.tsx`: đọc `?attempt=` → `GET /attempts/{id}/report`, render score ring + 6 trục + timeline + strengths/risks + integrity badge từ dữ liệu thật.
- `/dashboard/page.tsx`: `GET /dashboard` → KPIs, radar, trend, recent attempts thật.
- `lib/exercises.ts`: giữ làm seed + fallback; frontend ưu tiên fetch `GET /exercises`.
- SSO Google/GitHub: ẩn hoặc gắn tooltip "Coming soon" (không để nút chết).

---

## 11. Cấu hình, bảo mật, anti-cheat

- `.env`: `DATABASE_URL`, `JWT_SECRET`, `JWT_EXPIRE_MINUTES`, `OPENAI_API_KEY`, `OPENAI_MODEL`, `CORS_ORIGINS`, `SANDBOX_TIMEOUT`.
- Mật khẩu hash bcrypt (passlib); JWT HS256; CORS cho `http://localhost:3000`.
- **Anti-cheat Phase 1 (mức cơ bản):** ghi PASTE (length/speed), FOCUS_LOST → `integrity_flags`. Tính **Integrity Score 3 mức**: green (sạch) / yellow (vài tín hiệu: paste lớn, mất focus) / red (nhiều tín hiệu trùng). **Chỉ gắn cờ, không tự đánh trượt** (spec §6.3) → `attempts.integrity_status`, hiện badge ở report.

---

## 12. Tiêu chí nghiệm thu (Definition of Done — spec §11.2)

- [ ] Event stream ghi đủ & replay được phiên làm bài (`events` append-only).
- [ ] Scoring Engine chấm 6 trục đúng công thức Mục 5; xuất radar + feedback.
- [ ] Rule Engine nạp luật `.yaml`, đổi ngưỡng không cần sửa code lõi.
- [ ] Phát hiện & gắn cờ tối thiểu T1 (paste) – T2 (tab switch); Integrity Score 3 mức.
- [ ] Verification-trap & explain-back hoạt động: người dán code ngoài không đạt Understanding/Verification cao.
- [ ] AI Mentor không trả lời nguyên lời giải hoàn chỉnh khi bị prompt mồi (T5).
- [ ] Frontend: mọi nút (auth, run, hypothesis, chat, submit→explain-back, feedback, dashboard) chạy thật end-to-end.

---

## 13. Thứ tự build (tăng dần, test được từng bước)

1. **Scaffold**: project, config, `db.py`, models, Alembic init + migration, seed exercises/testcases, `docker-compose` Postgres, `main.py` chạy được + `/health`.
2. **Auth**: signup/login/me + security → nối `AuthPanel`.
3. **Exercises API** → nối level picker + solve brief (frontend fetch).
4. **Attempt + events + snapshots + sandbox run** → nối editor gõ được + "Run tests" thật.
5. **AI Mentor (OpenAI) + hypothesis** → nối chat Ciel + "Log hypothesis".
6. **Scoring + Rule Engine + submit/explain-back** → sinh FluencyReport (+ pytest cho engine).
7. **Report + Dashboard API** → nối trang Feedback + Dashboard.
8. **Anti-cheat cơ bản + Integrity** → badge + pass toàn bộ DoD Mục 12.

---

## Phụ lục — Ghi nhận nguồn

Lớp đo lường (rubric 6 trục, penalty-based scoring, telemetry schema, ý tưởng rule-as-data) nội hoá từ repo MIT `microsoft/AI-Engineering-Coach`. CodeProve tự viết lại thuật toán (không copy nguyên file) nên không ràng buộc attribution; nếu sau này copy nguyên file luật/code sẽ kèm header MIT của Microsoft.
