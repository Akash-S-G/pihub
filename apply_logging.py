import json

# ========================
# UPDATE NOTEBOOK 02
# ========================
with open('/home/akash/Desktop/PIHUB/02_ARTIFACT_GENERATION.ipynb', 'r') as f:
    nb02 = json.load(f)

for cell in nb02["cells"]:
    if cell["cell_type"] == "code":
        src = "".join(cell["source"])
        
        # 1. Update Model to Llama 3.1
        if 'CONFIG = {' in src and '"content_model_repo"' in src:
            new_source = []
            for line in cell["source"]:
                if '"content_model_repo"' in line:
                    new_source.append('    "content_model_repo": "bartowski/Meta-Llama-3.1-8B-Instruct-GGUF",\n')
                elif '"content_model_file"' in line:
                    new_source.append('    "content_model_file": "Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf",\n')
                else:
                    new_source.append(line)
            cell["source"] = new_source

        # 2. Add Logger Config to the Setup Block
        if 'OUTPUT_ROOT = Path(CONFIG["output_root"])' in src:
            new_source = []
            for line in cell["source"]:
                new_source.append(line)
                if 'PACK_ROOT = OUTPUT_ROOT / "generated_pack"' in line:
                    new_source.extend([
                        "\n",
                        "# Logging Configuration\n",
                        "LOG_FILE = OUTPUT_ROOT / \"generation_progress.log\"\n",
                        "logging.basicConfig(\n",
                        "    level=logging.INFO,\n",
                        "    format='%(asctime)s [%(levelname)s] %(message)s',\n",
                        "    handlers=[\n",
                        "        logging.FileHandler(LOG_FILE),\n",
                        "        logging.StreamHandler(sys.stdout)\n",
                        "    ]\n",
                        ")\n",
                        "logger = logging.getLogger(\"ArtifactGen\")\n"
                    ])
            cell["source"] = new_source

        # 3. Add Logging to Generation Logic
        if 'def generate_json' in src:
            # We want to replace the silent loop with logged loop
            # and generate_json with logged generation
            new_code = """
def enriched_section_text(section: SectionData) -> str:
    parts = [f"Section Title: {section.title}", section.content]
    if section.equations:
        parts.append("Equations:\\n" + "\\n".join(section.equations[:20]))
    if section.tables:
        table_lines = [json.dumps(t, ensure_ascii=False)[:2500] for t in section.tables[:5]]
        parts.append("Tables:\\n" + "\\n".join(table_lines))
    captions = [f"{fig.figure_id}: {fig.caption} (Image Path: {fig.image_path})" for fig in section.figures]
    if captions:
        parts.append("Figure references:\\n" + "\\n".join(captions[:20]))
    return "\\n\\n".join(part for part in parts if part).strip()

def prompt_for_artifact(section: SectionData, artifact_name: str, spec: Dict[str, Any], num_sections: int) -> str:
    source_text = enriched_section_text(section)[:12000]
    target_val = spec['target_calc'](num_sections)
    target_instruction = spec['target_msg'].replace("{T}", str(target_val))
    schema = spec['schema']
    
    return f\"\"\"\\
You are generating curriculum artifacts for offline school tutoring.
Use only the Docling-extracted source section, including tables, equations, and figure captions.
Do not invent facts.

CRITICAL INSTRUCTIONS:
- {target_instruction}
- Return exactly ONE valid JSON object.
- The first character must be {{ and the last character must be }}.
- Do not use markdown fences. Do not include explanations before or after JSON.
- Ensure the JSON strictly matches the Required JSON Schema.

Artifact: {artifact_name}
Required JSON Schema: {json.dumps(schema, ensure_ascii=False)}

Source:
{source_text}
\"\"\"

def generate_json(section: SectionData, artifact_name: str, spec: dict, num_sections: int) -> Dict[str, Any]:
    digest = hashlib.sha256((section.section_id + artifact_name + section.content).encode("utf-8")).hexdigest()
    cpath = CACHE_ROOT / f"{digest}.json"
    
    if CONFIG["resume"] and cpath.exists():
        logger.info(f"[{section.section_id}] Cache HIT for '{artifact_name}'. Skipping generation.")
        return json.loads(cpath.read_text(encoding="utf-8"))

    schema = spec['schema']
    base_prompt = prompt_for_artifact(section, artifact_name, spec, num_sections)
    last_error = ""
    max_retries = max(1, int(CONFIG["max_retries"]))
    
    for retry in range(max_retries):
        logger.info(f"[{section.section_id}] Generating '{artifact_name}' (Attempt {retry + 1}/{max_retries})...")
        prompt = base_prompt if retry == 0 else base_prompt + f"\\n\\nYour previous response was invalid because: {last_error}\\nReturn corrected JSON only."
        start_t = time.time()
        result = CONTENT_LLM(prompt, max_tokens=CONFIG["max_tokens"], temperature=CONFIG["temperature"], top_p=CONFIG["top_p"])
        raw = result["choices"][0]["text"]
        tokens = result["usage"]["completion_tokens"]
        try:
            parsed = normalize_payload_for_schema(extract_json_object(raw), schema)
            jsonschema_validate(parsed, schema)
            cpath.write_text(json.dumps(parsed, indent=2, ensure_ascii=False), encoding="utf-8")
            logger.info(f"[{section.section_id}] SUCCESS '{artifact_name}' in {time.time()-start_t:.1f}s ({tokens} tokens).")
            return parsed
        except Exception as exc:
            last_error = str(exc)
            logger.warning(f"[{section.section_id}] FAILED '{artifact_name}' (Attempt {retry + 1}): {last_error}")
    
    logger.error(f"[{section.section_id}] GIVEN UP on '{artifact_name}' after {max_retries} attempts.")
    payload = normalize_payload_for_schema(schema_default(schema), schema)
    payload["_generation_failed"] = True
    payload["_failure_reason"] = last_error
    cpath.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload

all_artifacts = {}
VALIDATION_REPORT = {"total_sections": 0, "successful_artifacts": {}, "failed_artifacts": {}, "errors": []}
start_time = time.time()

logger.info(f"Starting Generation Pipeline for {len(CHAPTERS)} chapters...")

for chapter in tqdm(CHAPTERS, desc="Chapters"):
    num_sections = max(1, len(chapter.sections))
    for section in tqdm(chapter.sections, desc=f"Sections: {chapter.chapter_title}", leave=False):
        VALIDATION_REPORT["total_sections"] += 1
        for artifact_name, spec in ARTIFACT_SPECS.items():
            if CONFIG.get(spec["enabled"], False):
                payload = generate_json(section, artifact_name, spec, num_sections)
                all_artifacts.setdefault(artifact_name, []).append({"section_id": section.section_id, "chapter_id": chapter.document_id, "payload": payload})
                if payload.get("_generation_failed"):
                    VALIDATION_REPORT["failed_artifacts"][artifact_name] = VALIDATION_REPORT["failed_artifacts"].get(artifact_name, 0) + 1
                    VALIDATION_REPORT["errors"].append({"section_id": section.section_id, "artifact": artifact_name, "error": payload.get("_failure_reason")})
                else:
                    VALIDATION_REPORT["successful_artifacts"][artifact_name] = VALIDATION_REPORT["successful_artifacts"].get(artifact_name, 0) + 1

logger.info("Saving manifest files to disk...")
for artifact_name, spec in ARTIFACT_SPECS.items():
    if CONFIG.get(spec["enabled"], False):
        output_file = PACK_ROOT / spec["file"]
        output_file.write_text(json.dumps(all_artifacts.get(artifact_name, []), indent=2, ensure_ascii=False), encoding="utf-8")

VALIDATION_REPORT["total_time_seconds"] = round(time.time() - start_time, 2)
(PACK_ROOT / "generation_report.json").write_text(json.dumps(VALIDATION_REPORT, indent=2), encoding="utf-8")
logger.info(f"LLM JSON Generation complete in {VALIDATION_REPORT['total_time_seconds']}s. Validation report saved.")
print("Process completed successfully.")
"""
            cell["source"] = [l + "\n" for l in new_code.strip().split("\n")]

