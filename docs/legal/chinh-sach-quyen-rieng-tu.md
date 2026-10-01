# Chính sách quyền riêng tư — CodeProve

> **BẢN NHÁP, chưa công bố.** Phiên bản `2026-10`. Nhóm cần duyệt; nếu có thể, nên nhờ người có chuyên môn pháp lý xem theo Nghị định 13/2023/NĐ-CP. Các chỗ **[NHÓM ĐIỀN: …]** phải được quyết định trước khi đăng. Bản này mô tả đúng hệ thống tại thời điểm viết (sau P3.7); khi hệ thống đổi thì phải sửa văn bản và tăng `POLICY_VERSION`.

## Tiếng Việt

**Cập nhật lần cuối:** [NHÓM ĐIỀN: ngày công bố] · **Phiên bản:** 2026-10

CodeProve là nền tảng luyện và đánh giá kỹ năng lập trình có trợ lý AI (Ciel). Chính sách này giải thích chúng tôi thu thập dữ liệu gì, dùng để làm gì, chia sẻ với ai và bạn có những quyền gì.

**Bên kiểm soát dữ liệu:** nhóm phát triển CodeProve, [NHÓM ĐIỀN: tên nhóm / tổ chức, địa chỉ]. Liên hệ về quyền riêng tư: **trinhkiet2005@gmail.com**.

### 1. Dữ liệu chúng tôi thu thập

| Nhóm dữ liệu | Gồm những gì | Lấy từ đâu |
|---|---|---|
| Tài khoản | Họ tên, email, mật khẩu (chỉ lưu dạng băm, không đọc được), ảnh đại diện (nếu bạn tải lên) | Bạn nhập khi đăng ký, hoặc Google gửi (tên, email) khi bạn đăng nhập bằng Google |
| Quá trình làm bài | Code bạn viết (các bản lưu tự động), các lần chạy và nộp, test bạn viết, các bước khi tìm lỗi (dòng bạn chọn, lời giải thích), giả thuyết và câu trả lời explain-back | Trong lúc bạn làm bài |
| Tín hiệu làm bài | Thời điểm các thao tác, việc dán nội dung từ ngoài vào, rời khỏi trang hoặc thoát toàn màn hình trong khi làm bài | Trình duyệt gửi trong lúc bạn làm bài, dùng cho phần điểm về tính trung thực |
| Trò chuyện với Ciel | Câu hỏi bạn gửi và câu trả lời bạn đã thấy | Trong lúc bạn dùng Ciel |
| Kết quả | Điểm theo 6 trục, báo cáo và nhận xét, điểm kỹ năng (Elo) theo từng kỹ năng, lịch sử bài đã làm, Daily Bug Hunt | Hệ thống tính từ quá trình làm bài |
| Kỹ thuật | Số token mỗi lần gọi AI (không có nội dung), thời gian; token đăng nhập lưu trong trình duyệt của bạn | Hệ thống tự ghi |

Chúng tôi không thu thập số CMND/CCCD, thông tin thanh toán, vị trí hay danh bạ. [NHÓM ĐIỀN: nếu sau này có thanh toán, phải bổ sung mục này.]

### 2. Mục đích sử dụng

- Cho bạn làm bài, chạy code và nhận phản hồi.
- Chấm điểm quá trình giải bài và viết nhận xét.
- Ciel trả lời câu hỏi trong lúc bạn làm bài.
- Cá nhân hoá:
  - gợi ý bài tiếp theo và trang Tiến độ (tính trên máy chủ của chúng tôi);
  - nếu bạn bật **Cá nhân hoá AI**, Ciel nhận một bản tóm tắt ngắn về kỹ năng mạnh/yếu của bạn (không có tên, email, code hay nội dung trò chuyện).
- Cải thiện chất lượng chấm điểm. Thành viên nhóm chấm lại một số phiên làm bài dưới dạng ẩn danh hoá: thay tài khoản bằng mã ngẫu nhiên, xoá email và số điện thoại khỏi nội dung.
- Kiểm soát chi phí và chống lạm dụng (giới hạn số tin nhắn với Ciel).

Chúng tôi **không bán** dữ liệu của bạn và **không dùng** nó để quảng cáo.

### 3. Bên thứ ba xử lý dữ liệu

