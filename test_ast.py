ARTIFACT_SPECS: Dict[str, Dict[str, Any]] = {
    "concepts": {"enabled": "generate_concepts", "file": "concepts.json", "target_msg": "Generate exactly 20 concepts from this chapter.", "schema": {"type": "object", "required": ["concepts"], "properties": {"concepts": {"type": "array", "items": {"type": "object", "required": ["id", "name", "definition", "importance", "keywords"], "properties": {"id": {"type": "string"}, "name": {"type": "string"}, "definition": {"type": "string"}, "importance": {"type": "string", "enum": ["high", "medium", "low"]}, "keywords": {"type": "array", "items": {"type": "string"}}}}}}}},
    "learning_objectives": {"enabled": "generate_learning_objectives", "file": "learning_objectives.json", "target_msg": "Generate exactly 8 learning objectives using Bloom's Taxonomy.", "schema": {"type": "object", "required": ["learning_objectives"], "properties": {"learning_objectives": {"type": "array", "items": {"type": "object", "required": ["id", "objective", "blooms_level", "difficulty"], "properties": {"id": {"type": "string"}, "objective": {"type": "string"}, "blooms_level": {"type": "string"}, "difficulty": {"type": "string"}}}}}}}},
    "glossary": {"enabled": "generate_glossary", "file": "glossary.json", "target_msg": "Generate exactly 35 glossary terms with definition and example.", "schema": {"type": "object", "required": ["glossary"], "properties": {"glossary": {"type": "array", "items": {"type": "object", "required": ["term", "definition", "example"], "properties": {"term": {"type": "string"}, "definition": {"type": "string"}, "example": {"type": "string"}}}}}}}},
    "summary": {"enabled": "generate_summary", "file": "summary.json", "target_msg": "Generate exactly 1 short summary (150-300 words) and 1 detailed summary (600-1200 words) for this entire chapter.", "schema": {"type": "object", "required": ["summary_short", "summary_detailed"], "properties": {"summary_short": {"type": "string"}, "summary_detailed": {"type": "string"}}}},
    "detailed_explanation": {"enabled": "generate_detailed_explanation", "file": "detailed_explanation.json", "target_msg": "Generate exactly 1 detailed explanation (500-1500 words) summarizing the core mechanisms of the chapter.", "schema": {"type": "object", "required": ["explanation"], "properties": {"explanation": {"type": "string"}}}},
    "misconceptions": {"enabled": "generate_misconceptions", "file": "misconceptions.json", "target_msg": "Generate exactly 15 common misconceptions based on the chapter.", "schema": {"type": "object", "required": ["items"], "properties": {"items": {"type": "array", "items": {"type": "object", "required": ["misconception", "correction", "psychological_reason"], "properties": {"misconception": {"type": "string"}, "correction": {"type": "string"}, "psychological_reason": {"type": "string"}}}}}}}},
    "mcq_quiz": {"enabled": "generate_mcq_quiz", "file": "mcq_quiz.json", "target_msg": "Generate exactly 25 MCQs from the chapter.", "schema": {"type": "object", "required": ["items"], "properties": {"items": {"type": "array", "items": {"type": "object", "required": ["question", "options", "correct_answer", "explanation", "difficulty"], "properties": {"question": {"type": "string"}, "options": {"type": "array", "items": {"type": "string"}}, "correct_answer": {"type": "string"}, "explanation": {"type": "string"}, "difficulty": {"type": "string"}}}}}}}},
    "short_answer_questions": {"enabled": "generate_short_answer", "file": "short_answer_questions.json", "target_msg": "Generate exactly 15 short answer questions.", "schema": {"type": "object", "required": ["items"], "properties": {"items": {"type": "array", "items": {"type": "object", "required": ["question", "sample_answer", "marks"], "properties": {"question": {"type": "string"}, "sample_answer": {"type": "string"}, "marks": {"type": "integer"}}}}}}}},
    "flashcards": {"enabled": "generate_flashcards", "file": "flashcards.json", "target_msg": "Generate exactly 25 flashcards.", "schema": {"type": "object", "required": ["items"], "properties": {"items": {"type": "array", "items": {"type": "object", "required": ["front", "back", "difficulty"], "properties": {"front": {"type": "string"}, "back": {"type": "string"}, "difficulty": {"type": "string"}}}}}}}},
    "concept_relationships": {"enabled": "generate_concept_relationships", "file": "concept_relationships.json", "target_msg": "Generate exactly 30 concept relationships.", "schema": {"type": "object", "required": ["items"], "properties": {"items": {"type": "array", "items": {"type": "object", "required": ["source", "target", "relationship"], "properties": {"source": {"type": "string"}, "target": {"type": "string"}, "relationship": {"type": "string"}}}}}}}},
    "image_captions": {"enabled": "generate_image_captions", "file": "image_captions.json", "target_msg": "Generate captions for all prominent figures mentioned.", "schema": {"type": "object", "required": ["items"], "properties": {"items": {"type": "array", "items": {"type": "object", "required": ["figure_id", "caption", "educational_explanation"], "properties": {"figure_id": {"type": "string"}, "caption": {"type": "string"}, "educational_explanation": {"type": "string"}}}}}}}},
    "investigations": {"enabled": "generate_investigations", "file": "investigations.json", "target_msg": "Generate exactly 8 practical investigations or labs.", "schema": {"type": "object", "required": ["items"], "properties": {"items": {"type": "array", "items": {"type": "object", "required": ["title", "objective", "materials", "procedure", "observations", "conclusion"], "properties": {"title": {"type": "string"}, "objective": {"type": "string"}, "materials": {"type": "array", "items": {"type": "string"}}, "procedure": {"type": "array", "items": {"type": "string"}}, "observations": {"type": "array", "items": {"type": "string"}}, "conclusion": {"type": "string"}}}}}}}},
    "teacher_notes": {"enabled": "generate_teacher_notes", "file": "teacher_notes.json", "target_msg": "Generate exactly 1 set of teacher notes for the chapter.", "schema": {"type": "object", "required": ["teaching_tips", "common_errors", "discussion_questions"], "properties": {"teaching_tips": {"type": "array", "items": {"type": "string"}}, "common_errors": {"type": "array", "items": {"type": "string"}}, "discussion_questions": {"type": "array", "items": {"type": "string"}}}}}},
    "prerequisites": {"enabled": "generate_prerequisites", "file": "prerequisites.json", "target_msg": "Generate exactly 10 prerequisites.", "schema": {"type": "object", "required": ["items"], "properties": {"items": {"type": "array", "items": {"type": "object", "required": ["concept", "required_before", "reason"], "properties": {"concept": {"type": "string"}, "required_before": {"type": "boolean"}, "reason": {"type": "string"}}}}}}}},
    "difficulty_analysis": {"enabled": "generate_difficulty_analysis", "file": "difficulty_analysis.json", "target_msg": "Generate exactly 1 difficulty analysis profile.", "schema": {"type": "object", "required": ["easy_concepts", "medium_concepts", "hard_concepts", "estimated_learning_time_minutes"], "properties": {"easy_concepts": {"type": "array", "items": {"type": "string"}}, "medium_concepts": {"type": "array", "items": {"type": "string"}}, "hard_concepts": {"type": "array", "items": {"type": "string"}}, "estimated_learning_time_minutes": {"type": "integer"}}}},
    "faqs": {"enabled": "generate_faqs", "file": "faqs.json", "target_msg": "Generate exactly 15 FAQs.", "schema": {"type": "object", "required": ["items"], "properties": {"items": {"type": "array", "items": {"type": "object", "required": ["question", "answer"], "properties": {"question": {"type": "string"}, "answer": {"type": "string"}}}}}}}},
    "common_doubts": {"enabled": "generate_common_doubts", "file": "common_doubts.json", "target_msg": "Generate exactly 15 common doubts with follow-up questions.", "schema": {"type": "object", "required": ["items"], "properties": {"items": {"type": "array", "items": {"type": "object", "required": ["doubt", "explanation", "follow_up_questions"], "properties": {"doubt": {"type": "string"}, "explanation": {"type": "string"}, "follow_up_questions": {"type": "array", "items": {"type": "string"}}}}}}}},
    "exam_questions": {"enabled": "generate_exam_questions", "file": "exam_questions.json", "target_msg": "Generate exactly 20 exam questions.", "schema": {"type": "object", "required": ["items"], "properties": {"items": {"type": "array", "items": {"type": "object", "required": ["question", "type", "answer", "marks"], "properties": {"question": {"type": "string"}, "type": {"type": "string", "enum": ["MCQ", "Short Answer", "Long Answer", "HOTS/Application"]}, "answer": {"type": "string"}, "marks": {"type": "integer"}}}}}}}}
}

