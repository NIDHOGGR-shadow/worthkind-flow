# ML: deferred and guarded

First release uses **deterministic rules** for human/emergency bypass and basic intent categories. A language model is not required to route or store a guest enquiry. The low-quality synthetic classifier from the earlier experimental package is **not deployed** here.

Before any supervised ML model is used for guests:
- Obtain consented, annotated and de-identified real cases with documented hotel policies.
- Split data by time and property and compare every model with the rule baseline.
- Validate unsafe-intent recall, macro-F1, per-class errors, grounding, latency, handoff and token costs.
- Version evaluation fixtures, prompts, model, retrieval index and tool schemas.
- Shadow test, canary and roll back. Never auto-train on private conversations.
- Keep financial and booking truth in authorized PMS/payment systems.

[Full ML decisions](../docs/ML_DECISIONS.md) · [Original inference and release flow](../docs/v5/diagrams/02-ml-inference-and-release.mmd)
