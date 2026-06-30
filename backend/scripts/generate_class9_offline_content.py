from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path("/home/akash/Desktop/PIHUB")
TEXT_DIR = ROOT / "TEMP" / "class9_generation"
OUTPUT_DIR = ROOT / "TEMP" / "class9_generation_outputs"


STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "have", "are", "was", "were", "will", "their",
    "there", "them", "they", "these", "those", "into", "about", "into", "chapter", "section", "activity",
    "activities", "figure", "fig", "reprint", "page", "pages", "also", "such", "which", "when", "what",
    "where", "why", "how", "does", "done", "than", "then", "can", "could", "would", "should", "shall",
    "may", "might", "must", "not", "only", "any", "all", "some", "many", "most", "more", "less", "very",
    "each", "such", "like", "your", "you", "our", "his", "her", "its", "into", "over", "under", "within",
    "between", "through", "after", "before", "while", "during", "because", "therefore", "since",
    "class", "grade", "textbook", "introduction", "overview", "reprint", "chapter", "unit", "lesson",
    "exercise", "example", "examples", "question", "questions", "answer", "answers", "students", "student",
    "teacher", "teachers", "activity", "let", "us", "think", "act", "discussion", "discussion", "observe",
    "observations", "definition", "defined", "called", "known",
}


CUES = [
    r"\bis called\b",
    r"\bare called\b",
    r"\bmeans\b",
    r"\brefers to\b",
    r"\bdefined as\b",
    r"\bdenotes\b",
    r"\bknown as\b",
    r"\bconsists of\b",
    r"\bis the\b",
    r"\bare the\b",
]


SECTION_RE = re.compile(
    r"^(?:chapter\s+\d+|unit\s+\d+|\d+(?:\.\d+)*\s+.+|[A-Z][A-Z0-9 ,:;()'’–\-]{5,}|what is .+|why .+)$",
    re.IGNORECASE,
)
FORMULA_RE = re.compile(
    r"([A-Za-z][A-Za-z0-9_ ()]{0,40}\s*(?:=|∝|≤|≥|<|>)\s*[^.;\n]{1,100}|[A-Za-z0-9]+\s*/\s*[A-Za-z0-9]+)"
)
DEFINITION_RE = re.compile(
    r"^\s*(?:the\s+)?([A-Za-z][A-Za-z0-9' -]{2,60}?)\s+(?:is|are|was|were|means|refers to|defined as|consists of|denotes|is called|are called)\b",
    re.IGNORECASE,
)
WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9']+")
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+|\n+")
GENERIC_CONCEPTS = {
    "the chapter",
    "this chapter",
    "the book",
    "the text",
    "the topic",
    "the idea",
    "in everyday life",
    "in this chapter",
}


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").replace("\u00a0", " ")).strip()


def format_title(text: str) -> str:
    text = normalize_space(text)
    if not text:
        return text
    title = text.title()
    title = title.replace("'S", "'s")
    title = title.replace(" Ii", " II").replace(" Iii", " III").replace(" Iv", " IV")
    return title


def slug_to_title(slug: str) -> str:
    parts = slug.replace("_", " ").split()
    words = []
    for part in parts:
        if part.lower() == "s":
            words[-1] = words[-1] + "'s"
            continue
        words.append(part)
    title = " ".join(words)
    title = title.replace("Ii", "II").replace("Iii", "III").replace("Iv", "IV")
    return format_title(title)


def clean_lines(text: str) -> list[str]:
    lines: list[str] = []
    for raw in text.splitlines():
        line = normalize_space(raw)
        if not line:
            continue
        if re.fullmatch(r"\d+", line):
            continue
        if line.lower() in {"reprint 2025-26", "mathematics", "science", "social science"}:
            continue
        lines.append(line)
    return lines


