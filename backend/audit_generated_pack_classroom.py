import json
import time
from urllib import request

def audit():
    print("1. Triggering Generated Pack Importer via Pack-Service...")
    data = json.dumps({"source_dir": "/shared/generated_pack"}).encode("utf-8")
    req = request.Request("http://pack-service:8030/packs/import/generated", data=data, headers={"Content-Type": "application/json"})
    
    try:
        response = request.urlopen(req, timeout=300)
        result = json.loads(response.read())
        print("Import successful:")
        print(json.dumps(result, indent=2))
        pack_id = result.get("pack", {}).get("pack_id")
    except Exception as e:
        print(f"Import failed: {e}")
        return

    print("\n2. Verifying Pack Manifest is available to PiHub Sync...")
    try:
        req_sync = request.Request("http://pack-service:8030/sync/manifest", method="POST")
        res_sync = request.urlopen(req_sync)
        sync_data = json.loads(res_sync.read())
        found = False
        for p in sync_data.get("packs", []):
            if p.get("pack_id") == pack_id:
                found = True
                print(f"Pack {pack_id} found in sync manifest!")
                break
        if not found:
            print("ERROR: Pack not found in sync manifest.")
    except Exception as e:
        print(f"Sync manifest check failed: {e}")

    time.sleep(2)

    print("\n3. Testing Tutor Retrieval (POST /ai/tutor/debug)...")
    try:
        tutor_data = json.dumps({"question": "What is photosynthesis?", "grade": 10, "subject": "science"}).encode("utf-8")
        req_tutor = request.Request("http://inference-service:8010/ai/tutor/debug", data=tutor_data, headers={"Content-Type": "application/json"})
        res_tutor = request.urlopen(req_tutor)
        tutor_result = json.loads(res_tutor.read())
        
        chunks = tutor_result.get("retrieved_chunks", [])
        if not chunks:
            chunks = tutor_result.get("curriculum", {}).get("results", [])
            
        print(f"Retrieved {len(chunks)} chunks.")
        found_generated = False
        for i, chunk in enumerate(chunks):
            print(f"\nChunk {i+1}:")
            text = chunk.get("text", "")
            print(f"Text: {text[:100]}...")
            print(f"Metadata: {chunk.get('metadata')}")
            if chunk.get("metadata", {}).get("source") == "generated_pack":
                found_generated = True
                print("SUCCESS: Found chunk from generated_pack!")
        if not found_generated:
            print("ERROR: No chunks from generated_pack were retrieved.")
    except Exception as e:
        print(f"Tutor retrieval failed: {e}")

if __name__ == "__main__":
    audit()
