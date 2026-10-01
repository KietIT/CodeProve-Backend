# Legal texts

- [chinh-sach-quyen-rieng-tu.md](chinh-sach-quyen-rieng-tu.md): the privacy policy (vi + en). It is a **draft** until the team approves it.

## How to publish or change the policy

1. **Fill every `[NHÓM ĐIỀN: …]` / `[TEAM: …]`:**
   - organisation and address;
   - AWS region and frontend host;
   - retention periods;
   - response time;
   - minimum age;
   - a link to OpenAI's current API data terms.
2. **Team review.** If possible, a person with legal expertise checks it against Nghị định 13/2023/NĐ-CP, including whether a cross-border transfer impact assessment is needed. This file is not legal advice.
3. **Keep it true to the system.** The text must describe what the code does. Check, at least:
   - what is sent to OpenAI (`app/features/privacy/scrub.py`, `store=False` in `app/features/mentor/client.py`);
   - what the learner brief contains (`app/features/learner/brief.py`);
   - which endpoints need consent (`require_consent`);
   - that self-service deletion and export do not exist yet (P3.8), so the policy says "by email".
4. **Publish.** The frontend renders the approved text on `/privacy`.
5. **Every later change** to the meaning of the text needs a new `POLICY_VERSION` in `app/features/privacy/service.py` and a matching version line here. Everyone is then asked for consent again before the AI features work. A typo fix may keep the version.

## Known gaps to close (P3.8)

- Withdrawal of consent, data access and copy, and account deletion are handled by email. There is no self-service API yet.
- Retention periods are not enforced by a job yet.
