# Worthkind Flow — model selection and evaluation

## Model-by-job matrix

| Task | P0 implementation | Candidate later | Evaluation |
| --- | --- | --- | --- |
| Human/emergency bypass | Deterministic phrase + UI controls | Keep hard-coded bypass | 100% on mandatory fixed release set |
| Guest intent | Rules first with clarification | Supervised classifier, tested by property/language | Macro-F1 and per-class recall vs rule baseline |
| FAQ / hotel policies | Approved tenant-filtered lexical retrieval | Embeddings + reranker + versioned index | Correctness and abstention on missing facts |
| Response wording | Approved templates; optional tool-constrained LLM | Retrieval-grounded LLM | Hallucination rate, latency, cost |
| Voice | Disabled until channel policy and handoff ready | STT + TTS evaluated on local speech | Intent WER, transcription failure and handoff |
| Food ETA | No prediction | Supervised regression after order data | MAE by kitchen, route and time |
| Occupancy forecast | No prediction | Time-series baseline before complex ML | WAPE or MASE and stability |
| Ad optimization | No autonomous spend | Conversion attribution, later experiments | Incremental ROI, budget guardrail |

## MLOps policy

1. Collect only approved and purpose-limited operational data.
2. De-identify and label examples; do not auto-train on conversations.
3. Split evaluation to avoid contamination between properties and repeat guests.
4. Compare candidate model against the simple rule baseline.
5. Gate prompts, retrieval indexes, schemas, tool versions **as well as** models.
6. Shadow-test before deployment; log policy overrides and failed/abstained routes.
7. Version every release; establish human-reviewed rollback.
8. Monitor intent confusion, unsupported answers, handoff, cost per conversation and drift.

Previous synthetic training baseline accuracy (~37% holdout) is insufficient; **custom ML routing is disabled for real guests**. The "ML layer" is an optional assistive component, never a payment or hotel booking authority.

References: https://scikit-learn.org/stable/modules/model_evaluation.html ; https://owasp.org/www-project-top-10-for-large-language-model-applications/ ; https://fastapi.tiangolo.com/
