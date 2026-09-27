"""Feedback text per finding code, in Vietnamese and English (P1.5).

Reviewed by the team (docs/calibration/phan-hoi-can-duyet.md, review of preview
round 3): state only what the system observed, no absolutes ("the surest",
"the most important"), no guessed motives, and no examples that only fit one
kind of exercise. Each code has what_happened, why_it_matters, how_to_improve,
and a `practice` phrase (lower case, starts with a verb) that becomes try_next:
"Thử bài CP-105 và <practice>." when an exercise is suggested, else "<Practice>."
"""
import string

from app.features.feedback.diagnosis import Finding

FIELDS = ("what_happened", "why_it_matters", "how_to_improve", "try_next")
DEFAULT_LOCALE = "vi"

_CATEGORIES = {
    "vi": {"happy": "thông thường", "boundary": "giá trị biên", "edge": "tình huống đặc biệt",
           "error": "xử lý lỗi", "uncategorized": "khác"},
    "en": {"happy": "typical", "boundary": "boundary", "edge": "edge", "error": "error handling",
           "uncategorized": "other"},
}
_SOME_CASES = {"vi": "một số trường hợp", "en": "some cases"}
_FAILED_TESTS = {"vi": ", gồm: {names}", "en": ", including {names}"}
_SIGNALS = {"vi": ("dán nội dung từ ngoài {n} lần", "rời trang {n} lần"),
            "en": ("pasted from outside {n} time(s)", "left the page {n} time(s)")}
_AND = {"vi": "và", "en": "and"}
_TRY = {"vi": ("Thử bài {next} và {practice}.", "{practice}."),
        "en": ("Try {next} and {practice}.", "{practice}.")}


def _t(what: str, why: str, how: str, practice: str) -> dict[str, str]:
    return {"what_happened": what, "why_it_matters": why, "how_to_improve": how, "practice": practice}


