# Kiểm định engine v2 trên bộ mẫu (P1.4, Task 7)

39 lượt mô phỏng của P1.3, chấm lại bằng engine v2 trên production. Lệnh dùng:

```
rescore --engine v2 --backfill-judges --keys keys.json --out engine_v2.json
```

Kết quả được so với điểm của 4 người chấm (`results-2026-09-26.md`). Cách so như sau:
- Spearman: điểm trục của engine so với mức trung bình của người chấm, chỉ tính các lượt mà đa số người chấm không chọn N/A.
- "N/A khớp": tỉ lệ lượt mà engine và đa số người chấm cùng chọn, hoặc cùng không chọn, "Không áp dụng".

## Kết quả

| Trục | Spearman v1 | Spearman v2 | N/A khớp v1 | N/A khớp v2 | Ngưỡng (plan P1.4) | Đạt |
|---|---|---|---|---|---|---|
| Thấu hiểu | 0,96 | 0,94 | 100% | 100% | không tụt quá 0,05 | ✓ |
| Giả thuyết | 0,89 | 0,94 | 100% | 100% | không tụt quá 0,05 | ✓ |
| Prompting | 0,57 | 0,90 | 100% | 100% | ≥ 0,70 | ✓ |
| Kiểm chứng | −0,36 | 0,61 | 87% | 100% | > 0,30 và N/A ≥ 90% | ✓ |
| Testing | 0,93 | 0,95 | 100% | 100% | không tụt quá 0,05 | ✓ |
| Debug | 0,69 | 0,96 | 87% | 87% | ≥ 0,69 và N/A ≥ 95% | ✓ / ✗ |
| **Tổng thể** | 0,92 | **0,95** | | | ≥ 0,90 | ✓ |

Cột "Spearman v2" là kết quả sau khi áp dụng quyết định về trục Debug (xem mục dưới). Engine v2 lúc chạy trên EC2 chưa có quy tắc này, khi đó Debug đạt 0,83 và tổng thể 0,94.

## Trục Debug

**Tiêu chí N/A (87%, ngưỡng 95%) chưa đạt, nhưng phần lệch đến từ người chấm.** Engine áp dụng đúng quy tắc: bài debug luôn chấm; bài implement là N/A khi chưa từng chạy fail. Có 5 lượt lệch:
- sim-24 và sim-40 là bài debug, nhưng đa số người chấm chọn N/A.
- Ở sim-01, sim-26 (pass ngay lần đầu) và sim-21, sim-38 (chưa chạy code của chính mình), người chấm chia đôi 2–2 nên không có đa số.

Đây chính là lỗi công cụ chấm đã ghi trong báo cáo P1.3: giữa 4 người với nhau chỉ đồng ý 41% về N/A ở trục này. Task 8 sửa trang chấm để người chấm không chọn được N/A trái quy tắc.

**Quyết định của chủ dự án (2026-09-26): "sửa được một phần" là mức 2.** Trường hợp này là test hiển thị pass hết nhưng test ẩn (trường hợp biên) còn fail khi Submit (sim-16, 19, 20, 22, 28, 36, 37).
- Bản v2 đầu tiên cho 0, trong khi người chấm cho 2–3.
- Đổi sang mức 2 thì Spearman của Debug tăng từ 0,83 lên 0,96, và tỉ lệ khớp đúng mức tăng từ 67% lên 88%. Hướng dẫn chấm đã được sửa theo.
- **Rủi ro:** quy tắc này được chọn dựa trên chính 24 lượt dùng để kiểm định, nên cần kiểm lại khi có bài làm thật.

## Còn lệch

- **sim-06, trục Kiểm chứng:** v2 cho mức 2, người chấm cho 0–1. Đây là hệ quả trực tiếp của quyết định "Ciel đưa code nhưng người học không dùng thì mức 2". Ở lượt này học sinh vốn làm kém, nên người chấm hạ điểm cả trục này.
- **Mức khớp đúng với trung vị người chấm (lệch không quá 0,5 mức):**

  | Trục | Khớp đúng mức |
  |---|---|
  | Testing | 97% |
  | Giả thuyết | 82% |
  | Prompting | 79% |
  | Thấu hiểu | 72% |
  | Kiểm chứng | 55% (n = 11) |

  Ở cả 5 trục này, ≥ 91% số lượt lệch không quá 1 mức. (Debug sau khi đổi quy tắc: 88% khớp đúng mức, xem mục trên.)

## Hạn chế

Giống báo cáo P1.3:
- Bộ mẫu là mô phỏng, do cùng một người viết.
- Người chấm chấm nhanh.
- Trục Kiểm chứng chỉ có 11 lượt.
- Các ví dụ mẫu trong prompt chấm lấy từ hướng dẫn chấm, không lấy từ bộ mẫu, nên phần LLM chấm không bị "học đáp án". Tuy vậy, quy tắc Debug ở trên được chọn dựa trên chính bộ mẫu.

Cần kiểm định lại trên ≥ 15 lượt thật trước P1.7.

## Quyết định

Bật engine v2 (`SCORING_ENGINE=v2`), rồi chấm lại toàn bộ báo cáo (quyết định của chủ dự án, 2026-09-26).
