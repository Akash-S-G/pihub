import json
import re

def update_02():
    with open('/home/akash/Desktop/PIHUB/02_ARTIFACT_GENERATION.ipynb', 'r') as f:
        nb = json.load(f)
        
    for cell in nb['cells']:
        if cell['cell_type'] == 'code' and "all_artifacts = {}" in "".join(cell['source']):
            source = "".join(cell['source'])
            
            # Add logging init
            source = source.replace(
                "all_artifacts = {}",
                "all_artifacts = {}\nVALIDATION_REPORT = {\"total_sections\": 0, \"successful_artifacts\": {}, \"failed_artifacts\": {}, \"errors\": []}\nstart_time = time.time()"
            )
            
            # Track total sections
            source = source.replace(
                "    for section in tqdm(chapter.sections, desc=f\"Sections: {chapter.chapter_title}\", leave=False):",
                "    for section in tqdm(chapter.sections, desc=f\"Sections: {chapter.chapter_title}\", leave=False):\n        VALIDATION_REPORT[\"total_sections\"] += 1"
            )
            
            # Track success/failure
            source = source.replace(
                "                all_artifacts.setdefault(artifact_name, []).append({\"section_id\": section.section_id, \"chapter_id\": chapter.document_id, \"payload\": payload})",
                "                all_artifacts.setdefault(artifact_name, []).append({\"section_id\": section.section_id, \"chapter_id\": chapter.document_id, \"payload\": payload})\n" + 
                "                if payload.get(\"_generation_failed\"):\n" +
                "                    VALIDATION_REPORT[\"failed_artifacts\"][artifact_name] = VALIDATION_REPORT[\"failed_artifacts\"].get(artifact_name, 0) + 1\n" +
                "                    VALIDATION_REPORT[\"errors\"].append({\"section_id\": section.section_id, \"artifact\": artifact_name, \"error\": payload.get(\"_failure_reason\")})\n" +
                "                else:\n" +
                "                    VALIDATION_REPORT[\"successful_artifacts\"][artifact_name] = VALIDATION_REPORT[\"successful_artifacts\"].get(artifact_name, 0) + 1\n"
            )
            
            # Save report
            source = source.replace(
                "print(\"LLM JSON Generation complete.\")",
                "VALIDATION_REPORT[\"total_time_seconds\"] = round(time.time() - start_time, 2)\n" +
                "(PACK_ROOT / \"generation_report.json\").write_text(json.dumps(VALIDATION_REPORT, indent=2), encoding=\"utf-8\")\n" +
                "print(\"LLM JSON Generation complete. Validation report saved.\")\n" +
                "print(json.dumps(VALIDATION_REPORT, indent=2))"
            )
            
            # Convert back to list of lines
            cell['source'] = [line + '\n' for line in source.split('\n')]
            # Fix the last line which might have an extra \n
            if cell['source'] and cell['source'][-1] == '\n':
                cell['source'] = cell['source'][:-1]

    with open('/home/akash/Desktop/PIHUB/02_ARTIFACT_GENERATION.ipynb', 'w') as f:
        json.dump(nb, f, indent=2)

