# Model shortlist and deferred activation (2026-11-26)

Status: research only. Founder explicitly deferred Modal activation. No Qwen default, model download, paid resource provisioning or new inference dependency. Existing model identity/location is still unknown; evaluate it before adding another model.

| Capability | Candidates | Acceptance focus |
| --- | --- | --- |
| Chat and bounded tool reasoning | [Granite 4.2 3B](https://huggingface.co/ibm-granite/granite-4.2-3b), [Ministral 3 8B](https://huggingface.co/mistralai/Ministral-3-8B-Instruct-2512) | Structured responses, grounding, abstention, tool request schema, latency |
| Multimodal | [Gemma 4 E4B](https://huggingface.co/google/gemma-4-E4B-it) | Only if product need warrants; no guest document ingestion by default |
| ASR | [Whisper large v3 turbo](https://huggingface.co/openai/whisper-large-v3-turbo), [SunflowerASR](https://huggingface.co/Sunbird/SunflowerASR-51-african-languages), [NaijaVox 2.0](https://huggingface.co/Axiveri/NaijaVox-2.0) | Nigerian English, Pidgin, code switching, noisy hotel audio, privacy |
| TTS | [Chatterbox](https://github.com/resemble-ai/chatterbox), [Kokoro](https://huggingface.co/hexgrad/Kokoro-82M) | Pronunciation, latency, licensed preset voice; no cloning by default |
| Retrieval | [BGE-M3](https://huggingface.co/BAAI/bge-m3), [multilingual E5 small](https://huggingface.co/intfloat/multilingual-e5-small) | Tenant isolation, approved sources, retrieval quality; lexical retrieval remains usable |

No candidate is approved for production. Verify exact checkpoint and dependency licences, GPU/CPU requirements, deployment compatibility, Nigerian speech performance and cost on representative consented non-customer test inputs. Keep model IDs configurable; preserve the existing authenticated Modal chat/ASR/TTS contracts and existing SQL retrieval until separately approved. Embedding service is optional and not implemented by this note. Retain manual workflows, deterministic emergency handoff, server-side authorization, quota, explicit opt-in and human approval. No direct model database credentials or financial execution. When approved, fetch weights within cloud infrastructure and cache on persistent volume; use zero minimum containers where suitable and verify spend limits and authenticated inference before enabling per property.
