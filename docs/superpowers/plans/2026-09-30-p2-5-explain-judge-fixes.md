# P2.5 Explain-back Judge Fixes — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Status:** approved by Kiệt with the request to implement it right away (2026-09-30).

**Goal:** Fix the two explain-back problems the team found in the P1.5 review: (1) the judge rated as strong an explanation of code the tests show is wrong (items 3a, 8b: "a lock makes it safe" for a `with threading.Lock():` created on every call); (2) a question asked about a technique the student did not use (item 12a: "partition" when the code merged the two arrays).

**Architecture:** (1) The explain judge also receives the student's final code and the submit-suite result (passed/total and up to 3 failing hidden test names), with a rule: an answer that presents code the tests show wrong as correct is at most level 1 (score ≤ 7). (2) The question generator is told to ask only about what the final code does, never about techniques named in the problem or usual for it but absent from the code. Stored verdicts are not re-asked (old sessions keep their scores, decision 6); the effect is measured in P2.6.

## Tasks

1. `judges.judge_explain(client, question, answer, context="")`: the context block goes before the question; `EXPLAIN_SCORE_SYSTEM` gets the rule. `scoring_service.explain_context(code, suite)` builds it (code capped at 60 lines; suite line; failing hidden test names). `score_with_explanations` and `backfill` pass it. Tests: context present in the judge's input, rule in the prompt, no context when there is no code, trivial answers still skip the call.
2. `EXPLAIN_QUESTION_SYSTEM`: ask only about constructs that appear in the final code; if the code fails tests, one question may ask how it handles the failing case, without saying what is wrong. Test: the rule is in the prompt and the final code is what the generator sees.
3. Full suite, commit, push; Kiệt merges and deploys (no migration, no rescore).