def extract_title(raw_lines: list[str], slug: str) -> tuple[str, int]:
    chapter_index = None
    for i, line in enumerate(raw_lines[:40]):
        if re.fullmatch(r"chapter\s+\d+", normalize_space(line), re.IGNORECASE):
            chapter_index = i
            break
    if chapter_index is None:
        return slug_to_title(slug), -1

    fragments: list[str] = []
    consumed = chapter_index
    for line in raw_lines[chapter_index + 1 : chapter_index + 10]:
        text = normalize_space(line)
        if not text:
            if fragments:
                break
            continue
        if re.match(r"^\d+(?:\.\d+)*\s+", text) or text.upper() == "OVERVIEW":
            break
        if len(text.split()) <= 7 or text.isupper() or text.endswith("?"):
            fragments.append(text)
            consumed += 1
            continue
        if fragments:
            break

    combined = format_title(normalize_space(" ".join(fragments)).strip(" :-"))
    combined = re.sub(r"\s+\?", "?", combined)
    if combined and len(combined.split()) >= 2:
        return combined, consumed
    return format_title(slug_to_title(slug)), consumed


def split_sentences(text: str) -> list[str]:
    parts = [normalize_space(part) for part in SENTENCE_RE.split(text) if normalize_space(part)]
    filtered = [p for p in parts if len(p) > 20]
    return filtered


def word_tokens(text: str) -> list[str]:
    return [m.group(0).lower() for m in WORD_RE.finditer(text)]


def strip_numbering(text: str) -> str:
    text = re.sub(r"^\d+(?:\.\d+)*\s*", "", text).strip()
    text = re.sub(r"^chapter\s+\d+\s*", "", text, flags=re.IGNORECASE)
    text = text.replace("C hapter", "Chapter")
    return format_title(text.strip(" :-"))


def looks_like_heading(line: str) -> bool:
    if len(line) > 140:
        return False
    if re.match(r"^chapter\s+\d+", line, re.IGNORECASE):
        return True
    if re.match(r"^\d+(?:\.\d+)*\s+", line):
        return True
    if line.isupper() and len(line.split()) <= 8:
        return True
    if re.match(r"^(what is|why|how|what are|why are)\b", line, re.IGNORECASE):
        return len(line.split()) <= 10 and len(line) <= 80
    if SECTION_RE.match(line):
        return len(line.split()) <= 10 and len(line) <= 80
    return False


def extract_headings(lines: list[str], start_index: int = 0, title: str | None = None) -> list[str]:
    headings: list[str] = []
    for line in lines[start_index:]:
        if looks_like_heading(line):
            cleaned = strip_numbering(line)
            if cleaned and cleaned.lower() not in {"introduction", "overview"}:
                if title and cleaned.lower() == title.lower():
                    continue
                headings.append(cleaned)
    deduped: list[str] = []
    seen = set()
    for heading in headings:
        key = heading.lower()
        if key not in seen:
            deduped.append(heading)
            seen.add(key)
    return deduped


def extract_formulae(text: str) -> list[str]:
    formulas: list[str] = []
    for match in FORMULA_RE.finditer(text):
        formula = normalize_space(match.group(0))
        if 4 <= len(formula) <= 120 and formula not in formulas:
            formulas.append(formula)
    return formulas[:10]


def extract_definition_terms(sentences: list[str]) -> list[str]:
    terms: list[str] = []
    for sentence in sentences:
        match = DEFINITION_RE.match(sentence)
        if not match:
            continue
        term = format_title(normalize_space(match.group(1)))
        term = term.strip(" ,:-")
        term_low = term.lower()
        if term_low in GENERIC_CONCEPTS:
            continue
        if len(term.split()) > 7:
            continue
        if term_low.startswith(("the chapter", "this chapter", "a chapter", "in everyday")):
            continue
        if term and term not in terms:
            terms.append(term)
    return terms


def extract_bigrams(tokens: list[str]) -> list[str]:
    pairs: Counter[tuple[str, str]] = Counter()
    for left, right in zip(tokens, tokens[1:]):
        if left in STOPWORDS or right in STOPWORDS:
            continue
        if len(left) < 3 or len(right) < 3:
            continue
        if left.isdigit() or right.isdigit():
            continue
        pairs[(left, right)] += 1
    phrases = [" ".join(pair) for pair, count in pairs.most_common() if count >= 2]
    return phrases[:20]


