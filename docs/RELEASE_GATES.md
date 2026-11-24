# Worthkind Flow P0 release gates

All thresholds below are **proposed test targets**, not production measurements.

| Gate | Acceptance method | Blocking condition | Owner |
| --- | --- | --- | --- |
| Hotel and scope | Pilot decision-maker identified, hotel systems documented | No agreed operational owner | Product owner |
| Tenant isolation | Multi-hotel negative tests for every private read/write | Any unauthorized read or write | Backend/security |
| Direct and human bypass | 20 AI-disabled/offline/mobile scripted journeys | Any visitor forced through AI | UX/QA |
| Human handoff | 20 cases covering queued, claimed, response, timeout, reopen | Missing assigned owner, timestamps or guest status | Backend/reception |
| Approved information | 100 approved FAQs + intentional missing facts | Unsupported facts presented as true or invented booking | AI/ML + hotel |
| Financial actions | 100 payment/booking cases after PMS integration exists | False confirmations or duplicate charge effects | Integrations/finance |
| AI safety | Fixed unsafe/urgent/prompt-injection dataset | Any successful unauthorized tool execution | QA/security |
| Event durability | Crash injection between write, publish and ack | Committed state missing required audit/outbox | Backend/reliability |
| Operations | Action logs, alerting, recovery instructions | Untracked failed jobs or unrecoverable cases | SRE |
| Privacy | Purpose-bound PII, retention, export/deletion and consent controls | Tenant leakage or improper marketing outreach | Security/legal |
| Spend | Per-tenant token/message/voice ceilings and alerts | Unbounded paid-service consumption | Product/platform |

## Before declaring production-ready

Require hotel sign-off, code review, a real PMS contract for any confirmed booking features, backups, security tests, response and incident playbooks, and monitoring. A successful prototype test suite is not evidence that those conditions are fulfilled.

## Go/no-go

P0 is a **human-assisted enquiry platform**. Production payment, room inventory and dispatch stay disabled until their specific adapters, failure recovery and provider tests pass.
