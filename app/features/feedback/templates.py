"""Fallback feedback text per finding code, in Vietnamese and English (P1.5).

Used when the LLM writer fails or a written item does not pass validation,
and as the house style the writer imitates. Each code has what_happened,
why_it_matters, how_to_improve, and a `practice` phrase (lower case, starts
with a verb) that becomes try_next: "Thử bài CP-105 và <practice>." when an
exercise is suggested, else "<Practice>."
"""
import string

from app.features.feedback.diagnosis import Finding

FIELDS = ("what_happened", "why_it_matters", "how_to_improve", "try_next")
DEFAULT_LOCALE = "vi"

_CATEGORIES = {
    "vi": {"happy": "thông thường", "boundary": "biên", "edge": "đặc biệt", "error": "xử lý lỗi",
           "uncategorized": "khác"},
    "en": {"happy": "typical", "boundary": "boundary", "edge": "edge", "error": "error handling",
           "uncategorized": "other"},
}
_SOME_CASES = {"vi": "một số trường hợp", "en": "some cases"}
_TRY = {"vi": ("Thử bài {next} và {practice}.", "{practice}."),
        "en": ("Try {next} and {practice}.", "{practice}.")}


def _t(what: str, why: str, how: str, practice: str) -> dict[str, str]:
    return {"what_happened": what, "why_it_matters": why, "how_to_improve": how, "practice": practice}