def sentence_score(sentence: str, keywords: list[str], concepts: list[str], formulas: list[str]) -> float:
    score = 0.0
    lowered = sentence.lower()
    for word in keywords:
        if word in lowered:
            score += 1.0
    for concept in concepts:
        if concept.lower() in lowered:
            score += 2.0
    for formula in formulas:
        if formula.lower() in lowered:
            score += 2.5
    if any(cue in lowered for cue in ("is called", "are called", "means", "defined as", "refers to", "consists of")):
        score += 1.5
    if sentence[:1].isupper():
        score += 0.25
    return score


def summarize_text(text: str, title: str, subject: str, headings: list[str], formulas: list[str]) -> tuple[str, list[str]]:
    sentences = split_sentences(text)
    tokens = [t for t in word_tokens(text) if t not in STOPWORDS]
    top_words = [word for word, _ in Counter(tokens).most_common(10)]
    keywords = top_words[:]
    concept_seed = headings[:6] + formulas[:4]
    ranked = sorted(
        ((sentence_score(sentence, keywords, concept_seed, formulas), sentence) for sentence in sentences),
        key=lambda item: item[0],
        reverse=True,
    )
    selected: list[str] = []
    for _, sentence in ranked:
        if sentence not in selected:
            selected.append(sentence)
        if len(selected) == 5:
            break
    if not selected and sentences:
        selected = sentences[:3]

    if selected:
        overview = " ".join(selected[:3])
    else:
        overview = f"This chapter focuses on {title.lower()} and the main ideas students need to understand."
    overview = normalize_space(overview)
    if len(overview) > 850:
        overview = overview[:847].rsplit(" ", 1)[0] + "..."

    key_points: list[str] = []
    for heading in headings[:5]:
        key_points.append(f"{heading} is a major part of the chapter.")
    for sentence in selected:
        if len(key_points) >= 5:
            break
        point = normalize_space(sentence)
        if point not in key_points:
            key_points.append(point[:220].rstrip())
    while len(key_points) < 5 and top_words:
        word = top_words[len(key_points) % len(top_words)]
        key_points.append(f"The chapter repeatedly uses the idea of {word}.")
    return overview, key_points[:5]


def candidate_concepts(headings: list[str], formulas: list[str], definition_terms: list[str], text: str) -> list[str]:
    candidates: list[str] = []
    for source in headings + definition_terms + formulas:
        source = strip_numbering(source)
        if not source or len(source) < 3:
            continue
        if source.lower() in {"introduction", "overview", "exercise", "examples"}:
            continue
        if source not in candidates:
            candidates.append(source)
    return candidates[:12]


def surrounding_sentence(text: str, term: str) -> str:
    sentences = split_sentences(text)
    term_low = term.lower()
    for sentence in sentences:
        if term_low in sentence.lower():
            return normalize_space(sentence)
    return ""


def shorten(text: str, limit: int = 170) -> str:
    text = normalize_space(text)
    if len(text) <= limit:
        return text
    return text[: limit - 3].rsplit(" ", 1)[0] + "..."


def concept_description(term: str, text: str, subject: str, overview: str) -> str:
    sentence = surrounding_sentence(text, term)
    if sentence and len(sentence) > 30:
        if term.lower() not in sentence.lower():
            sentence = f"{term}: {sentence}"
        return shorten(sentence, 240)
    subject_hint = {
        "mathematics": "the numerical rules, properties, and examples used to solve problems",
        "science": "the observations, processes, and laws that explain how the natural world works",
        "social": "the ideas, institutions, and real-world situations that shape society and governance",
    }.get(subject, "the main ideas in the chapter")
    return shorten(
        f"{term} is an important idea in this chapter. It helps students understand {subject_hint}.",
        240,
    )


