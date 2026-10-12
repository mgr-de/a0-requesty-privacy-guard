# Routing regression coverage for CPU PII evaluation

PII inference remains in `a0-local-privacy-guard`. That companion's `feat/cpu-pii-evaluation` branch adds an explicit optional offline Nym ONNX backend and aggregate CPU benchmarks. This repository does not add a detector, change the default, or change Requesty/local routes.

The added test verifies that local endpoint recognition is unaffected by detector selection: `local`, `presidio`, and `nym` cannot permit a remote or credential-bearing endpoint. Existing native suites cover guarded transports, streams, ownership, model gates, structured data and policy.

The local guard benchmark runs regex/spaCy, Presidio and Nym against one annotated synthetic DE/EN/mixed corpus, with production mappings, isolated workers and reproducible artifacts. Its native mode adds actual `PayloadFilter` input/output checks around a simulated echo. The local Ollama smoke goes through the native privacy wrapper and accepts only host-local HTTP endpoints. No Requesty calls are made.

Run each plugin suite separately in a clean, isolated Agent Zero checkout. Refer to the local guard's `docs/CPU-DETECTOR-EVALUATION.md` for setup, commands, measurements, limits and result interpretation. Live Requesty testing requires a separately established budget; credentials stay outside source control and reports.