from typing import Any, List, Dict

def strip_markdown_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"): text = text.split("\n", 1)[-1]
    if text.endswith("```"): text = text.rsplit("\n", 1)[0]
    return text.strip()

def extract_balanced_json_candidates(text: str) -> List[str]:
    candidates = []
    pairs = {"{": "}", "[": "]"}
    for start in range(len(text)):
        if text[start] in pairs:
            expected_stack = [pairs[text[start]]]
            for index in range(start + 1, len(text)):
                current = text[index]
                if current == '\\': continue
                if current in pairs: expected_stack.append(pairs[current])
                elif expected_stack and current == expected_stack[-1]:
                    expected_stack.pop()
                    if not expected_stack:
                        candidates.append(text[start : index + 1])
                        break
    return candidates

def extract_json_object(text: str) -> Any:
    text = strip_markdown_fences(text)
    decoder = json.JSONDecoder()
    for candidate in [text, *extract_balanced_json_candidates(text)]:
        candidate = candidate.strip()
        if not candidate: continue
        try:
            parsed, _ = decoder.raw_decode(candidate)
            return parsed
        except json.JSONDecodeError:
            pass
    return {}

def schema_default(schema: Dict[str, Any]) -> Any:
    schema_type = schema.get("type", "string")
    if schema_type == "object":
        result = {}
        properties = schema.get("properties", {})
        for key in schema.get("required", []):
            result[key] = schema_default(properties.get(key, {}))
        return result
    if schema_type == "array": return []
    if schema_type in ("number", "integer"): return 0
    if schema_type == "boolean": return False
    return ""

def normalize_payload_for_schema(payload: Any, schema: Dict[str, Any]) -> Dict[str, Any]:
    if isinstance(payload, list) and schema.get("type") == "object" and "items" in schema.get("properties", {}):
        payload = {"items": payload}
    if not isinstance(payload, dict): payload = schema_default(schema)
    properties = schema.get("properties", {})
    for key in schema.get("required", []):
        if key not in payload or payload[key] is None:
            payload[key] = schema_default(properties.get(key, {}))
    return payload
