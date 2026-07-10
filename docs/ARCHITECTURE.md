# Architecture

v0.2 removes the old role-pipeline contract and replaces it with four deterministic concerns:

1. autonomous execution without step-by-step human approval;
2. deterministic audit reconstruction through append-only journal and Run Report artifacts;
3. learning extraction into runtime learning state;
4. validated OKF LLMWiki updates through a Python transaction layer.

The runtime surface is intentionally smaller than the v15/v0.1 line:

- journal recording;
- learning extraction;
- next-turn handoff generation;
- audit checks and Run Report generation;
- OKF bundle validation and transactional apply.

The frame-* skill family remains as the only skill family kept from the previous layout. Everything else that used to drive Gatekeeper, Sensemaker, Meta-Evaluator, memory promotion, or loop brief pattern capture is removed from the v0.2 branch.

The design principle is simple: block only what directly threatens safety or bundle integrity, and report everything else as a post-run alert.
