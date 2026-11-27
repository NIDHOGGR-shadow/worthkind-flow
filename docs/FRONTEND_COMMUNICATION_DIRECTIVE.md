# Worthkind Flow — frontend communication directive

Approved product direction, 2026-11-26. This supersedes standalone AI Studio in the frontend completion directive; the rest of the original 15-domain product scope and frontend ownership remain unchanged.

## Product experience
- One Communication Hub for hotel guest enquiries, staff ownership, responses, transfers, escalation, and resolution. Integrate it with departmental work, schedules, reservations and notifications. Prefer a searchable inbox and focused request details on desktop and mobile.
- Guest text/voice assistance is optional. Direct human reception remains accessible without a model. On AI abstention or explicit human request, offer an editable human enquiry using only the guest-selected context. Do not send a request without explicit submission. Do not claim staff acceptance before the server confirms it.
- Keep AI policy, approved knowledge and usage limits under Hotel settings / Assistant settings. Staff assistance belongs in Communication Hub; operational alerts and approval proposals belong in Department work. No standalone AI Studio in navigation.
- Present real status, authorized records, clear actions, and responsive accessible UI. Hide technical IDs except when needed for support or receipt recovery. Do not create fake messages, delivery receipts, availability indicators or bookings.

## Current contract and ownership
Use existing versioned property-scoped case queue, claim, respond and control APIs. Current guest receipt returns case status and latest staff reply, not a full live conversation history. The initial Hub is a request inbox, not a verified real-time chat. Existing schedule read may expose authorized staff members; scheduled duty is not confirmed presence or availability. Use named staff selection when authorized; do not guess transfer targets.

Backend owner: add persistent guest/staff conversation threads and append-only messages, explicit human handoff, authorized routing by department/shift/availability/workload, claim/accept, escalation timers, staff notifications and delivery receipts, guest confirmation/reopen, conversation pagination/unread and subscription or polling contract. Provide a scoped staff directory and capability/role contract. Publish exact APIs; preserve direct reception when AI is unavailable. Do not expose private transcript to unrelated staff or allow AI to claim human acceptance. No separate AI Studio expansion.

Frontend owner: inspect existing Brilliant design, update communication layout and assistant placement without restarting completed work; original canvas reached its 64 chat edit limit, so preserve it and document any unverified canvas changes. Implement available UI contracts, test, commit to work/frontend-neutral-redesign, and continue the remaining frontend assignment. Do not change backend infrastructure or simulate unavailable business operations.

## Acceptance
Guest can ask for a person directly; an AI handoff can open the human enquiry with consented context; guest can track confirmed staff response through the existing receipt. Staff can browse/search authorized cases, accept/respond/transfer/escalate/resolve using current server contract. Policy controls remain under settings. Operational alerts/proposals are in department work. All private state clears on property switch/sign-out. Mobile and desktop browser tests cover new navigation and workflows. Full conversation routing and real-time human messaging stay unverified until backend contract and integrated tests exist.
