# Problems for Daily Bug Hunt: short enough that Ciel's solution fits in
# 10-20 lines (spec section 3). Separate from `exercises_seed.py` - those
# problems are sized for full graded exercises, not a 2-5 minute daily game.
# Each entry is a bilingual pair: the UI shows whichever matches the user's
# locale, and the English title doubles as the stable exclusion key for the
# 30-day no-repeat window.
DAILY_PROMPTS: list[dict[str, str]] = [
    {"vi": "Kiểm tra một số có phải số nguyên tố", "en": "Check whether a number is prime"},
    {"vi": "Tìm phần tử xuất hiện nhiều nhất trong danh sách", "en": "Find the most frequent element in a list"},
    {"vi": "Đảo ngược một chuỗi", "en": "Reverse a string"},
    {"vi": "Tính tổng N số Fibonacci đầu tiên", "en": "Sum the first N Fibonacci numbers"},
    {"vi": "Kiểm tra chuỗi có phải palindrome", "en": "Check whether a string is a palindrome"},
    {"vi": "Tìm số lớn thứ hai trong danh sách", "en": "Find the second largest number in a list"},
    {"vi": "Đếm số nguyên âm trong danh sách từ", "en": "Count vowels in a list of words"},
    {"vi": "Loại bỏ phần tử trùng lặp khỏi danh sách, giữ thứ tự", "en": "Remove duplicates from a list, keeping order"},
    {"vi": "Tìm ước chung lớn nhất của hai số", "en": "Find the greatest common divisor of two numbers"},
    {"vi": "Kiểm tra hai chuỗi có phải là anagram", "en": "Check whether two strings are anagrams"},
    {"vi": "Tính giai thừa của một số", "en": "Compute the factorial of a number"},
    {"vi": "Tìm phần tử còn thiếu trong dãy số liên tiếp", "en": "Find the missing number in a consecutive sequence"},
    {"vi": "Đếm số lần xuất hiện của mỗi ký tự trong chuỗi", "en": "Count occurrences of each character in a string"},
    {"vi": "Tìm cặp số trong danh sách có tổng bằng target", "en": "Find a pair of numbers that sums to a target"},
    {"vi": "Sắp xếp danh sách bằng bubble sort", "en": "Sort a list with bubble sort"},
    {"vi": "Tìm chuỗi con dài nhất không lặp ký tự", "en": "Find the longest substring without repeating characters"},
    {"vi": "Kiểm tra ngoặc đơn có cân bằng không", "en": "Check whether parentheses are balanced"},
    {"vi": "Tính trung bình cộng bỏ qua giá trị âm", "en": "Compute the average ignoring negative values"},
    {"vi": "Tìm phần tử xuất hiện đúng 1 lần trong danh sách có phần tử lặp", "en": "Find the element that appears exactly once in a list of duplicates"},
    {"vi": "Chuyển số nguyên sang chuỗi nhị phân", "en": "Convert an integer to a binary string"},
    {"vi": "Tính số ngày giữa hai mốc thời gian", "en": "Count the days between two dates"},
    {"vi": "Gộp hai danh sách đã sắp xếp thành một danh sách sắp xếp", "en": "Merge two sorted lists into one sorted list"},
    {"vi": "Tìm phần tử nhỏ nhất trong danh sách đã sắp xếp và xoay vòng", "en": "Find the minimum in a rotated sorted list"},
    {"vi": "Đếm số cách leo hết cầu thang (climbing stairs)", "en": "Count the ways to climb a staircase"},
    {"vi": "Tìm subarray liên tiếp có tổng lớn nhất (Kadane)", "en": "Find the maximum-sum contiguous subarray (Kadane)"},
    {"vi": "Kiểm tra ma trận vuông có đối xứng qua đường chéo không", "en": "Check whether a square matrix is symmetric across its diagonal"},
    {"vi": "Tìm k phần tử lớn nhất trong danh sách", "en": "Find the k largest elements in a list"},
    {"vi": "Nhóm các từ là anagram của nhau", "en": "Group words that are anagrams of each other"},
    {"vi": "Tính khoảng cách Levenshtein đơn giản giữa hai chuỗi ngắn", "en": "Compute a simple Levenshtein distance between two short strings"},
    {"vi": "Tìm phần tử chung giữa hai danh sách", "en": "Find the common elements between two lists"},
]
