# Chính sách quyền riêng tư — CodeProve

## Tiếng Việt

**Cập nhật lần cuối:** 01/10/2026 · **Phiên bản:** 2026-10-2

CodeProve là nền tảng luyện và đánh giá kỹ năng lập trình có trợ lý AI (Ciel). Chính sách này giải thích chúng tôi thu thập dữ liệu gì, dùng để làm gì, chia sẻ với ai và bạn có những quyền gì.

**Bên kiểm soát dữ liệu:** Nhóm phát triển CodeProve. Mọi yêu cầu và câu hỏi về quyền riêng tư xin gửi tới **flux@codeprove.vn**.

### 1. Dữ liệu chúng tôi thu thập

| Nhóm dữ liệu | Gồm những gì | Lấy từ đâu |
|---|---|---|
| Tài khoản | Họ tên, email, mật khẩu (chỉ lưu dạng băm, không đọc được), ảnh đại diện (nếu bạn tải lên) | Bạn nhập khi đăng ký, hoặc Google gửi (tên, email) khi bạn đăng nhập bằng Google |
| Quá trình làm bài | Code bạn viết (các bản lưu tự động), các lần chạy và nộp, test bạn viết, các bước khi tìm lỗi (dòng bạn chọn, lời giải thích), giả thuyết và câu trả lời explain-back | Trong lúc bạn làm bài |
| Tín hiệu làm bài | Thời điểm các thao tác, việc dán nội dung từ ngoài vào, rời khỏi trang hoặc thoát toàn màn hình trong khi làm bài | Trình duyệt gửi trong lúc bạn làm bài, dùng cho phần điểm về tính trung thực |
| Trò chuyện với Ciel | Câu hỏi bạn gửi và câu trả lời bạn đã thấy | Trong lúc bạn dùng Ciel |
| Kết quả | Điểm theo 6 trục, báo cáo và nhận xét, điểm kỹ năng (Elo) theo từng kỹ năng, lịch sử bài đã làm, Daily Bug Hunt | Hệ thống tính từ quá trình làm bài |
| Kỹ thuật | Số token mỗi lần gọi AI (không có nội dung), thời gian; token đăng nhập lưu trong trình duyệt của bạn | Hệ thống tự ghi |