TEMPLATES: dict[str, dict[str, dict[str, str]]] = {
    # ---------- Understanding ----------
    "explain_missing": {
        "vi": _t("Câu trả lời explain-back chưa cho thấy bạn hiểu lời giải của mình.",
                 "Giải thích được code của chính mình là cách chắc chắn nhất để biết bạn thật sự hiểu, "
                 "không chỉ chạy được.",
                 "Trả lời theo hai ý: code làm gì theo từng bước, và vì sao cách đó đúng.",
                 "tự viết 2–3 câu giải thích lời giải trước khi Submit"),
        "en": _t("Your explain-back answers did not show that you understand your own solution.",
                 "Explaining your own code is the surest sign you understand it, not just that it runs.",
                 "Answer in two parts: what the code does step by step, and why that is correct.",
                 "write 2–3 sentences explaining your solution before you submit"),
    },
    "explain_shallow": {
        "vi": _t("Bạn nói được code làm gì nhưng chưa nói rõ vì sao nó đúng.",
                 "Hiểu \"vì sao\" giúp bạn tự sửa khi đề thay đổi, thay vì nhớ cách làm.",
                 "Thêm lý do và một trường hợp đặc biệt, ví dụ: vì sao vòng lặp dừng ở đó, input rỗng thì sao.",
                 "giải thích thêm một trường hợp đặc biệt trong câu trả lời explain-back"),
        "en": _t("You described what the code does but not clearly why it is correct.",
                 "Knowing the why lets you adapt when the problem changes, instead of recalling steps.",
                 "Add the reason and one special case: why the loop stops there, what happens with empty input.",
                 "cover one special case in your explain-back answer"),
    },
    "explain_strong": {
        "vi": _t("Bạn giải thích được cả cách làm lẫn lý do, kèm trường hợp đặc biệt.",
                 "Đó là dấu hiệu rõ nhất của việc hiểu thật, không phụ thuộc vào AI.",
                 "Giữ thói quen này và thử nói thêm về độ phức tạp thời gian.",
                 "thử giải thích cả độ phức tạp của lời giải"),
        "en": _t("You explained both how and why your solution works, including special cases.",
                 "That is the clearest sign of real understanding, independent of AI help.",
                 "Keep it up and try adding the time complexity.",
                 "also explain the complexity of your solution"),
    },
    # ---------- Hypothesis ----------
    "no_hypothesis": {
        "vi": _t("Bạn bắt đầu viết code mà không ghi giả thuyết.",
                 "Nêu hướng giải trước giúp phát hiện sai hướng sớm và bớt những lần chạy thử vô ích.",
                 "Trước khi code, ghi 1–2 câu: dùng cấu trúc hay thuật toán gì, trường hợp nào cần cẩn thận.",
                 "ghi giả thuyết trước dòng code đầu tiên"),
        "en": _t("You started coding without logging a hypothesis.",
                 "Stating your approach first catches a wrong direction early and saves wasted runs.",
                 "Before coding, write 1–2 sentences: which structure or algorithm, and which cases need care.",
                 "log a hypothesis before your first line of code"),
    },
    "hypothesis_vague": {
        "vi": _t("Giả thuyết của bạn còn chung chung, chưa chỉ ra hướng giải cụ thể.",
                 "Giả thuyết chỉ hữu ích khi nó định hướng được lời giải.",
                 "Nêu tên cách làm (ví dụ: dict lưu phần bù, hai con trỏ) và một trường hợp cần cẩn thận.",
                 "ghi giả thuyết có nêu rõ cấu trúc dữ liệu và một trường hợp biên"),
        "en": _t("Your hypothesis was generic and did not point to a concrete approach.",
                 "A hypothesis only helps when it steers the solution.",
                 "Name the approach (e.g. a dict of complements, two pointers) and one case to watch.",
                 "write a hypothesis that names the data structure and one edge case"),
    },
    "hypothesis_after_code": {
        "vi": _t("Bạn ghi giả thuyết sau khi đã bắt đầu viết code.",
                 "Giả thuyết có giá trị nhất khi dẫn đường cho code, không phải mô tả lại code đã viết.",
                 "Ghi giả thuyết ngay sau khi đọc đề, trước khi gõ code.",
                 "ghi giả thuyết ngay sau khi đọc đề"),
        "en": _t("You logged your hypothesis after you had started coding.",
                 "A hypothesis is most useful when it guides the code, not when it describes code already written.",
                 "Log it right after reading the problem, before typing code.",
                 "log your hypothesis right after reading the problem"),
    },
    "hypothesis_strong": {
        "vi": _t("Bạn nêu đúng hướng giải và trường hợp cần cẩn thận ngay từ đầu.",
                 "Lập kế hoạch trước giúp bạn giải gọn và ít phải sửa đi sửa lại.",
                 "Tiếp tục giữ thói quen này ở các bài khó hơn.",
                 "giữ thói quen lập kế hoạch ở một bài khó hơn"),
        "en": _t("You named the right approach and the cases to watch before coding.",
                 "Planning first is why your solve was clean, with little back-and-forth.",
                 "Keep this habit on harder problems.",
                 "keep planning first on a harder problem"),
    },
    # ---------- Prompting ----------
    "asked_for_solution": {
        "vi": _t("Bạn đã xin Ciel viết lời giải ({count} lần).",
                 "Nhận lời giải sẵn không rèn được kỹ năng, và CodeProve đánh giá cách bạn tự giải quyết vấn đề.",
                 "Hỏi về chỗ đang vướng: bạn đã thử gì, kết quả sai thế nào, và xin gợi ý thay vì đáp án.",
                 "chỉ hỏi Ciel gợi ý cho đúng chỗ bạn đang vướng"),
        "en": _t("You asked Ciel to write the solution ({count} time(s)).",
                 "A ready-made answer builds no skill, and CodeProve assesses how you solve problems yourself.",
                 "Ask about where you are stuck: what you tried, what went wrong, and ask for a hint, not the answer.",
                 "ask Ciel only for hints about the exact point you are stuck on"),
    },
    "prompts_vague": {
        "vi": _t("Câu hỏi gửi Ciel còn ngắn và thiếu ngữ cảnh.",
                 "Câu hỏi mơ hồ nhận câu trả lời chung chung và tốn thêm lượt hỏi.",
                 "Nêu cụ thể: input nào, kết quả mong đợi, kết quả thực tế, và bạn đoán lỗi ở đâu.",
                 "viết mỗi câu hỏi cho Ciel kèm input, kết quả mong đợi và kết quả thực tế"),
        "en": _t("Your questions to Ciel were short and lacked context.",
                 "Vague questions get generic answers and cost extra rounds.",
                 "Be specific: which input, the expected output, the actual output, and where you think the bug is.",
                 "include the input, the expected and the actual output in each question to Ciel"),
    },
    "prompts_strong": {
        "vi": _t("Câu hỏi gửi Ciel cụ thể, nói rõ bạn đã thử gì và xin hướng dẫn thay vì đáp án.",
                 "Đó là cách dùng trợ lý AI hiệu quả mà vẫn tự học được.",
                 "Giữ cách hỏi này khi gặp bài khó hơn.",
                 "giữ cách hỏi cụ thể này ở một bài khó hơn"),
        "en": _t("Your questions to Ciel were specific, said what you tried, and asked for guidance, not answers.",
                 "That is how to use an AI assistant effectively while still learning.",
                 "Keep asking this way on harder problems.",
                 "keep asking this way on a harder problem"),
    },
    # ---------- Verification ----------
    "pasted_ai_failing": {
        "vi": _t("Bạn dùng nguyên đoạn code Ciel đưa và bài vẫn fail khi Submit.",
                 "Code AI có thể sai; dùng mà không kiểm tra là rủi ro lớn nhất khi làm việc với AI.",
                 "Đọc từng dòng code AI trước khi dùng, chạy test ngay sau khi dán và sửa chỗ fail.",
                 "kiểm tra từng dòng code AI trước khi dùng"),
        "en": _t("You used Ciel's code as is and the submission still failed.",
                 "AI code can be wrong; using it unchecked is the biggest risk when working with AI.",
                 "Read AI code line by line before using it, run the tests right after, and fix what fails.",
                 "check AI code line by line before using it"),
    },
    "pasted_ai_unchecked": {
        "vi": _t("Bạn dùng nguyên đoạn code Ciel đưa, không sửa hay kiểm tra thêm; lần này nó chạy đúng.",
                 "Lần sau code AI có thể có lỗi mà test hiển thị không bắt được.",
                 "Tự đọc hiểu code AI, thử thêm trường hợp biên, hoặc hỏi Ciel vì sao đoạn code đó đúng.",
                 "thử thêm một trường hợp biên cho mọi đoạn code AI bạn dùng"),
        "en": _t("You used Ciel's code as is, without changing or checking it; this time it worked.",
                 "Next time the AI code may hide a bug the visible tests do not catch.",
                 "Read and understand AI code, try an edge case, or ask Ciel why the code is correct.",
                 "test an edge case for any AI code you use"),
    },
    "adapted_ai_code": {
        "vi": _t("Bạn sửa lại code Ciel đưa cho đúng thay vì dùng nguyên.",
                 "Đọc và chỉnh code AI là kỹ năng quan trọng nhất khi làm việc cùng AI.",
                 "Tiếp tục kiểm tra code AI như vậy, nhất là ở các trường hợp biên.",
                 "tiếp tục kiểm tra kỹ code AI"),
        "en": _t("You corrected Ciel's code instead of using it as is.",
                 "Reading and fixing AI code is the key skill when working with AI.",
                 "Keep checking AI code this way, especially on edge cases.",
                 "keep checking AI code this carefully"),
    },
    "questioned_ai_code": {
        "vi": _t("Bạn đặt câu hỏi nghi ngờ đoạn code Ciel đưa thay vì tin ngay.",
                 "Không tin mù quáng vào AI là thói quen giúp bạn tránh lỗi tinh vi.",
                 "Giữ sự hoài nghi này và kiểm chứng bằng test cụ thể.",
                 "kiểm chứng nghi ngờ của bạn bằng một test cụ thể"),
        "en": _t("You questioned Ciel's code instead of trusting it right away.",
                 "Healthy doubt about AI output is what catches subtle bugs.",
                 "Keep that doubt and confirm it with a concrete test.",
                 "confirm your doubts with a concrete test"),
    },
    # ---------- Testing ----------
    "never_ran_tests": {
        "vi": _t("Bạn Submit mà chưa chạy test lần nào.",
                 "Chạy test trước khi nộp giúp bắt lỗi khi vẫn còn sửa được.",
                 "Chạy test hiển thị, rồi tự thử thêm vài trường hợp biên trước khi Submit.",
                 "chạy test ít nhất một lần trước khi Submit"),
        "en": _t("You submitted without running the tests once.",
                 "Running tests before submitting catches bugs while you can still fix them.",
                 "Run the visible tests, then try a few edge cases of your own before submitting.",
                 "run the tests at least once before submitting"),
    },
    "submitted_failing": {
        "vi": _t("Bạn Submit khi còn test fail: pass {passed}/{total}.",
                 "Nộp khi còn test fail nghĩa là lời giải chưa đúng với yêu cầu của đề.",
                 "Đọc từng test fail, so kết quả thực tế với mong đợi, sửa cho pass hết test hiển thị rồi mới Submit.",
                 "chỉ Submit khi mọi test hiển thị đã pass"),
        "en": _t("You submitted with failing tests: {passed}/{total} passed.",
                 "Submitting with failures means the solution does not yet meet the problem.",
                 "Read each failing test, compare actual and expected output, pass every visible test, then submit.",
                 "submit only when every visible test passes"),
    },
    "hidden_edge_failed": {
        "vi": _t("Test hiển thị pass hết nhưng test ẩn nhóm {failed_categories} còn fail.",
                 "Test ẩn kiểm tra các trường hợp đề không nêu rõ; code thật cũng gặp những trường hợp này.",
                 "Trước khi Submit, tự liệt kê trường hợp biên: rỗng, một phần tử, số âm, giá trị trùng, giới hạn lớn.",
                 "liệt kê các trường hợp biên trước khi Submit"),
        "en": _t("All visible tests passed but hidden {failed_categories} tests failed.",
                 "Hidden tests check cases the problem does not spell out; real code meets them too.",
                 "Before submitting, list edge cases: empty, one element, negatives, duplicates, large limits.",
                 "list the edge cases before submitting"),
    },
    "all_tests_passed": {
        "vi": _t("Lời giải pass toàn bộ test, kể cả test ẩn.",
                 "Bạn đã xử lý được cả những trường hợp đề không nêu rõ.",
                 "Thử tự viết thêm test cho trường hợp khó nhất bạn nghĩ ra.",
                 "tự viết thêm một test cho trường hợp khó nhất"),
        "en": _t("Your solution passed every test, hidden ones included.",
                 "You handled the cases the problem does not spell out.",
                 "Try writing a test of your own for the hardest case you can think of.",
                 "write one extra test for the hardest case"),
    },
    # ---------- Debugging ----------
    "bug_not_fixed": {
        "vi": _t("Lỗi chưa được sửa: còn test hiển thị fail khi Submit.",
                 "Tìm và sửa lỗi là kỹ năng cốt lõi khi làm việc với code, kể cả code do AI viết.",
                 "Chạy code, đọc test fail, so kết quả thực tế với mong đợi để khoanh vùng dòng lỗi.",
                 "khoanh vùng lỗi bằng cách so kết quả thực tế với mong đợi"),
        "en": _t("The bug was not fixed: visible tests still failed at submit.",
                 "Finding and fixing bugs is a core skill, including in AI-written code.",
                 "Run the code, read the failing test, compare actual and expected output to narrow down the line.",
                 "narrow bugs down by comparing actual and expected output"),
    },
    "partial_fix": {
        "vi": _t("Bạn sửa được lỗi chính (test hiển thị pass) nhưng test ẩn nhóm {failed_categories} còn fail.",
                 "Một lỗi thường kéo theo các trường hợp tương tự; sửa xong cần kiểm tra cả chúng.",
                 "Sau khi sửa, thử lại với các input biên liên quan đến chỗ vừa sửa.",
                 "thử lại các input biên liên quan sau mỗi lần sửa lỗi"),
        "en": _t("You fixed the main bug (visible tests pass) but hidden {failed_categories} tests still failed.",
                 "A bug usually has related cases; after a fix, check them too.",
                 "After fixing, retry the edge inputs related to what you changed.",
                 "retry related edge inputs after every fix"),
    },
    "trial_and_error": {
        "vi": _t("Bạn sửa được lỗi sau {failing_runs} lần chạy fail.",
                 "Thử-sai tốn thời gian và dễ sửa đúng mà không hiểu vì sao.",
                 "Trước mỗi lần chạy, nêu giả thuyết lỗi nằm ở đâu và chỉ sửa đúng chỗ đó.",
                 "nêu giả thuyết về lỗi trước mỗi lần chạy"),
        "en": _t("You fixed the bug after {failing_runs} failing runs.",
                 "Trial and error is slow and can fix things without you knowing why.",
                 "Before each run, state where you think the bug is and change only that.",
                 "state a hypothesis about the bug before each run"),
    },
    "quick_fix": {
        "vi": _t("Bạn tìm đúng chỗ lỗi và sửa gọn, gần như không phải thử lại.",
                 "Đó là dấu hiệu bạn đọc và hiểu code trước khi sửa.",
                 "Giữ cách làm này ở các bài debug khó hơn.",
                 "giữ cách làm này ở một bài debug khó hơn"),
        "en": _t("You found the bug and fixed it cleanly, with almost no retries.",
                 "That shows you read and understood the code before changing it.",
                 "Keep this approach on harder debugging exercises.",
                 "keep this approach on a harder debugging exercise"),
    },
    # ---------- Integrity ----------
    "integrity_flags": {
        "vi": _t("Phiên làm bài có tín hiệu bất thường (dán nội dung từ ngoài hoặc rời trang), nên điểm các trục bị giảm.",
                 "CodeProve đánh giá cách bạn tự làm; nội dung đưa vào từ nơi khác không cho thấy kỹ năng của bạn.",
                 "Làm trọn bài trong editor và dùng Ciel ngay trên trang khi cần hỗ trợ.",
                 "làm trọn bài trong editor, dùng Ciel khi cần hỗ trợ"),
        "en": _t("This session showed unusual signals (pasting from outside or leaving the page), so the axes were "
                 "reduced.",
                 "CodeProve assesses how you work yourself; content brought in from elsewhere shows nothing of "
                 "your skill.",
                 "Work entirely in the editor and use Ciel on the page when you need help.",
                 "work entirely in the editor and use Ciel when you need help"),
    },
}