with open('/home/akash/Desktop/PIHUB/02_ARTIFACT_GENERATION.ipynb', 'w') as f:
    json.dump(nb02, f, indent=2)

# ========================
# UPDATE NOTEBOOK 03
# ========================
with open('/home/akash/Desktop/PIHUB/03_VOICE_GENERATION.ipynb', 'r') as f:
    nb03 = json.load(f)

for cell in nb03["cells"]:
    if cell["cell_type"] == "code":
        src = "".join(cell["source"])
        if 'def synthesize_wav' in src:
            # We want to replace the synthesis function to add detailed prints
            new_code = """
print("Loading models...")
start_load = time.time()
llm = Llama(model_path=MODEL_PATH, n_ctx=4096, n_threads=8, n_gpu_layers=0, logits_all=False, verbose=False)
decoder = ort.InferenceSession(SNAC_DECODER, providers=["CPUExecutionProvider"])
print(f"Models loaded in {time.time() - start_load:.1f}s")

def synthesize_wav(text_chunks, output_path, category, insert_pause=False):
    if output_path.exists(): 
        print(f"  [CACHE HIT] {output_path.name}")
        return str(output_path.relative_to(VOICE_ROOT))
    
    print(f"\\nSynthesizing [{category}]: {output_path.name} ({len(text_chunks)} chunks)")
    synth_start = time.time()
    combined_samples = []
    for i, chunk in enumerate(text_chunks):
        if not chunk: continue
        try:
            chunk_start = time.time()
            body = llm.tokenize(f"English (Indian) (Female): {chunk}".encode("utf-8"), add_bos=False, special=True)
            ids = [128259, llm.token_bos()] + list(body) + [128009, 128260]
            
            generated = []
            for token in llm.generate(ids, temp=0.6, top_k=40, top_p=0.9, repeat_penalty=1.0, reset=True):
                generated.append(int(token))
                if int(token) == 128258 or len(generated) >= 200: break
                    
            codes = snac_codes(ids + generated, len(ids))
            audio = decode_snac(decoder, codes)
            if len(audio) > 0: 
                combined_samples.append(audio)
            
            pause_msg = ""
            if insert_pause and i < len(text_chunks) - 1:
                combined_samples.append(np.zeros(PAUSE_SAMPLES, dtype=np.float32))
                pause_msg = " [+1.5s pause]"
                
            print(f"  -> Chunk {i+1}/{len(text_chunks)} ({len(audio)} samples) in {time.time() - chunk_start:.1f}s{pause_msg}")
            
        except Exception as e:
            err_msg = f"Error chunk '{chunk[:30]}...': {e}"
            print(f"  -> [FAILED] {err_msg}")
            report["errors"].append(err_msg)
            
    if combined_samples:
        final_audio = np.concatenate(combined_samples)
        sf.write(output_path, final_audio, SAMPLE_RATE)
        report["total_files"] += 1
        report["categories"][category] = report["categories"].get(category, 0) + 1
        print(f"  [SUCCESS] Saved {len(final_audio)} total samples in {time.time() - synth_start:.1f}s")
        return str(output_path.relative_to(VOICE_ROOT))
    
    print(f"  [FATAL] Failed to generate {output_path.name}")
    report["errors"].append(f"Failed to generate: {output_path.name}")
    return None

def clean_slug(text):
    return re.sub(r'[^a-z0-9]+', '_', str(text).lower()).strip('_')[:50]

def read_json(fname):
    p = PACK_ROOT / fname
    return json.loads(p.read_text("utf-8")) if p.exists() else []

# 1. SECTION SUMMARIES
all_summaries = []
for s in read_json("summary.json"):
    if s.get("chapter_id"): manifest["chapter_id"] = s["chapter_id"]
    txt = s.get("payload", {}).get("summary_short", "")
    if txt:
        all_summaries.append(txt)
        p = synthesize_wav(chunk_text(txt), VOICE_ROOT / "section_summaries" / f"{s.get('section_id')}.wav", "section_summaries")
        if p: manifest["sections"].append(p)

if all_summaries:
    p = synthesize_wav(chunk_text(" ".join(all_summaries)), VOICE_ROOT / "chapter_summary.wav", "section_summaries")
    if p: manifest["summary"] = p

# 2. OBJECTIVES
obj_texts = []
for o in read_json("learning_objectives.json"):
    for i in o.get("payload", {}).get("learning_objectives", []):
        obj_texts.append(i.get("objective", ""))
if obj_texts:
    p = synthesize_wav(chunk_text(" ".join(obj_texts)), VOICE_ROOT / "learning_objectives.wav", "section_summaries")
    if p: manifest["objectives"] = p

# 3. CONCEPTS
for s in read_json("concepts.json"):
    for c in s.get("payload", {}).get("concepts", []):
        if c.get("name"):
            p = synthesize_wav(chunk_text(c["name"]), VOICE_ROOT / "concepts" / f"{clean_slug(c['name'])}.wav", "concepts")
            if p: manifest["concepts"].append(p)

# 4. GLOSSARY
for s in read_json("glossary.json"):
    for g in s.get("payload", {}).get("glossary", []):
        if g.get("term"):
            txt = f"{g['term']}. {g.get('definition', '')}"
            p = synthesize_wav(chunk_text(txt), VOICE_ROOT / "glossary" / f"{clean_slug(g['term'])}.wav", "glossary")
            if p: manifest["glossary"].append(p)

# 5. FAQS
idx = 1
for s in read_json("faqs.json"):
    for f in s.get("payload", {}).get("items", []):
        txt = f"{f.get('question', '')} {f.get('answer', '')}"
        p = synthesize_wav(chunk_text(txt), VOICE_ROOT / "faqs" / f"faq_{idx:03d}.wav", "faqs")
        if p: manifest["faqs"].append(p)
        idx += 1

# 6. DOUBTS
idx = 1
for s in read_json("common_doubts.json"):
    for d in s.get("payload", {}).get("items", []):
        txt = f"{d.get('doubt', '')} {d.get('explanation', '')}"
        p = synthesize_wav(chunk_text(txt), VOICE_ROOT / "doubts" / f"doubt_{idx:03d}.wav", "doubts")
        if p: manifest["doubts"].append(p)
        idx += 1

# 7. FLASHCARDS
idx = 1
for s in read_json("flashcards.json"):
    for f in s.get("payload", {}).get("items", []):
        if f.get("front") and f.get("back"):
            parts = chunk_text(f["front"]) + chunk_text(f["back"])
            p = synthesize_wav(parts, VOICE_ROOT / "flashcards" / f"flashcard_{idx:03d}.wav", "flashcards", insert_pause=True)
            if p: manifest["flashcards"].append(p)
            idx += 1

# 8. FULL NARRATION
full_text = ""
for p in STRUCTURED_ROOT.rglob("structured_chapter.json"):
    try:
        j = json.loads(p.read_text("utf-8"))
        for sec in j.get("sections", []):
            full_text += sec.get("content", "") + ". "
    except: pass
if full_text.strip():
    p = synthesize_wav(chunk_text(full_text, 30), VOICE_ROOT / "full_chapter.wav", "full_narration")
    if p: manifest["full_narration"] = p

# Wrap up
(VOICE_ROOT / "voice_manifest.json").write_text(json.dumps(manifest, indent=2))
report["total_time_seconds"] = round(time.time() - report["start_time"])
(VOICE_ROOT / "voice_generation_report.json").write_text(json.dumps(report, indent=2))
print("\\n\\n==============================")
print(f"Voice generation complete in {report['total_time_seconds']}s")
print(f"Total files generated: {report['total_files']}")
print(f"Errors encountered: {len(report['errors'])}")
print("==============================")
"""
            # We want to replace from 'print("Loading models...")' onwards
            idx = src.find('print("Loading models...")')
            if idx == -1:
                # Fallback if I slightly changed the string earlier
                idx = src.find('llm = Llama(')
            
            prefix = src[:idx]
            cell["source"] = [l + "\n" for l in prefix.split("\n")]
            cell["source"].pop() # drop last empty line
            cell["source"].extend([l + "\n" for l in new_code.strip().split("\n")])

with open('/home/akash/Desktop/PIHUB/03_VOICE_GENERATION.ipynb', 'w') as f:
    json.dump(nb03, f, indent=2)

print("Logging added to both notebooks successfully.")