def update_03():
    with open('/home/akash/Desktop/PIHUB/03_VOICE_GENERATION.ipynb', 'r') as f:
        nb = json.load(f)

    for cell in nb['cells']:
        if cell['cell_type'] == 'code' and "svara_js_code" in "".join(cell['source']):
            source = "".join(cell['source'])
            
            # Add JS report init
            source = source.replace(
                "  let manifest = { chapter_id: 'unknown', summary: '', objectives: '', full_narration: '', sections: [], concepts: [], glossary: [], faqs: [], doubts: [], flashcards: [] };",
                "  let manifest = { chapter_id: 'unknown', summary: '', objectives: '', full_narration: '', sections: [], concepts: [], glossary: [], faqs: [], doubts: [], flashcards: [] };\n" +
                "  let report = { total_files: 0, errors: [], start_time: Date.now(), categories: { section_summaries: 0, concepts: 0, glossary: 0, faqs: 0, doubts: 0, flashcards: 0, full_narration: 0 } };"
            )
            
            # Update JS synthesize wrapper
            source = source.replace(
                "function cleanSlug(text) {",
                "async function synthesizeAndLog(model, tokenizer, decoder, textChunks, outputPath, category, insertPause = false) {\n" +
                "    let res = await synthesizeWav(model, tokenizer, decoder, textChunks, outputPath, insertPause);\n" +
                "    if(res) { report.total_files++; if(report.categories[category]!==undefined) report.categories[category]++; }\n" +
                "    else { report.errors.push(`Failed to synthesize ${outputPath}`); }\n" +
                "    return res;\n" +
                "  }\n\n" +
                "function cleanSlug(text) {"
            )
            
            # Replace synthesizeWav calls with synthesizeAndLog
            source = source.replace(
                "if(await synthesizeWav(model, tokenizer, decoder, chunkText(text), path.join(VOICE_DIR, p)))",
                "if(await synthesizeAndLog(model, tokenizer, decoder, chunkText(text), path.join(VOICE_DIR, p), 'section_summaries'))"
            )
            source = source.replace(
                "if(await synthesizeWav(model, tokenizer, decoder, chunkText(allSummaries.join(' ')), path.join(VOICE_DIR, p)))",
                "if(await synthesizeAndLog(model, tokenizer, decoder, chunkText(allSummaries.join(' ')), path.join(VOICE_DIR, p), 'section_summaries'))"
            )
            source = source.replace(
                "if(await synthesizeWav(model, tokenizer, decoder, chunkText(objText), path.join(VOICE_DIR, p)))",
                "if(await synthesizeAndLog(model, tokenizer, decoder, chunkText(objText), path.join(VOICE_DIR, p), 'section_summaries'))"
            )
            source = source.replace(
                "if(await synthesizeWav(model, tokenizer, decoder, chunkText(text), path.join(VOICE_DIR, p)))",
                "if(await synthesizeAndLog(model, tokenizer, decoder, chunkText(text), path.join(VOICE_DIR, p), 'concepts'))"
            )
            source = source.replace(
                "if(await synthesizeWav(model, tokenizer, decoder, chunkText(text), path.join(VOICE_DIR, p)))",
                "if(await synthesizeAndLog(model, tokenizer, decoder, chunkText(text), path.join(VOICE_DIR, p), 'glossary'))"
            )
            
            # Replace the generic synthesizeWav for others manually
            source = re.sub(
                r"if\(await synthesizeWav\(model, tokenizer, decoder, chunkText\(text\), path.join\(VOICE_DIR, p\)\)\)\s*manifest.faqs",
                "if(await synthesizeAndLog(model, tokenizer, decoder, chunkText(text), path.join(VOICE_DIR, p), 'faqs'))\n        manifest.faqs",
                source
            )
            source = re.sub(
                r"if\(await synthesizeWav\(model, tokenizer, decoder, chunkText\(text\), path.join\(VOICE_DIR, p\)\)\)\s*manifest.doubts",
                "if(await synthesizeAndLog(model, tokenizer, decoder, chunkText(text), path.join(VOICE_DIR, p), 'doubts'))\n        manifest.doubts",
                source
            )
            source = re.sub(
                r"if\(await synthesizeWav\(model, tokenizer, decoder, parts, path.join\(VOICE_DIR, p\), true\)\)\s*manifest.flashcards",
                "if(await synthesizeAndLog(model, tokenizer, decoder, parts, path.join(VOICE_DIR, p), 'flashcards', true))\n        manifest.flashcards",
                source
            )
            source = re.sub(
                r"if\(await synthesizeWav\(model, tokenizer, decoder, chunkText\(fullText, 30\), path.join\(VOICE_DIR, p\)\)\)\s*manifest.full_narration",
                "if(await synthesizeAndLog(model, tokenizer, decoder, chunkText(fullText, 30), path.join(VOICE_DIR, p), 'full_narration'))\n         manifest.full_narration",
                source
            )
            
            # Replace remaining generic concepts/glossary replacements that might have been overwritten
            # Actuall the first batch of replace() hits the first match. Let's do it safer.
            
            # Wait, `replace` replaces ALL occurrences.
            # But the ones above (faqs, doubts) were using `chunkText(text)` which were already replaced by the generic `section_summaries` replace!
            
            pass # We will rewrite this carefully.