| Bên | Vai trò | Dữ liệu nhận được |
|---|---|---|
| **OpenAI** (Hoa Kỳ) | Mô hình AI cho Ciel, chấm câu trả lời và viết nhận xét | Đề bài; nội dung bạn viết (câu hỏi, code, giả thuyết, câu trả lời). Trước khi gửi, chúng tôi xoá email, số điện thoại và họ tên đầy đủ của bạn khỏi nội dung. Chúng tôi không gửi tên tài khoản, email hay mã người dùng của bạn. Mọi yêu cầu đều đặt chế độ `store=false`, tức không cho OpenAI lưu lại để huấn luyện hay đánh giá. [NHÓM ĐIỀN: kiểm tra và dẫn link điều khoản dữ liệu API hiện hành của OpenAI.] |
| **Amazon Web Services** | Máy chủ và cơ sở dữ liệu, bản sao lưu | Toàn bộ dữ liệu ở mục 1 (lưu trữ) |
| **Cloudflare** | Đường truyền từ internet tới máy chủ | Lưu lượng truy cập (đã mã hoá HTTPS) |
| **Google** | Đăng nhập bằng Google (nếu bạn chọn) | Google xác thực bạn và gửi lại tên, email |
| [NHÓM ĐIỀN: nơi chạy frontend] | Phục vụ giao diện web | Lưu lượng truy cập |

**Chuyển dữ liệu ra nước ngoài:** dữ liệu được xử lý tại máy chủ ở [NHÓM ĐIỀN: khu vực AWS] và tại OpenAI ở Hoa Kỳ. Khi đồng ý với chính sách này, bạn đồng ý việc chuyển dữ liệu đó cho các mục đích ở mục 2. [NHÓM ĐIỀN: thủ tục hồ sơ đánh giá tác động chuyển dữ liệu ra nước ngoài theo Nghị định 13, nếu áp dụng.]

### 4. Thời gian lưu trữ

[NHÓM ĐIỀN: quyết định cụ thể. Đề xuất để thảo luận:]
- Dữ liệu tài khoản và kết quả: lưu trong thời gian tài khoản còn hoạt động.
- Quá trình làm bài chi tiết (sự kiện, các bản lưu code): 12 tháng kể từ khi tạo.
- Bản sao lưu cơ sở dữ liệu: [số] ngày.
- Khi bạn yêu cầu xoá tài khoản, chúng tôi xoá trong vòng 30 ngày. Bản sao lưu cũ tự hết hạn theo thời gian trên.

### 5. Quyền của bạn

Bạn có quyền:
- được biết về việc xử lý dữ liệu;
- đồng ý hoặc rút lại đồng ý;
- xem và nhận bản sao dữ liệu;
- yêu cầu sửa hoặc xoá;
- hạn chế hoặc phản đối việc xử lý;
- khiếu nại theo quy định pháp luật.

Cách thực hiện:
- **Tắt Cá nhân hoá AI:** tự làm ở trang Hồ sơ, có hiệu lực ngay.
- **Sửa họ tên:** tự làm ở trang Hồ sơ.
- **Xem, nhận bản sao, xoá tài khoản, rút lại đồng ý:** hiện tại gửi email tới **trinhkiet2005@gmail.com** từ email tài khoản của bạn. Chúng tôi phản hồi trong vòng [NHÓM ĐIỀN: số] ngày. Nếu bạn rút lại đồng ý, các tính năng AI (Ciel, chấm điểm explain-back) sẽ ngừng hoạt động với tài khoản của bạn; phần luyện code khác vẫn dùng được.

### 6. Bảo mật

- Kết nối được mã hoá HTTPS.
- Mật khẩu được băm.
- Code của bạn chạy trong môi trường cách ly.
- Cơ sở dữ liệu chỉ truy cập được từ bên trong máy chủ.
- Chỉ thành viên vận hành được truy cập dữ liệu, và chỉ khi cần.

Không hệ thống nào an toàn tuyệt đối. Nếu xảy ra sự cố lộ dữ liệu, chúng tôi sẽ thông báo cho bạn và cơ quan có thẩm quyền theo quy định.

### 7. Trẻ em

[NHÓM ĐIỀN: độ tuổi tối thiểu. Nghị định 13 yêu cầu sự đồng ý của cha mẹ hoặc người giám hộ với trẻ em dưới 16 tuổi; nếu không hỗ trợ việc này, ghi rõ "CodeProve dành cho người từ 16 tuổi".]

### 8. Thay đổi chính sách

Khi chính sách thay đổi, chúng tôi cập nhật phiên bản và hỏi lại sự đồng ý của bạn trước khi bạn dùng tiếp các tính năng AI.

