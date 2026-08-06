# 🛡️ Sprint 2.1: Intent Validation Layer (Quality Gate) Engineering Report

**Module**: Intent Validation Layer (`src/intent_validator.py`)  
**Role**: Principal RAG Architect, Senior Search Engineer & NLP Architect  
**Status**: 🟢 **IMPLEMENTED, TESTED & INTEGRATED**  

---

## 1. 🎯 Purpose & Scope

The **Intent Validation Layer** (`src/intent_validator.py`) functions as the final **Quality Gate** between Context Engineering (`context_builder.py`) and Answer Generation (`gemini_service.py`).

### Strict Single Responsibility Principle (SRP)
- **Included**: Evaluates how well the extracted context snippets in `ContextPackage` satisfy the target intent of `QueryInfo`.
- **Excluded**: NO database queries, NO query rewriting, NO article text modification, NO LLM or Gemini API calls.

---

## 2. 🏛️ Pipeline Architecture

```
User Query ➔ QueryProcessor ➔ Retriever ➔ ContextBuilder ➔ IntentValidator 🛡️ ➔ Gemini ➔ Answer
```

The validator assesses the **actual context** (`ContextPackage`) right before Gemini receives it.

---

## 3. ⚙️ Scoring & Evaluation Methodology

### Component Weights (Summing to 100.0)
- `WEIGHT_DISTRICT`: **25.0%**
- `WEIGHT_PERSON`: **25.0%**
- `WEIGHT_CATEGORY`: **30.0%**
- `WEIGHT_DATE`: **20.0%**

*(Note: If a query does not specify a particular entity/date, its weight is dynamically redistributed across requested criteria).*

### Retrieval Status & Confidence Thresholds

| Retrieval Status | Score Threshold | Definition |
| :--- | :--- | :--- |
| **`EXACT_MATCH`** | Score ≥ 90.0% | All query-specified entities and topics found in context snippets. |
| **`PARTIAL_MATCH`** | 60.0% ≤ Score < 90.0% | Major entities found; one important element missing. |
| **`RELATED_MATCH`** | 30.0% ≤ Score < 60.0% | General location/category found; specific intent missing. |
| **`NO_MATCH`** | Score < 30.0% | No meaningful relationship between query intent and context. |

---

## 4. 📊 Example Validations

### 🔴 Example A: Conflict Detection
- **Query**: `"विनायक राऊत सिंधुदुर्ग पाऊस"`
- **Extracted Context**: Vinayak Raut news in Sindhudurg (Topic: Politics / `राजकीय भूकंप`).
- **Validation Result**:
  - `retrieval_status`: **`PARTIAL_MATCH` / `RELATED_MATCH`**
  - `confidence`: **`MEDIUM`**
  - `validation_reason`: *"Matched entities: District: Sindhudurg, Person: विनायक राऊत. Missing topics: पाऊस, Category: Weather."*

### 🟢 Example B: Exact Match
- **Query**: `"अमित शाह पुणे"`
- **Extracted Context**: Amit Shah's visit to Pune.
- **Validation Result**:
  - `retrieval_status`: **`EXACT_MATCH`**
  - `confidence`: **`HIGH`**
  - `overall_match_score`: **`100.0%`**
  - `validation_reason`: *"Matched entities: District: Pune, Person: अमित शाह."*

---

## 5. 🛡️ Architectural Verification Checklist
- [x] **Does Intent Validator have a single responsibility?** YES (Evaluates context quality vs intent).
- [x] **Can Retriever be replaced without changing Validator?** YES.
- [x] **Can Gemini be replaced without changing Validator?** YES.
- [x] **Is the evaluation 100% deterministic?** YES.
- [x] **Does it explain WHY retrieval quality is low?** YES (`validation_reason` string).
