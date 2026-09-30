# P3.1 Ciel Remembers the Attempt — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ciel sees the conversation of the current attempt: the last 6 exchanges are sent as chat history (P3 decision 4). Today every message goes with `history=[]`.

**Architecture:** `mentor/service.mentor_reply` loads the attempt's last 6 `PromptLog` rows (what the student saw: withheld replies were already replaced), oldest first, as user/assistant messages, each capped at 2 000 characters and 8 000 in total (dropping the oldest first), and passes them to every `client.chat` call of that message (first try and the P2.1/P2.2 retry). Nothing else changes: guards, events, logs. No migration, no frontend change.

**Scope decided in the P3 design:** within one attempt only; across attempts Ciel will know the student only through the learner brief (P3.3/P3.5), never raw chat.

## Tasks

1. `mentor/memory.py`: `attempt_history(db, attempt_id) -> list[dict]` (limit 6, caps as above). Tests: order, the 6-exchange limit, per-message and total caps, empty attempt.
2. `mentor_reply` passes the history to both calls. Tests: the second question sees the first exchange; a withheld reply appears as the text the student saw; other attempts' messages never appear.
3. Full suite, commit, push; Kiệt merges and deploys (no EC2 command).
