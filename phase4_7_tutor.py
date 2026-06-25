import urllib.request
import json

def test_tutor(question, language="en", sim_ctx=None):
    payload = {
        "question": question,
        "language": language
    }
    if sim_ctx:
        payload["simulation_context"] = sim_ctx
        
    req = urllib.request.Request(
        "http://127.0.0.1:80/ai/tutor/debug",
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
            return data
    except Exception as e:
        print(f"Error for '{question}': {e}")
        return None

print("--- Phase 5: Generated Pack Retrieval ---")
q1 = test_tutor("What is photosynthesis?", "en")
if q1:
    sources = [chunk.get("metadata", {}).get("source", "") for chunk in q1.get("retrieved_chunks", [])]
    print(f"Retrieved Chunks: {len(sources)}")
    print(f"Sources: {sources}")
    has_generated = any("generated_pack" in s for s in sources)
    print(f"Contains generated_pack: {has_generated}")
    
q2 = test_tutor("What is force?", "en")
if q2:
    sources = [chunk.get("metadata", {}).get("source", "") for chunk in q2.get("retrieved_chunks", [])]
    print(f"Sources (force): {sources}")

print("\n--- Phase 6: Multilingual Preservation ---")
q_hi = test_tutor("प्रकाश संश्लेषण क्या है?", "hi")
if q_hi:
    print(f"Response (hi): {q_hi.get('answer', '')[:50]}...")

q_kn = test_tutor("ಪ್ರಕಾಶಸಂಶ್ಲೇಷಣೆ ಎಂದರೇನು?", "kn")
if q_kn:
    print(f"Response (kn): {q_kn.get('answer', '')[:50]}...")

print("\n--- Phase 7: Simulation Context ---")
sim = {"id": "pendulum", "state": {"length": 2.0, "angle": 30}}
q_sim = test_tutor("What is the length of this pendulum?", "en", sim)
if q_sim:
    print(f"Context used: {sim}")
    print(f"Simulation in Prompt Context: {'pendulum' in q_sim.get('context', '')}")
    print(f"Answer: {q_sim.get('answer', '')}")
