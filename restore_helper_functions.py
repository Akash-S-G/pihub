import json

helper_code = """
def strip_markdown_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\\n", 1)[-1]
    if text.endswith("```"):
        text = text.rsplit("\\n", 1)[0]
    return text.strip()

def extract_balanced_json_candidates(text: str) -> List[str]:
    candidates = []
    pairs = {"{": "}", "[": "]"}
    for start in range(len(text)):
        if text[start] in pairs:
            expected_stack = [pairs[text[start]]]
            for index in range(start + 1, len(text)):
                current = text[index]
                if current == '\\\\':
                    continue
                if current in pairs:
                    expected_stack.append(pairs[current])
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
        if not candidate:
            continue
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
    if schema_type == "array":
        return []
    if schema_type in ("number", "integer"):
        return 0
    if schema_type == "boolean":
        return False
    return ""

def normalize_payload_for_schema(payload: Any, schema: Dict[str, Any]) -> Dict[str, Any]:
    if isinstance(payload, list) and schema.get("type") == "object" and "items" in schema.get("properties", {}):
        payload = {"items": payload}
    if not isinstance(payload, dict):
        payload = schema_default(schema)
    properties = schema.get("properties", {})
    for key in schema.get("required", []):
        if key not in payload or payload[key] is None:
            payload[key] = schema_default(properties.get(key, {}))
    return payload
"""

with open('/home/akash/Desktop/PIHUB/02_ARTIFACT_GENERATION.ipynb', 'r') as f:
    nb = json.load(f)

for cell in nb["cells"]:
    if cell["cell_type"] == "code" and "ARTIFACT_SPECS" in "".join(cell["source"]):
        # Make sure we don't double append
        if "def normalize_payload_for_schema" not in "".join(cell["source"]):
            cell["source"].append("\n")
            cell["source"].extend([l + "\n" for l in helper_code.strip().split("\n")])
        break

with open('/home/akash/Desktop/PIHUB/02_ARTIFACT_GENERATION.ipynb', 'w') as f:
    json.dump(nb, f, indent=2)

print("Helper functions restored successfully.")