---

## English

**Last updated:** [TEAM: publication date] · **Version:** 2026-10

CodeProve is a platform for practising and assessing programming skills with an AI assistant (Ciel). This policy explains what data we collect, why, who we share it with, and your rights.

**Data controller:** the CodeProve team, [TEAM: name / organisation, address]. Privacy contact: **trinhkiet2005@gmail.com**.

### 1. Data we collect

| Category | What | Source |
|---|---|---|
| Account | Name, email, password (stored only as a hash), avatar (if you upload one) | You, at sign-up; or Google (name, email) when you sign in with Google |
| Work on exercises | Your code (autosaved versions), runs and submissions, the tests you write, debugging steps (lines you pick, your explanation), hypotheses and explain-back answers | While you work |
| Session signals | Timing of actions; pasting from outside, leaving the page or exiting full screen during an exercise | Your browser, for the integrity part of the score |
| Ciel chat | The questions you send and the replies you saw | While you use Ciel |
| Results | Scores on 6 axes, reports and feedback, per-skill ratings (Elo), exercise history, Daily Bug Hunt | Computed from your work |
| Technical | Token counts of each AI call (no content), timestamps; the sign-in token stored in your browser | Logged automatically |

We do not collect ID numbers, payment data, location or contacts. [TEAM: add a section if payments are added.]

### 2. Why we use it

- To let you solve exercises, run code and get feedback.
- To score how you solved the exercise and write feedback.
- For Ciel to answer your questions while you work.
- Personalisation:
  - next-exercise suggestions and the Progress page (computed on our server);
  - if **AI personalisation** is on, Ciel receives a short summary of your strong and weak skills (no name, email, code or chat).
- To improve scoring. Team members re-rate some sessions in pseudonymised form: accounts are replaced by random keys, and emails and phone numbers are removed from the text.
- Cost control and abuse prevention (limits on Ciel messages).

We do **not sell** your data and do **not use** it for advertising.

### 3. Processors

| Party | Role | Data received |
|---|---|---|
| **OpenAI** (USA) | AI model for Ciel, answer scoring and feedback writing | The exercise, and what you wrote (questions, code, hypotheses, answers). Before sending, we remove emails, phone numbers and your full name from the text. We do not send your account name, email or user id. Every request uses `store=false`, so OpenAI does not keep it for training or evaluation. [TEAM: check and link OpenAI's current API data terms.] |
| **Amazon Web Services** | Servers, database, backups | All data in section 1 (storage) |
| **Cloudflare** | Network path from the internet to our server | Traffic (HTTPS-encrypted) |
| **Google** | Google sign-in (if you choose it) | Google authenticates you and returns your name and email |
| [TEAM: frontend host] | Serves the web app | Traffic |

**Transfers abroad:** data is processed on servers in [TEAM: AWS region] and by OpenAI in the USA. By accepting this policy you agree to these transfers for the purposes in section 2. [TEAM: cross-border transfer impact assessment under Decree 13, if applicable.]

### 4. Retention

[TEAM: decide. Proposal for discussion:]
- Account data and results: kept while the account is active.
- Detailed session data (events, code versions): 12 months from creation.
- Database backups: [number] days.
- On a deletion request, we delete within 30 days. Older backups expire on the schedule above.

### 5. Your rights

You have the right:
- to be informed;
- to give or withdraw consent;
- to access and get a copy of your data;
- to have it corrected or deleted;
- to restrict or object to processing;
- to complain as provided by law.

How to use them:
- **Turn off AI personalisation:** on the Profile page, effective immediately.
- **Edit your name:** on the Profile page.
- **Access, copy, account deletion, withdrawal of consent:** for now, email **trinhkiet2005@gmail.com** from your account's email address. We answer within [TEAM: number] days. If you withdraw consent, the AI features (Ciel, explain-back scoring) stop for your account; the rest of the coding practice remains available.

### 6. Security

- Connections are encrypted with HTTPS.
- Passwords are hashed.
- Your code runs in an isolated sandbox.
- The database is reachable only from inside the server.
- Only operating team members access data, and only when needed.

No system is perfectly secure. In case of a data breach, we will notify you and the authorities as required.

### 7. Children

[TEAM: minimum age. Decree 13 requires a parent or guardian's consent for children under 16; if that is not supported, state "CodeProve is for people aged 16 and over".]

### 8. Changes

When this policy changes, we update the version and ask for your consent again before you use the AI features.
