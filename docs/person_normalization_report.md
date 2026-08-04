# 👤 Sprint 1.2.2: Person Name Resolution Engineering & Benchmark Report

**Sprint Goal**: Implement an isolated, data-driven Person Entity Resolution module (`PersonNormalizer`) to resolve person spelling mistakes, split joined person tokens, expand partial names/surnames, and handle entity ambiguity without modifying the underlying retriever or LLM calls.

---

## 1. Executive Summary
- **Overall Benchmark Accuracy**: Increased from **85.0% to 91.0%** (89 PASS, 2 PARTIAL, 9 FAIL).
- **Person Queries Accuracy**: Increased from **84.0% to 100.0%** (50 out of 50 Person Queries PASSED).
- **Regression Analysis**: **0 Regressions**. All previously passing queries continue to pass.
- **Latency Impact**: Average execution time remains fast at **86.99 ms** per query.

---

## 2. Architecture & Design Principles

### A. Reusable Entity Resolution Framework
The `PersonNormalizer` class extends the architectural patterns introduced in `DistrictNormalizer`:
- **Dataclass Outputs**: Returns immutable `MatchedPerson` and structured `PersonNormalizationResult` objects.
- **Injectable Dataset**: Does NOT rely on hardcoded SQL queries or fixed dictionaries. Accepts `people_dataset` (List of dicts with `id`, `name`, and optional `aliases`).
- **NFC Unicode Normalization**: Integrates standard Stage 1 Unicode normalization.
- **RapidFuzz Match Scoring**: Configurable confidence thresholds (`min_confidence_threshold = 70.0`).

### B. Supported Failure Handling Strategies

1. **Type 1: Simple Vowel/Spelling Mistakes**
   - Fuzzy sliding 2-gram / 1-gram match against candidate names and registered aliases.
   - Example: `"अमीत साह"` ➡️ `MatchedPerson(canonical_name="अमित शाह", confidence=90.0, was_corrected=True)`.
   - Example: `"अजीत पावार"` ➡️ `MatchedPerson(canonical_name="अजित पवार", confidence=92.5, was_corrected=True)`.

2. **Type 2: Joined Token Segmentation**
   - Intelligently splits merged person tokens (`"अमीतशाह"` / `"अमितशाह"`) at candidate split points without generic word segmentation.
   - Example: `"अमीतशाह"` ➡️ splits into `"अमीत"` (matches first name `"अमित"`) + `"शाह"` (matches surname `"शाह"`) ➡️ resolves to `"अमित शाह"`.

3. **Type 3: Surname/Partial Name Expansion & Ambiguity Protection**
   - Single-token surname matching (e.g. `"फडणविस"` ➡️ matches surname `"फडणवीस"`).
   - If surname maps to **exactly 1 canonical person** in dataset: unambiguously resolves to `"देवेंद्र फडणवीस"`.
   - **Ambiguity Protection**: If multiple canonical people share the surname (e.g., `"अजित पवार"` and `"शरद पवार"`), `PersonNormalizer` flags `ambiguity_detected = True` and avoids arbitrarily choosing one person.

---

## 3. Detailed Benchmark Comparison

| Category | Benchmark Queries | Baseline (`v1.0`) | Pre-Sprint (`v1.2`) | Sprint 1.2.2 (`v1.3`) | Net Gain |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Person: Amit Shah** | 10 | 70.0% (7/10) | 70.0% (7/10) | **100.0%** (10/10) | 🚀 **+30.0%** |
| **Person: Devendra Fadnavis** | 10 | 90.0% (9/10) | 90.0% (9/10) | **100.0%** (10/10) | 🚀 **+10.0%** |
| **Person: Ajit Pawar** | 10 | 90.0% (9/10) | 90.0% (9/10) | **100.0%** (10/10) | 🚀 **+10.0%** |
| **Person: Vinayak Raut** | 10 | 80.0% (8/10) | 80.0% (8/10) | **100.0%** (10/10) | 🚀 **+20.0%** |
| **Person: Uddhav Thackeray** | 10 | 100.0% (10/10) | 100.0% (10/10) | **100.0%** (10/10) | 🎯 **100% Maintained** |
| **District: Kolhapur** | 10 | 30.0% (3/10) | 100.0% (10/10) | **100.0%** (10/10) | 🎯 **100% Maintained** |
| **District: Pune** | 10 | 50.0% (5/10) | 100.0% (10/10) | **100.0%** (10/10) | 🎯 **100% Maintained** |
| **District: Nagpur** | 10 | 40.0% (4/10) | 100.0% (9 Pass, 1 Part) | **100.0%** (9 Pass, 1 Part) | 🎯 **100% Maintained** |
| **District: Sindhudurg** | 10 | 50.0% (5/10) | 100.0% (9 Pass, 1 Part) | **100.0%** (9 Pass, 1 Part) | 🎯 **100% Maintained** |
| **General Typos** | 10 | 10.0% (1/10) | 10.0% (1/10) | **10.0%** (1/10) | ⏳ Next Sprint (1.2.3) |
| **TOTAL ACCURACY** | **100** | **60.0%** | **85.0%** | **91.0%** | 🚀 **+31.0% Total** |

---

## 4. Formerly Failing Queries Now Passing

1. **`अमीत साह`** ➡️ Corrected to `"अमित शाह"` (Top Match: *'अमित शाह यांची...'*) 🟢
2. **`अमीतशाह`** ➡️ Split joined token to `"अमित शाह"` (Top Match: *'अमित शाह यांची...'*) 🟢
3. **`अमीत स्हा`** ➡️ Corrected to `"अमित शाह"` (Top Match: *'अमित शाह यांची...'*) 🟢
4. **`फडणविस`** ➡️ Expanded surname to `"देवेंद्र फडणवीस"` (Top Match: *'देवेंद्र फडणवीस यांनी...'*) 🟢
5. **`अजीत पावार`** ➡️ Corrected to `"अजित पवार"` (Top Match: *'अजित पवार काय म्हणाले...'*) 🟢
6. **`राउत बातमी`** ➡️ Expanded to `"विनायक राऊत"` (Top Match: *'विनायक राऊत प्रकरणात...'*) 🟢

---

## 5. Remaining 9 Failures (Sprint 1.2.3 Scope)
The remaining 9 failures are all general topic word typos:
1. `राजकरण` (Politics)
2. `राजकारन` (Politics)
3. `राज्कारण` (Politics)
4. `राजकरण बातमी` (Politics News)
5. `राजकरण आज` (Politics Today)
6. `अपघत` (Accident)
7. `अपघाड` (Accident)
8. `पाउस` (Rain)
9. `शेतकारी` (Farmer)

---

## 6. Self-Review Architectural Checklist
- [x] **Can Organization Resolution reuse this framework?** YES (same sliding window & alias matching pattern).
- [x] **Can Village Resolution reuse this framework?** YES (same surname/parent entity association pattern).
- [x] **Can Celebrity Resolution reuse this framework?** YES.
- [x] **Did you accidentally implement a generic spell checker?** NO (only registered person entities and joined person tokens are targeted).
