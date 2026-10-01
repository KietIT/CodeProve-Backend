# Ciel: Reply Language and Piecemeal Solution Leak — Fix Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Reported by Kiệt (2026-10-01, CP-006 Count Word Frequency):**
1. After an English first message, Ciel kept answering in English when the student switched to Vietnamese.
2. Ciel gave the solution in pieces:
   - `words = text.lower().split()` in one reply;
   - `word_counts[word] = word_counts.get(word, 0) + 1` in a loop in a later reply, once more as a "different context" `counts[item] = counts.get(item, 0) + 1`.
   Together these are the whole reference solution.

**Causes:**
1. **Language.** The only language rule is "answer in the user's language" in the system prompt. With the attempt's history (P3.1) all in English, the model follows the history.
2. **Leak.**
   - The P2.1 guard withholds a reply only when its own code passes every visible test. Fragments never do, and fragments spread over several replies are never checked together.
   - The P3.5 fresher hint style allows "one tiny generic snippet (≤ 5 lines) of a building block". On a 3-line exercise, a building block *is* the solution.

---

## Decisions to approve

1. **Language per turn.**
   - The server detects the language of the student's latest message:
     - Vietnamese when it has Vietnamese letters (ă â đ ê ô ơ ư or tone marks), or at least 2 common unaccented Vietnamese words (e.g. "toi", "giup", "khong", "bai", "lam");
     - English when it has words but none of those;
     - otherwise (code only, "ok", numbers) the language of the student's previous detectable message.
   - The turn's system message (after the history) then says: "Reply in Vietnamese / English, whatever language earlier messages used."
2. **Tighter fresher hint style.**
   - Ciel may name the concept or data structure and describe steps in words.
   - Code only for general Python syntax that is not a step of this exercise. It must never show code for any step of the exercise, even renamed or "in a different context".
   - This replaces the "one tiny snippet of a building block" allowance approved in P3.5. Junior and senior stay as they are.
3. **New "solution overlap" guard, next to the P2.1 test guard.**
   - **Input:** the code in the new reply *plus* the code of Ciel's earlier replies in the same attempt.
   - **Normalisation:** identifiers are renamed to a placeholder (keywords, builtins and method names are kept), whitespace is ignored.
   - **Rule:** if that code covers **≥ 50%** of the token 5-grams of the reference solution's core lines (all lines except `def`, `return`, `import`, `pass`, comments and blanks), the reply is withheld. It then goes through the same retry with a stricter instruction, then the existing fallback message.
   - **Why it works here:** in CP-006 the renamed `counts[item] = counts.get(item, 0) + 1` and `.lower().split()` match the reference's core.
   - **Why cumulative:** drip-feeding over several replies is caught. A single short generic snippet is not enough.
   - **Threshold check before release:**
     - on all 30 exercises, pasting the reference's core into a reply must trigger it;
     - a set of generic snippets (a plain loop, an empty dict, a print) must not;
     - each mutant's core (a near-solution) must trigger it.
   - The 50% is adjusted if this check fails, and I report the numbers before shipping.
   - The reference solution never leaves the server; the guard only compares.

---

### Task 1: Language per turn
- `app/features/mentor/language.py`: `detect(text) -> "vi" | "en" | None` and `reply_language(message, previous_prompts)`.
- In `mentor_reply`, the language rule goes first in the turn instruction.
- Tests:
  - Vietnamese with and without accents;
  - English;
  - code-only messages fall back to the previous message;
  - the rule reaches the turn system message after the history;
  - the switch from English to Vietnamese mid-attempt flips the rule.

### Task 2: Fresher hint style
- Update `HINT_STYLE["fresher"]` in `app/features/mentor/prompts.py`.
- Update the P3.5 tests that quote it.

### Task 3: Solution-overlap guard
- `app/features/mentor/overlap.py`:
  - `normalize(code) -> list[str]` tokens;
  - `core_ngrams(reference)`;
  - `coverage(reference, code_blocks) -> float`;
  - `OVERLAP_THRESHOLD = 0.5`.
- `guard.py`: `leaks_solution(db, exercise, attempt_id, reply_text)` collects the code blocks of earlier `PromptLog` responses in the attempt plus this reply. It fails open (logged) if the reference is missing.
- `service.py`: the overlap result joins `withheld` (same retry + `FALLBACK`); the AI_REPLY payload records `withheldOverlap`.
- Tests:
  - the CP-006 transcript from the screenshots is withheld on the second piece;
  - every exercise's reference core is withheld;
  - generic snippets pass;
  - P2.1/P2.2 tests unchanged.
- Calibration script `python -m app.features.mentor.overlap_check` prints the coverage of references, mutants and generic snippets for the 30 content files.

### Task 4: Check and ship
- Rerun the CP-006 scenario by hand on staging and in the P3.5 check sheet (scenario 1).
- No migration. On EC2:

```bash
cd ~/CodeProve-Backend && git pull origin main && docker compose up -d --build
```
