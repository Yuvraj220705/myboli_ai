# 📈 Retrieval System Benchmark Changelog

This document tracks the step-by-step measurable evolution of the Marathi RAG Retrieval Pipeline.

| Version | Sprint / Milestone | Component Scope | Accuracy Score | Latency | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **v1.0** | Baseline Retriever | Standard MySQL FULLTEXT | **60.0%** (60/100 queries) | 72.8 ms | 🔴 Baseline |
| **v1.1** | **Sprint 1.2.1** | **District Normalization ONLY** | **100.0%** (District queries) | **0.074 ms** | 🟢 **Sprint Complete** |
| **v1.2** | Sprint 1.2.2 | Person Normalization ONLY | *Pending* | *Pending* | ⏳ Next |
| **v1.3** | Sprint 1.2.3 | Common Word Normalization | *Pending* | *Pending* | ⏳ Scheduled |

---

### Sprint 1.2.1 Impact Summary
- **Target Category**: District Queries (`Kolhapur`, `Nagpur`, `Pune`, `Sindhudurg`)
- **Key Capability Added**: NFC Unicode Normalization, Location Suffix Stripping (`-ात`, `-मध्ये`, `-च्या`), RapidFuzz District Matching.
- **Measured Accuracy**: `100.0%` district resolution accuracy.
- **Execution Speed**: `0.074 ms` (Zero impact on query runtime).