TEMPLATES: dict[str, dict[str, dict[str, str]]] = {
    # ---------- Understanding ----------
    "explain_missing": {
        "vi": _t("Câu trả lời explain-back chưa cho thấy bạn hiểu lời giải đang nộp.",
                 "Giải thích được code mình nộp là một cách quan trọng để biết bạn thật sự hiểu nó, "
                 "không chỉ chạy được.",
                 "Trả lời theo hai ý: code làm gì theo từng bước, và vì sao cách đó đúng.",
                 "tự viết 2–3 câu giải thích lời giải trước khi Submit"),
        "en": _t("Your explain-back answers did not show that you understand the solution you submitted.",
                 "Explaining the code you submit is an important way to know you understand it, not just "
                 "that it runs.",
                 "Answer in two parts: what the code does step by step, and why that is correct.",
                 "write 2–3 sentences explaining your solution before you submit"),
    },
    "explain_shallow": {
        "vi": _t("Bạn nói được code làm gì nhưng chưa nói rõ vì sao nó đúng.",
                 "Hiểu \"vì sao\" giúp bạn tự sửa khi đề thay đổi, thay vì nhớ cách làm.",
                 "Với mỗi bước chính, thêm một câu \"vì sao\": bước đó cần để làm gì, và nếu bỏ đi hoặc "
                 "làm khác thì kết quả sai ở đâu.",
                 "trả lời thêm \"vì sao\" cho mỗi bước chính trong explain-back"),
        "en": _t("You described what the code does but not clearly why it is correct.",
                 "Knowing the why lets you adapt when the problem changes, instead of recalling steps.",
                 "For each main step, add one \"why\" sentence: what the step is for, and what would go "
                 "wrong without it or done differently.",
                 "add a \"why\" for each main step in your explain-back answers"),
    },
    "explain_strong": {
        "vi": _t("Bạn giải thích được cả cách làm lẫn lý do vì sao lời giải đúng.",
                 "Điều đó cho thấy bạn hiểu cách làm của mình, không chỉ làm cho code chạy được.",
                 "Giữ thói quen này; ở bài sau thử nói thêm vì sao bạn chọn cách này thay vì một cách khác.",
                 "so sánh lời giải với một cách làm khác khi giải thích"),
        "en": _t("You explained both how your solution works and why it is correct.",
                 "That shows you understand your approach, not only that the code runs.",
                 "Keep it up; next time also say why you chose this approach over another one.",
                 "compare your solution with another approach when you explain it"),
    },
    # ---------- Hypothesis ----------
    "no_hypothesis": {
        "vi": _t("Bạn chưa ghi lại hướng giải (giả thuyết) trước khi code.",
                 "Ghi hướng giải trước có thể giúp phát hiện sai hướng sớm và bớt những lần chạy thử "
                 "không cần thiết.",
                 "Trước khi code, ghi 1–2 câu: bạn định làm theo cách nào, và trường hợp nào trong đề cần cẩn thận.",
                 "ghi 1–2 câu hướng giải trước dòng code đầu tiên"),
        "en": _t("You did not log your approach (hypothesis) before coding.",
                 "Writing your approach first can catch a wrong direction early and save unneeded runs.",
                 "Before coding, write 1–2 sentences: how you plan to solve it, and which cases in the "
                 "problem need care.",
                 "log 1–2 sentences of approach before your first line of code"),
    },
    "hypothesis_vague": {
        "vi": _t("Giả thuyết của bạn còn chung chung, chưa chỉ ra hướng giải cụ thể.",
                 "Giả thuyết hữu ích nhất khi nó định hướng được lời giải.",
                 "Nêu rõ bạn định dùng cấu trúc dữ liệu hoặc cách làm nào, và một trường hợp trong đề "
                 "cần cẩn thận.",
                 "ghi giả thuyết nêu rõ cách làm và một trường hợp cần cẩn thận"),
        "en": _t("Your hypothesis was generic and did not point to a concrete approach.",
                 "A hypothesis helps most when it steers the solution.",
                 "Say which data structure or approach you plan to use, and one case in the problem to watch.",
                 "write a hypothesis that names your approach and one case to watch"),
    },
    "hypothesis_after_code": {
        "vi": _t("Bạn ghi giả thuyết sau khi đã bắt đầu viết code.",
                 "Ghi trước khi code giúp định hướng tốt hơn; ghi sau vẫn có ích để kiểm tra lại cách nghĩ.",
                 "Lần tới, ghi 1–2 câu hướng giải ngay sau khi đọc đề, trước khi gõ code.",
                 "ghi giả thuyết ngay sau khi đọc đề"),
        "en": _t("You logged your hypothesis after you had started coding.",
                 "Writing it before coding steers you better; writing it after still helps you review your "
                 "thinking.",
                 "Next time, write 1–2 sentences of approach right after reading the problem, before typing code.",
                 "log your hypothesis right after reading the problem"),
    },
    "hypothesis_strong": {
        "vi": _t("Bạn ghi hướng giải và trường hợp cần cẩn thận trước khi code.",
                 "Lập kế hoạch trước có thể giúp bạn giải gọn hơn và ít phải sửa đi sửa lại.",
                 "Ở bài khó hơn, ghi thêm bạn sẽ kiểm tra hướng giải đó bằng test nào.",
                 "ghi hướng giải trước khi code"),
        "en": _t("You wrote down your approach and the cases to watch before coding.",
                 "Planning first can make your solve cleaner, with less back-and-forth.",
                 "On harder problems, also note which test would show your approach works.",
                 "log your approach before coding"),
    },
    # ---------- Prompting ----------
    "asked_for_solution": {
        "vi": _t("Bạn đã xin Ciel viết lời giải ({count} lần).",
                 "Nhận lời giải sẵn làm giảm cơ hội tự luyện, và CodeProve đánh giá cách bạn tự giải "
                 "quyết vấn đề.",
                 "Hỏi về chỗ đang vướng: bạn đã thử gì, kết quả sai thế nào, và xin gợi ý thay vì đáp án.",
                 "chỉ hỏi Ciel gợi ý cho đúng chỗ bạn đang vướng"),
        "en": _t("You asked Ciel to write the solution ({count} time(s)).",
                 "A ready-made answer means less practice for you, and CodeProve assesses how you solve "
                 "problems yourself.",
                 "Ask about where you are stuck: what you tried, what went wrong, and ask for a hint, not the answer.",
                 "ask Ciel only for hints about the exact point you are stuck on"),
    },
    "prompts_vague": {
        "vi": _t("Câu hỏi gửi Ciel còn ngắn và thiếu ngữ cảnh.",
                 "Câu hỏi mơ hồ thường nhận câu trả lời chung chung và tốn thêm lượt hỏi.",
                 "Nói rõ bạn đang vướng ở đâu và đã thử gì; nếu hỏi về lỗi, kèm input, kết quả mong đợi "
                 "và kết quả thực tế.",
                 "nói rõ chỗ đang vướng và điều đã thử trong mỗi câu hỏi gửi Ciel"),
        "en": _t("Your questions to Ciel were short and lacked context.",
                 "Vague questions tend to get generic answers and cost extra rounds.",
                 "Say where you are stuck and what you tried; when asking about a bug, include the input, "
                 "the expected and the actual output.",
                 "say where you are stuck and what you tried in each question to Ciel"),
    },
    "prompts_strong": {
        "vi": _t("Câu hỏi gửi Ciel cụ thể và nói rõ bạn đã thử gì.",
                 "Đó là cách dùng trợ lý AI hiệu quả mà vẫn tự học được.",
                 "Giữ cách hỏi này khi gặp bài khó hơn.",
                 "giữ cách hỏi cụ thể này ở một bài khó hơn"),
        "en": _t("Your questions to Ciel were specific and said what you had tried.",
                 "That is how to use an AI assistant effectively while still learning.",
                 "Keep asking this way on harder problems.",
                 "keep asking this way on a harder problem"),
    },
    # ---------- Verification ----------
    "pasted_ai_failing": {
        "vi": _t("Bạn dùng nguyên đoạn code Ciel đưa và bài vẫn fail khi Submit.",
                 "Code AI có thể sai; dùng mà chưa kiểm tra kỹ là một rủi ro lớn khi làm việc với AI.",
                 "Đọc từng dòng code AI trước khi nộp, chạy test ngay sau khi dán và sửa chỗ fail.",
                 "kiểm tra từng dòng code AI trước khi nộp"),
        "en": _t("You used Ciel's code as is and the submission still failed.",
                 "AI code can be wrong; using it without checking carefully is a real risk when working with AI.",
                 "Read AI code line by line before submitting, run the tests right after pasting, and fix "
                 "what fails.",
                 "check AI code line by line before submitting"),
    },
    "pasted_ai_unchecked": {
        "vi": _t("Bạn dùng nguyên đoạn code Ciel đưa; hệ thống chưa thấy dấu hiệu bạn đã kiểm tra hoặc "
                 "điều chỉnh nó. Lần này code chạy đúng.",
                 "Lần sau code AI có thể có lỗi mà test hiển thị không bắt được.",
                 "Tự đọc hiểu code AI, chạy thêm một trường hợp biên phù hợp với đề, hoặc hỏi Ciel vì sao "
                 "đoạn code đó đúng.",
                 "chạy thêm một trường hợp biên cho mỗi đoạn code AI bạn dùng"),
        "en": _t("You used Ciel's code as is; the system saw no sign that you checked or adjusted it. "
                 "This time it worked.",
                 "Next time the AI code may hide a bug the visible tests do not catch.",
                 "Read and understand AI code, run one more boundary case that fits the problem, or ask "
                 "Ciel why the code is correct.",
                 "run one more boundary case for any AI code you use"),
    },
    "adapted_ai_code": {
        "vi": _t("Bạn sửa lại code Ciel đưa thay vì dùng nguyên, và bài pass.",
                 "Đọc và chỉnh code AI là một kỹ năng quan trọng khi làm việc cùng AI.",
                 "Tiếp tục kiểm tra code AI như vậy, nhất là ở các trường hợp biên.",
                 "tiếp tục kiểm tra kỹ code AI"),
        "en": _t("You changed Ciel's code instead of using it as is, and it passed.",
                 "Reading and adjusting AI code is an important skill when working with AI.",
                 "Keep checking AI code this way, especially on boundary cases.",
                 "keep checking AI code this carefully"),
    },
    "questioned_ai_code": {
        "vi": _t("Bạn đặt câu hỏi nghi ngờ đoạn code Ciel đưa thay vì tin ngay.",
                 "Không tin ngay vào AI là thói quen tốt; test sẽ cho bạn câu trả lời chắc chắn hơn.",
                 "Giữ sự hoài nghi này và kiểm chứng bằng test cụ thể.",
                 "kiểm chứng nghi ngờ của bạn bằng một test cụ thể"),
        "en": _t("You questioned Ciel's code instead of trusting it right away.",
                 "Not trusting AI output right away is a good habit; a test gives you a firmer answer.",
                 "Keep that doubt and confirm it with a concrete test.",
                 "confirm your doubts with a concrete test"),
    },
    # ---------- Testing ----------
    "never_ran_tests": {
        "vi": _t("Bạn Submit mà chưa chạy test lần nào.",
                 "Chạy test giúp bạn phát hiện lỗi trước khi nộp bài.",
                 "Chạy test hiển thị, rồi thử thêm ít nhất một trường hợp biên phù hợp với đề trước khi Submit.",
                 "chạy test ít nhất một lần trước khi Submit"),
        "en": _t("You submitted without running the tests once.",
                 "Running the tests helps you find bugs before you submit.",
                 "Run the visible tests, then try at least one boundary case that fits the problem before "
                 "submitting.",
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
        "vi": _t("Test hiển thị pass hết nhưng test ẩn nhóm {failed_categories} còn fail{failed_tests}.",
                 "Test ẩn kiểm tra các trường hợp ít thấy trong ví dụ của đề; code dùng thật cũng sẽ gặp chúng.",
                 "Trước khi Submit, đọc lại đề và liệt kê các tình huống ví dụ chưa có: giá trị ở giới hạn "
                 "đề cho, input bất thường mà đề vẫn cho phép, các yêu cầu phụ; rồi tự chạy thử từng tình huống.",
                 "liệt kê các tình huống ví dụ chưa có trước khi Submit"),
        "en": _t("All visible tests passed but hidden {failed_categories} tests failed{failed_tests}.",
                 "Hidden tests check cases the examples rarely show; real code meets them too.",
                 "Before submitting, reread the problem and list the situations the examples skip: values at "
                 "the stated limits, unusual inputs the problem still allows, secondary requirements; then "
                 "try each one.",
                 "list the situations the examples skip before submitting"),
    },
    "all_tests_passed": {
        "vi": _t("Lời giải pass toàn bộ test, kể cả test ẩn.",
                 "Lời giải đã xử lý tốt các trường hợp mà bộ test kiểm tra.",
                 "Tự viết thêm test cho trường hợp khó nhất bạn nghĩ ra, để tìm những gì bộ test chưa có.",
                 "tự viết thêm một test cho trường hợp khó nhất"),
        "en": _t("Your solution passed every test, hidden ones included.",
                 "Your solution handles the cases the test suite checks.",
                 "Write a test of your own for the hardest case you can think of, to find what the suite misses.",
                 "write one extra test for the hardest case"),
    },
    # ---------- Debugging ----------
    "bug_not_fixed": {
        "vi": _t("Lỗi chưa được sửa hết: khi Submit còn test fail (pass {passed}/{total}).",
                 "Tìm và sửa lỗi là kỹ năng cốt lõi khi làm việc với code, kể cả code do AI viết.",
                 "Chạy code, đọc từng test fail, so kết quả thực tế với mong đợi để khoanh vùng dòng lỗi; "
                 "Submit khi mọi test hiển thị đã pass.",
                 "khoanh vùng lỗi bằng cách so kết quả thực tế với mong đợi"),
        "en": _t("The bug was not fully fixed: tests still failed at submit ({passed}/{total} passed).",
                 "Finding and fixing bugs is a core skill, including in AI-written code.",
                 "Run the code, read each failing test, compare actual and expected output to narrow down "
                 "the line; submit when every visible test passes.",
                 "narrow bugs down by comparing actual and expected output"),
    },
    "partial_fix": {
        "vi": _t("Test hiển thị đã pass nhưng test ẩn nhóm {failed_categories} còn fail{failed_tests}.",
                 "Một lỗi thường có các trường hợp tương tự; sửa xong cần kiểm tra cả chúng.",
                 "Sau khi sửa, tự chạy thêm các input gần với chỗ vừa sửa, nhất là giá trị ở giới hạn đề cho.",
                 "kiểm tra lại các input liên quan sau mỗi lần sửa lỗi"),
        "en": _t("The visible tests passed but hidden {failed_categories} tests still failed{failed_tests}.",
                 "A bug usually has related cases; after a fix, check them too.",
                 "After fixing, run inputs close to what you changed, especially values at the stated limits.",
                 "retry related inputs after every fix"),
    },
    "trial_and_error": {
        "vi": _t("Bạn sửa được lỗi sau {failing_runs} lần chạy fail.",
                 "Quá trình sửa cần khá nhiều lượt chạy; nêu giả thuyết trước mỗi lần chạy giúp mỗi lượt "
                 "có mục đích rõ hơn.",
                 "Trước mỗi lần chạy, ghi ngắn bạn nghĩ lỗi nằm ở đâu và chỉ sửa chỗ đó.",
                 "nêu giả thuyết về lỗi trước mỗi lần chạy"),
        "en": _t("You fixed the bug after {failing_runs} failing runs.",
                 "The fix took quite a few runs; stating a hypothesis before each run gives every run a "
                 "clearer purpose.",
                 "Before each run, note where you think the bug is and change only that.",
                 "state a hypothesis about the bug before each run"),
    },
    "quick_fix": {
        "vi": _t("Bạn sửa lỗi hiệu quả với ít lượt chạy lại.",
                 "Sửa đúng chỗ sớm giúp tiết kiệm thời gian và giữ code gọn.",
                 "Ở bài khó hơn, ghi lại vì sao bạn nghĩ lỗi nằm ở đó trước khi sửa.",
                 "giữ cách làm này ở một bài debug khó hơn"),
        "en": _t("You fixed the bug efficiently, with few reruns.",
                 "Fixing the right spot early saves time and keeps the code clean.",
                 "On harder exercises, note why you think the bug is there before changing it.",
                 "keep this approach on a harder debugging exercise"),
    },
    # ---------- Integrity ----------
    "integrity_flags": {
        "vi": _t("Hệ thống ghi nhận tín hiệu bất thường trong phiên làm bài ({signals}), nên điểm các trục "
                 "bị giảm.",
                 "CodeProve đánh giá cách bạn tự làm bài. Đây là tín hiệu hệ thống ghi nhận, không phải kết "
                 "luận: có thể có lý do hợp lệ.",
                 "Nếu bạn nghĩ hệ thống ghi nhận nhầm, hãy liên hệ đội CodeProve để được xem lại. Lần sau, "
                 "làm trọn bài trong editor và dùng Ciel ngay trên trang khi cần hỗ trợ.",
                 "làm trọn bài trong editor, dùng Ciel khi cần hỗ trợ"),
        "en": _t("The system recorded unusual signals in this session ({signals}), so the axes were reduced.",
                 "CodeProve assesses how you work yourself. This is a signal the system recorded, not a "
                 "verdict: there may be a valid reason.",
                 "If you think it was recorded by mistake, contact the CodeProve team for a review. Next time, "
                 "work entirely in the editor and use Ciel on the page when you need help.",
                 "work entirely in the editor and use Ciel when you need help"),
    },
}


class _Params(dict):
    def __missing__(self, key: str) -> str:
        return "?"


def _params(finding: Finding, locale: str) -> _Params:
    """The finding's params, with lists and counts turned into words for the sentence."""
    raw = finding.params
    params = _Params({k: v for k, v in raw.items() if k not in ("failed_categories", "failed_tests")})
    names = _CATEGORIES[locale]
    categories = [names.get(c, c) for c in raw.get("failed_categories") or []]
    params["failed_categories"] = _join(categories, locale) or _SOME_CASES[locale]
    tests = [f"“{name}”" for name in raw.get("failed_tests") or []]
    params["failed_tests"] = _FAILED_TESTS[locale].format(names=", ".join(tests)) if tests else ""
    paste, focus = _SIGNALS[locale]
    signals = [text.format(n=raw[key]) for key, text in (("paste", paste), ("focus_lost", focus)) if raw.get(key)]
    params["signals"] = _join(signals, locale) or "?"
    return params


def _join(items: list[str], locale: str) -> str:
    """"a", "a và b", "a, b và c" (en: "and")."""
    if len(items) < 2:
        return "".join(items)
    return f"{', '.join(items[:-1])} {_AND[locale]} {items[-1]}"


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
