# Worthkind Flow — source selection and license gate

**Status (19 November 2026):** engineering research and intake decisions, not proof of installed libraries, running integrations or deployment. This document lives on a feature branch based on the draft master architecture branch. Do not merge straight into main.

## Integration principle

Worthkind Flow is the product and the tenant/guest source-of-truth router. Use external projects as design research, standalone integrations, or individually reviewed libraries. Do not vendor complete third-party hotel apps into one directory. This preserves security boundaries, maintainability, distinct brands and license obligations. No third-party source files were copied by this change.

## Preferred shortlist

| Source | Upstream | Confirmed licensing / status | Intended extraction | Decision |
| --- | --- | --- | --- | --- |
| Our own Hotel OS | https://github.com/NIDHOGGR-shadow/hotel-os | Our own separate private source; code and rights need internal review | Hotel-site catalog, booking/Paystack adapters; hotel data and real-world payment verification are separate | ADAPT after tests |
| Our own Zuvamo / verodesk | https://github.com/NIDHOGGR-shadow/verodesk | Our own separate private source; integration requires code audit | Chat, voice, transport/channel adapters, safe tool orchestration | ADAPT behind Worthkind Flow policy |
| Kiranism Next Shadcn Dashboard Starter | https://github.com/Kiranism/next-shadcn-dashboard-starter | MIT LICENSE confirmed | React dashboard shell, navigation, cards, tables | CANDIDATE; copy only selected reviewed files after dependency/license audit |
| shadcn/ui | https://github.com/shadcn-ui/ui | MIT LICENSE.md confirmed | Accessible UI building blocks | USE at frontend implementation stage |
| assistant-ui | https://github.com/assistant-ui/assistant-ui | MIT LICENSE confirmed | React chat surface only; not a secure agent runtime | USE at optional AI-chat stage |
| openstay | https://github.com/antsal06/openstay | MIT LICENSE confirmed | Patterns for date-scoped room inventory, holds, idempotency and booking UX | STUDY / SELECTIVE REUSE after real PMS capability mapping |
| Chatwoot | https://github.com/chatwoot/chatwoot | MIT core with additional/non-core restrictions; check file-level license and SaaS terms | Separate staff conversation inbox, audited human takeover by API | EVALUATE standalone integration |
| OpenMeter | https://github.com/openmeterio/openmeter | Apache-2.0 LICENSE confirmed | Usage event ingestion and aggregation; subscription rating requires separate billing ledger | EVALUATE; no live billing implied |
| Langfuse | https://github.com/langfuse/langfuse | MIT core, enterprise directories excluded (see root LICENSE) | Agent tracing, prompt and evaluation observability with PII redaction | EVALUATE standalone |
| Vercel nextjs-subscription-payments | https://github.com/vercel/nextjs-subscription-payments | MIT LICENSE confirmed | Example subscription lifecycle, entitlement reconciliation | STUDY; Stripe example, not ready-made Paystack billing |
| QloApps | https://github.com/Qloapps/QloApps | OSL-3.0 core; some modules have AFL-3.0 or their own applicable licenses | Hotel booking/PMS workflow and calendar UX reference | REFERENCE ONLY until legal and file-level review |
| Kamra PMS | https://github.com/Kamra-PMS/kamra-pms | AGPL-3.0 license.txt confirmed | Front desk, housekeeping, kitchen, restaurant and operational models | REFERENCE ONLY; consider approved standalone integration, not copy-paste |
| Hotelier Suite | https://github.com/hotelier-suite/hotelier-frontend | No root LICENSE found in review on 19 Nov 2026 | Layout, card rhythm, reservation and staff dashboard inspiration | VISUAL REFERENCE ONLY, do not copy source |
| Hotel Management Web App | https://github.com/hotel-management-web-app/client | No root LICENSE found in review on 19 Nov 2026 | Dashboard KPIs, room and booking tables inspiration | VISUAL REFERENCE ONLY, do not copy source |
| Flowise | https://github.com/FlowiseAI/Flowise | Apache-2.0 core; commercial enterprise exclusions; upstream public archive reported | Agent workflow ideas | NOT SELECTED as primary runtime; existing Zuvamo adapter first |
| Dify | https://github.com/langgenius/dify | Modified Apache-based Dify Open Source License with extra commercial conditions | Workflow inspiration | NOT SELECTED for embedded SaaS source |

**Copyright:** Keep upstream copyright/license notices with any actual copied or substantially derived code, record path + upstream commit SHA, inspect transitively bundled assets/fonts/icons, and recheck licenses before importing or upgrading. An MIT license is not a security audit or assurance of compatibility; AGPL/OSL review is separate from technical feasibility. A public repository without a verified permission grant is not permission to copy.

## Ranked extraction order

1. Build an original Worthkind-branded UI and tenant role model. Start from small MIT UI components, not from a whole unrelated hotel app.
2. Wire property-scoped enquiry -> staff queue -> auditable reply with no AI, preserving the current P0 backend.
3. Add hotel manager invitation, tenant-aware authorization, page/content ownership and operational KPIs.
4. Adapt Worthkind-owned Zuvamo chat/voice to a typed, policy-gated agent service. AI is optional and cannot manufacture confirmations.
5. Build paid entitlements, meter events, actual invoices/processor settlement, feature flags and spend ceilings. Agent becomes embeddable only after verified hotel domain + subscription entitlement.
6. Integrate hotel-owned PMS/booking authority and payment gateway for real inventory and booking; never equate hotel booking payments to Worthkind subscription payments.
7. Add dining/housekeeping/event modules and approved outbound channels only as hotel workflows require.

## Reuse gate (must be completed before integrating external source)

- Confirm project ownership, exact upstream commit, source path, license and notice obligations.
- Inspect dependencies, security advisories, exposed client secrets and dangerous defaults.
- Document where guest data, staff data, AI prompts and hotel money are stored and transmitted.
- No cross-tenant data access; service-side authorization, role checks and database isolation tests.
- API contracts, webhook signature/nonce/replay protection, idempotent state changes and dead-letter retries.
- Test with fake tenant data locally; no production data or credentials in repo or screenshot.
- Include upstream notice file and a dependency inventory for imported code.
- Demonstrate rollback and a no-AI direct/human path.

## Not currently built by this register

No code has been pulled from upstream here; this is a legally cautious, actionable intake register. No operational subscriptions, live agents, production bookings, PMS calls, channel messages, payment processing or hotel customers are claimed. See the architecture and original design preview beside this document.