Chúng tôi không thu thập số CMND/CCCD, thông tin thanh toán, vị trí hay danh bạ.

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
| **OpenAI** (Hoa Kỳ) | Mô hình AI cho Ciel, chấm câu trả lời và viết nhận xét | Đề bài; nội dung bạn viết (câu hỏi, code, giả thuyết, câu trả lời). Trước khi gửi, chúng tôi xoá email, số điện thoại và họ tên đầy đủ của bạn khỏi nội dung. Chúng tôi không gửi tên tài khoản, email hay mã người dùng của bạn. Theo điều khoản của OpenAI, dữ liệu gửi qua API không được dùng để huấn luyện mô hình. Chúng tôi đặt `store=false` để OpenAI không lưu nội dung cho các tính năng lưu trữ. OpenAI vẫn có thể giữ log tối đa 30 ngày để phát hiện lạm dụng, trừ khi pháp luật yêu cầu lâu hơn. Chi tiết: [Điều khoản dữ liệu API của OpenAI](https://developers.openai.com/api/docs/guides/your-data) |
| **Amazon Web Services** (Sydney, Úc) | Máy chủ, cơ sở dữ liệu, bản sao lưu | Toàn bộ dữ liệu ở mục 1 (lưu trữ) |
| **Cloudflare** | Đường truyền từ internet tới máy chủ | Lưu lượng truy cập (đã mã hoá HTTPS) |
| **Vercel** (Hoa Kỳ) | Phục vụ giao diện web | Lưu lượng truy cập |
| **Google** | Đăng nhập bằng Google (nếu bạn chọn) | Google xác thực bạn và gửi lại tên, email |

**Chuyển dữ liệu ra nước ngoài:** dữ liệu của bạn được lưu trên máy chủ AWS tại Úc và được OpenAI xử lý tại Hoa Kỳ. Lưu lượng truy cập đi qua hạ tầng của Cloudflare và Vercel. Khi đồng ý với chính sách này, bạn đồng ý việc chuyển dữ liệu đó cho các mục đích ở mục 2.

### 4. Thời gian lưu trữ

- **Dữ liệu tài khoản, quá trình làm bài và kết quả:** lưu trong thời gian tài khoản còn hoạt động, để bạn xem lại lịch sử và tiến độ.
- **Khi bạn yêu cầu xoá tài khoản:** chúng tôi xoá dữ liệu gắn với tài khoản trong vòng 30 ngày. Bản sao lưu cơ sở dữ liệu tự hết hạn sau 30 ngày, nên dữ liệu đã xoá biến mất khỏi bản sao lưu chậm nhất 30 ngày sau đó.
- **Dữ liệu đã ẩn danh hoá** dùng để hiệu chỉnh chấm điểm (không còn email, số điện thoại hay mã tài khoản thật) có thể được giữ lâu hơn.
- **Log token của các lần gọi AI** chỉ là con số, không có nội dung, dùng cho báo cáo chi phí.

### 5. Quyền của bạn

Bạn có quyền:
- được biết về việc xử lý dữ liệu;
- đồng ý hoặc rút lại đồng ý;
- xem và nhận bản sao dữ liệu;
- yêu cầu sửa hoặc xoá;
- hạn chế hoặc phản đối việc xử lý;
- khiếu nại theo quy định pháp luật Việt Nam về bảo vệ dữ liệu cá nhân.

Cách thực hiện:
- **Tắt Cá nhân hoá AI:** tự làm ở trang Hồ sơ, có hiệu lực ngay.
- **Sửa họ tên:** tự làm ở trang Hồ sơ.
- **Xem, nhận bản sao, xoá tài khoản, rút lại đồng ý:** gửi email tới **flux@codeprove.vn** từ email tài khoản của bạn. Chúng tôi phản hồi trong vòng 72 giờ và hoàn tất yêu cầu trong thời hạn pháp luật quy định. Nếu bạn rút lại đồng ý, các tính năng AI (Ciel, kiểm tra giả thuyết, chấm điểm explain-back) sẽ ngừng hoạt động với tài khoản của bạn; phần luyện code khác vẫn dùng được.

### 6. Bảo mật

- Kết nối được mã hoá HTTPS.
- Mật khẩu được băm.
- Code của bạn chạy trong môi trường cách ly.
- Cơ sở dữ liệu chỉ truy cập được từ bên trong máy chủ.
- Bản sao lưu được mã hoá.
- Chỉ thành viên vận hành được truy cập dữ liệu, và chỉ khi cần.

Không hệ thống nào an toàn tuyệt đối. Nếu xảy ra sự cố lộ dữ liệu, chúng tôi sẽ thông báo cho bạn và cơ quan có thẩm quyền theo quy định.

### 7. Độ tuổi

CodeProve dành cho người từ **16 tuổi trở lên**. Nếu bạn dưới 16 tuổi, vui lòng không đăng ký. Nếu chúng tôi biết một tài khoản thuộc về người dưới 16 tuổi, chúng tôi sẽ xoá tài khoản đó.

### 8. Thay đổi chính sách

Khi chính sách thay đổi, chúng tôi cập nhật phiên bản và hỏi lại sự đồng ý của bạn trước khi bạn dùng tiếp các tính năng AI.

---

## English

**Last updated:** 1 October 2026 · **Version:** 2026-10-2

CodeProve is a platform for practising and assessing programming skills with an AI assistant (Ciel). This policy explains what data we collect, why, who we share it with, and your rights.

**Data controller:** the CodeProve team. Please send privacy requests and questions to **flux@codeprove.vn**.

### 1. Data we collect

| Category | What | Source |
|---|---|---|
| Account | Name, email, password (stored only as a hash), avatar (if you upload one) | You, at sign-up; or Google (name, email) when you sign in with Google |
| Work on exercises | Your code (autosaved versions), runs and submissions, the tests you write, debugging steps (lines you pick, your explanation), hypotheses and explain-back answers | While you work |
| Session signals | Timing of actions; pasting from outside, leaving the page or exiting full screen during an exercise | Your browser, for the integrity part of the score |
| Ciel chat | The questions you send and the replies you saw | While you use Ciel |
| Results | Scores on 6 axes, reports and feedback, per-skill ratings (Elo), exercise history, Daily Bug Hunt | Computed from your work |
| Technical | Token counts of each AI call (no content), timestamps; the sign-in token stored in your browser | Logged automatically |

We do not collect ID numbers, payment data, location or contacts.

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
| **OpenAI** (USA) | AI model for Ciel, answer scoring and feedback writing | The exercise, and what you wrote (questions, code, hypotheses, answers). Before sending, we remove emails, phone numbers and your full name from the text. We do not send your account name, email or user id. Under OpenAI's terms, API data is not used to train their models. We set `store=false` so that OpenAI does not keep the content for its storage features. OpenAI may still keep logs for up to 30 days to detect abuse, unless the law requires longer. Details: [OpenAI API data controls](https://developers.openai.com/api/docs/guides/your-data) |
| **Amazon Web Services** (Sydney, Australia) | Servers, database, backups | All data in section 1 (storage) |
| **Cloudflare** | Network path from the internet to our server | Traffic (HTTPS-encrypted) |
| **Vercel** (USA) | Serves the web app | Traffic |
| **Google** | Google sign-in (if you choose it) | Google authenticates you and returns your name and email |

**Transfers abroad:** your data is stored on AWS servers in Australia and processed by OpenAI in the USA. Traffic passes through Cloudflare's and Vercel's infrastructure. By accepting this policy you agree to these transfers for the purposes in section 2.

### 4. Retention

- **Account data, exercise work and results:** kept while your account is active, so you can see your history and progress.
- **On an account deletion request:** we delete the data linked to your account within 30 days. Database backups expire after 30 days, so deleted data leaves the backups at most 30 days later.
- **Pseudonymised data** used to calibrate scoring (no email, phone number or real account id) may be kept longer.
- **Token logs of AI calls** are numbers only, with no content, and are used for cost reports.

### 5. Your rights

You have the right:
- to be informed;
- to give or withdraw consent;
- to access and get a copy of your data;
- to have it corrected or deleted;
- to restrict or object to processing;
- to complain under Vietnam's personal data protection law.

How to use them:
- **Turn off AI personalisation:** on the Profile page, effective immediately.
- **Edit your name:** on the Profile page.
- **Access, copy, account deletion, withdrawal of consent:** email **flux@codeprove.vn** from your account's email address. We reply within 72 hours and complete the request within the time the law requires. If you withdraw consent, the AI features (Ciel, the hypothesis check, explain-back scoring) stop for your account; the rest of the coding practice remains available.

### 6. Security

- Connections are encrypted with HTTPS.
- Passwords are hashed.
- Your code runs in an isolated sandbox.
- The database is reachable only from inside the server.
- Backups are encrypted.
- Only operating team members access data, and only when needed.

No system is perfectly secure. In case of a data breach, we will notify you and the authorities as required.

### 7. Age

CodeProve is for people aged **16 and over**. If you are under 16, please do not sign up. If we learn that an account belongs to someone under 16, we will delete it.

### 8. Changes

When this policy changes, we update the version and ask for your consent again before you use the AI features.