def build_concepts(text: str, subject: str, headings: list[str], formulas: list[str], overview: str, definition_terms: list[str]) -> list[dict[str, str]]:
    concepts: list[dict[str, str]] = []
    for term in candidate_concepts(headings, formulas, definition_terms, text):
        description = concept_description(term, text, subject, overview)
        if term.lower() == "introduction":
            continue
        if all(term.lower() != existing["concept"].lower() for existing in concepts):
            concepts.append({"concept": term, "description": description})
        if len(concepts) == 5:
            break
    if len(concepts) < 5:
        topic_words = [w for w, _ in Counter(t for t in word_tokens(text) if t not in STOPWORDS).most_common(20)]
        for word in topic_words:
            pretty = word.replace("_", " ").title()
            if all(pretty.lower() != existing["concept"].lower() for existing in concepts):
                concepts.append({
                    "concept": pretty,
                    "description": shorten(
                        f"{pretty} is a recurring idea in {subject}. It appears in the chapter's explanations and examples.",
                        240,
                    ),
                })
            if len(concepts) == 5:
                break
    return concepts[:5]


def flashcard_front(term: str, subject: str) -> str:
    templates = {
        "mathematics": [
            "What does {term} mean?",
            "State the idea behind {term}.",
            "How is {term} used in this chapter?",
        ],
        "science": [
            "What is {term}?",
            "How does {term} help explain the chapter?",
            "Why is {term} important?",
        ],
        "social": [
            "What does {term} describe?",
            "Why is {term} important in this chapter?",
            "How does {term} shape the topic?",
        ],
    }
    template = templates.get(subject, templates["science"])[hash(term) % 3]
    return template.format(term=term)


def build_flashcards(concepts: list[dict[str, str]], subject: str, overview: str) -> list[dict[str, str]]:
    cards: list[dict[str, str]] = []
    for index, concept in enumerate(concepts[:5]):
        front = flashcard_front(concept["concept"], subject)
        if index == 0:
            front = f"What is the main idea of {concept['concept']}?"
        back = concept["description"]
        if index == 4:
            back = overview
        cards.append({"front": front, "back": shorten(back, 240)})
    while len(cards) < 5:
        cards.append({
            "front": "What is the key idea from this chapter?",
            "back": shorten(overview, 240),
        })
    return cards[:5]


def unique_options(options: list[str]) -> list[str]:
    deduped: list[str] = []
    seen = set()
    for option in options:
        normalized = normalize_space(option)
        if normalized and normalized not in seen:
            deduped.append(normalized)
            seen.add(normalized)
    return deduped


def build_quizzes(
    title: str,
    subject: str,
    concepts: list[dict[str, str]],
    formulas: list[str],
    overview: str,
) -> list[dict[str, str]]:
    quizzes: list[dict[str, str]] = []
    concept_names = [c["concept"] for c in concepts]
    descriptions = [shorten(c["description"], 120) for c in concepts]

    if concepts:
        correct = descriptions[0]
        options = unique_options([correct, *(descriptions[1:4]), overview[:120]])
        while len(options) < 4:
            options.append(shorten(concepts[len(options) % len(concepts)]["description"], 120))
        quizzes.append({
            "question": f"Which statement best describes {concepts[0]['concept']}?",
            "options": options[:4],
            "answer": correct,
            "explanation": concepts[0]["description"],
        })

    if len(concepts) >= 2:
        correct = concept_names[1]
        options = unique_options([correct, concept_names[0], *concept_names[2:5], title])
        while len(options) < 4:
            options.append(title)
        quizzes.append({
            "question": f"Which term from the chapter is most closely linked to {concept_names[1]}?",
            "options": options[:4],
            "answer": correct,
            "explanation": f"{concept_names[1]} is a key concept in the chapter and connects to the chapter theme of {title.lower()}.",
        })

    if formulas:
        correct = formulas[0]
        options = unique_options([correct, *(formulas[1:4]), "A descriptive paragraph", "A table of values"])
        while len(options) < 4:
            options.append(formulas[0])
        quizzes.append({
            "question": "Which formula or relationship is directly used in this chapter?",
            "options": options[:4],
            "answer": correct,
            "explanation": f"The chapter uses {correct} as one of its core relationships.",
        })
    else:
        correct = concepts[0]["concept"] if concepts else title
        other_terms = concept_names[1:5] if len(concept_names) > 1 else [title, "observation", "example"]
        options = unique_options([correct, *other_terms, "general knowledge"])
        while len(options) < 4:
            options.append(title)
        quizzes.append({
            "question": f"Which idea should a student focus on first in {title}?",
            "options": options[:4],
            "answer": correct,
            "explanation": f"Starting with {correct} gives the student the core structure of the chapter.",
        })

    if subject == "mathematics":
        answer = "It shows how the chapter's rule or theorem can be used to solve problems."
        quizzes.append({
            "question": f"What is the best use of the main idea in {title}?",
            "options": unique_options([
                answer,
                "It only helps memorize page numbers.",
                "It replaces the need for practice.",
                "It is unrelated to exercises.",
            ])[:4],
            "answer": answer,
            "explanation": answer,
        })
    elif subject == "science":
        answer = "It explains observations, causes, and effects in the natural world."
        quizzes.append({
            "question": f"Why is the chapter's idea useful in science?",
            "options": unique_options([
                answer,
                "It only lists names without explanation.",
                "It removes the need for experiments.",
                "It ignores evidence.",
            ])[:4],
            "answer": answer,
            "explanation": answer,
        })
    else:
        answer = "It helps students understand institutions, people, and decisions in real life."
        quizzes.append({
            "question": f"Why does this chapter matter in social studies?",
            "options": unique_options([
                answer,
                "It only focuses on private calculations.",
                "It avoids real-world examples.",
                "It is unrelated to citizenship.",
            ])[:4],
            "answer": answer,
            "explanation": answer,
        })

    while len(quizzes) < 5:
        quizzes.append({
            "question": f"What is one important takeaway from {title}?",
            "options": unique_options([
                overview[:120],
                "A random unrelated idea",
                "A page number",
                "A book cover image",
            ])[:4],
            "answer": overview[:120],
            "explanation": overview,
        })

    return quizzes[:5]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def chapter_slug_from_dir(chapter_dir: Path) -> str:
    return chapter_dir.name


