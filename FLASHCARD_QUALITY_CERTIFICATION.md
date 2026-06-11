# Flashcard Quality Certification

Validation source: public gateway APIs from the running Docker deployment.

Endpoint: `GET /flashcards` sampled from certified `/packs/sync` records.

Rejected classes: OCR fragments, trivial fronts, duplicate cards, navigation/metadata text, table artifacts, non-concepts.

Final evidence:

```json
{
  "flashcard_quality_score": 100.0,
  "flashcard_api_success_rate": 100.0,
  "failing_samples": 0
}
```

Verdict: PASS
