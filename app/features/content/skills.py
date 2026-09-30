"""Skill tags (P3.2): the fixed taxonomy exercises are tagged with.

Each exercise carries 1-3 tags in its reviewed content file. They feed the
learner model (P3.3: an Elo rating per skill) and the recommendation (P3.4).
Labels are what the UI shows; the keys are the stable contract.
"""
TAXONOMY: dict[str, dict[str, str]] = {
    "hash-map": {"vi": "Bảng băm (dict)", "en": "Hash map"},
    "two-pointers": {"vi": "Hai con trỏ", "en": "Two pointers"},
    "sliding-window": {"vi": "Cửa sổ trượt", "en": "Sliding window"},
    "binary-search": {"vi": "Tìm kiếm nhị phân", "en": "Binary search"},
    "recursion": {"vi": "Đệ quy", "en": "Recursion"},
    "dynamic-programming": {"vi": "Quy hoạch động", "en": "Dynamic programming"},
    "graph": {"vi": "Đồ thị", "en": "Graphs"},
    "linked-structures": {"vi": "Danh sách liên kết, cây", "en": "Linked lists and trees"},
    "string-processing": {"vi": "Xử lý chuỗi", "en": "String processing"},
    "control-flow": {"vi": "Vòng lặp và điều kiện", "en": "Loops and conditions"},
    "null-handling": {"vi": "Xử lý dữ liệu thiếu", "en": "Missing data"},
    "error-handling": {"vi": "Xử lý ngoại lệ", "en": "Error handling"},
    "concurrency": {"vi": "Đồng thời, đa luồng", "en": "Concurrency"},
    "input-validation": {"vi": "Kiểm tra dữ liệu vào", "en": "Input validation"},
    "security": {"vi": "Bảo mật", "en": "Security"},
    "caching": {"vi": "Bộ nhớ đệm", "en": "Caching"},
    "data-structure-design": {"vi": "Thiết kế cấu trúc dữ liệu", "en": "Data structure design"},
}
MAX_SKILLS = 3
