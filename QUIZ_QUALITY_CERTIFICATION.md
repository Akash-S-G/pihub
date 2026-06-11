# Quiz Quality Certification

Validation source: public gateway APIs from the running Docker deployment.

Endpoint: `GET /quizzes` sampled from certified `/packs/sync` records.

Rejected classes: ambiguous questions, missing options, missing answers, OCR-derived prompts, weak distractors, out-of-context facts.

Final evidence:

```json
{
  "quiz_quality_score": 100.0,
  "quiz_api_success_rate": 100.0,
  "failing_samples": 0
}
```

Verdict: PASS
