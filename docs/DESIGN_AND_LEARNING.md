# Worthkind Flow — Design handoff and learning

## Editable UI references

- [Worthkind Flow Figma screens](https://www.figma.com/design/AowGGCbv6F6UjzCuygzniY): guest website, optional AI, owner dashboard, reception, food mobile, careers/suppliers and control center.
- [Original platform FigJam architecture](https://www.figma.com/board/yRipnEN64R7kUvIHr6vLCH): high-level first visual. Prefer the **corrected v5** diagrams in [v5/diagrams](v5/diagrams/) for implementation.
- Local demo guest and reception HTML screens: `../apps/web/`.

## Product founder's role

Interview a real hotel manager/receptionist, obtain system/provider details, measure missed enquiries/response time, define priorities, approve copy and policies, secure pilot permission and sign off staged releases. Do not become the sole backend, ML, QA, sales and support owner.

## Engineering learning route

1. **HTTP APIs and backend:** https://fastapi.tiangolo.com/tutorial/ — distinguish user interaction and verified business result.
2. **Access control:** https://supabase.com/docs/guides/database/postgres/row-level-security — tenant isolation, private guest information and staff boundaries.
3. **AI safe actions:** https://owasp.org/www-project-top-10-for-large-language-model-applications/ — prompt injection, tool abuse and policy enforcement.
4. **ML evaluation:** https://scikit-learn.org/stable/modules/model_evaluation.html — confusion matrices, calibration and baseline comparison.
5. **Payments:** https://paystack.com/docs/payments/verify-payments/ — server-side verification, idempotency and reconciliation.
6. **Provider webhooks:** https://docs.stripe.com/webhooks — signatures, retries and unordered delivery.
7. **Responsible release practice:** https://www.nist.gov/itl/ai-risk-management-framework — evidence, evaluation and human accountability.

Suggested exercise: take [03-first-slice-booking-handoff.mmd](v5/diagrams/03-first-slice-booking-handoff.mmd) and write the expected system response when PMS is unavailable, when AI is down, when a receptionist fails to accept a case and when payment is verified but the booking is not.

## QA handoff

Test on 320px, 390px, 768px and desktop, screen reader and keyboard, low-bandwidth and interrupted sessions. Distinguish fully simulated design screens from production-integrated hotel behavior. Prices, inventory, ratings and staff response times are never placeholders presented as facts.