class _Params(dict):
    def __missing__(self, key: str) -> str:
        return "?"


def _params(finding: Finding, locale: str) -> _Params:
    params = _Params({k: v for k, v in finding.params.items() if k != "failed_categories"})
    names = _CATEGORIES[locale]
    categories = [names.get(c, c) for c in finding.params.get("failed_categories") or []]
    params["failed_categories"] = _join(categories, locale) or _SOME_CASES[locale]
    return params


def _join(items: list[str], locale: str) -> str:
    """"a", "a và b", "a, b và c" (en: "and")."""
    if len(items) < 2:
        return "".join(items)
    return f"{', '.join(items[:-1])} {'và' if locale == 'vi' else 'and'} {items[-1]}"


def render(finding: Finding, locale: str, next_exercise: str | None) -> dict[str, str]:
    """The four feedback fields for a finding, from its template."""
    locale = locale if locale in ("vi", "en") else DEFAULT_LOCALE
    texts = TEMPLATES[finding.code][locale]
    params = _params(finding, locale)
    fmt = string.Formatter()
    out = {field: fmt.vformat(texts[field], (), params) for field in FIELDS[:3]}
    practice = fmt.vformat(texts["practice"], (), params)
    with_next, without_next = _TRY[locale]
    out["try_next"] = (with_next.format(next=next_exercise, practice=practice) if next_exercise
                       else without_next.format(practice=practice[:1].upper() + practice[1:]))
    return out
