# Worthkind Flow — owner console design preview

Open index.html locally in a browser. This is an original dependency-free, responsive HTML/CSS/JavaScript interface study for the **hotel owner** workspace, inspired by comparison of various hotel PMS and SaaS dashboard approaches. No code from the external projects was copied.

## Pages within the preview

- Overview: dashboard KPIs, illustrative weekly activity, room breakdown, tasks and operational principles.
- Guest inbox: staff-owned incoming requests.
- Reservations: source-labelled conceptual booking table.
- Operations: housekeeping, kitchen, IT/maintenance and events departments.
- AI agents: optional chat/voice/dining/events products, plan/permissions/approval placeholders.
- Usage & billing: distinct Worthkind subscriptions versus guest payments to hotels; budget display.
- Integrations: PMS, hotel payment service, model/knowledge and approved communication channels.

Navigation buttons switch static panels. Data values are **synthetic** and labels explicitly say so. There are no requests to a remote API, no secrets, no scripts or assets from CDNs, no authenticating users and no actual widget/payment/agent activation. Deliberately disabled controls are not an implementation.

## Implementation proposal

Use Next.js/TypeScript, with MIT shadcn/ui and a reviewed MIT dashboard starter as candidate component sources, backed by the existing Worthkind Flow API boundary and a secure tenant identity model. This HTML file is a visual reference, not a component library or production app to deploy. Use real authenticated property-scoped queries with source and freshness labels before showing operational KPIs.

Follow ../../docs/reuse/SOURCE_AND_LICENSE_REGISTER.md and ../../docs/reuse/PLATFORM_BLUEPRINT.md, plus the existing 15-domain master architecture. Do not expose this preview as an active hotel dashboard or submit guest information to it. No external repository is vendored in this change.

## Manual review targets

- Desktop widths 1440 and 1024; mobile widths 768, 390, 320.
- Keyboard focus and navigation switching; screen headings and hidden panel accessibility.
- Synthetic numbers only and no actionable checkout, installation or production claims.
- Contrast, overflow, error/empty-state and reduced-motion review before converting to React.