def main() -> None:
    if not OUTPUT_DIR.exists():
        raise SystemExit(f"Missing output directory: {OUTPUT_DIR}")

    chapter_dirs = sorted([p for p in OUTPUT_DIR.iterdir() if p.is_dir()])
    if not chapter_dirs:
        raise SystemExit(f"No chapter output directories found in {OUTPUT_DIR}")

    processed = 0
    missing_sources: list[str] = []
    for chapter_dir in chapter_dirs:
        slug = chapter_slug_from_dir(chapter_dir)
        txt_path = TEXT_DIR / f"{slug}.txt"
        if not txt_path.exists():
            missing_sources.append(slug)
            continue

        raw_text = txt_path.read_text(encoding="utf-8", errors="ignore")
        raw_lines = raw_text.splitlines()
        title, title_end_index = extract_title(raw_lines, slug)
        lines = clean_lines(raw_text)
        subject = "social" if slug.startswith("social_") else "science" if slug.startswith("science_") else "mathematics"
        body_text = "\n".join(lines)
        headings = extract_headings(raw_lines, max(0, title_end_index + 1), title=title)
        sentences = split_sentences(body_text)
        formulas = extract_formulae(raw_text)
        definition_terms = extract_definition_terms(sentences)
        overview, key_points = summarize_text(body_text, title, subject, headings, formulas)
        concepts = build_concepts(body_text, subject, headings, formulas, overview, definition_terms)
        flashcards = build_flashcards(concepts, subject, overview)
        quizzes = build_quizzes(title, subject, concepts, formulas, overview)

        summary_payload = {
            "chapter_title": title,
            "overview": overview,
            "key_points": key_points,
        }
        concepts_payload = concepts
        flashcards_payload = flashcards
        quizzes_payload = quizzes

        write_json(chapter_dir / "summary.json", summary_payload)
        write_json(chapter_dir / "concepts.json", concepts_payload)
        write_json(chapter_dir / "flashcards.json", flashcards_payload)
        write_json(chapter_dir / "quizzes.json", quizzes_payload)
        processed += 1

    print(f"Generated offline content for {processed} chapter(s).")
    if missing_sources:
        print(f"Skipped {len(missing_sources)} output dir(s) without matching source text.")
        print(", ".join(sorted(missing_sources)))


if __name__ == "__main__":
    main()
