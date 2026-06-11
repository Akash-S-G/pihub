import json
import subprocess
import time

def main():
    report_path = '/home/akash/Desktop/PIHUB/backend/pack_validation_report.json'
    with open(report_path, 'r') as f:
        data = json.load(f)

    packs_to_regenerate = []
    for pack_id, pack_info in data.items():
        if pack_info.get("valid"):
            continue
        errors = pack_info.get("errors", [])
        if any("duplicate-term" in err or "term-missing" in err for err in errors):
            packs_to_regenerate.append((pack_id, pack_info))

    print(f"Found {len(packs_to_regenerate)} packs to regenerate.")

    for i, (pack_id, pack_info) in enumerate(packs_to_regenerate):
        try:
            # We must fetch the manifest using docker exec curl to extract the correct curriculum details
            curl_cmd = [
                "docker", "exec", "pihub-pack-service", "curl", "-s",
                f"http://localhost:8030/packs/{pack_id}/manifest"
            ]
            result = subprocess.run(curl_cmd, capture_output=True, text=True)
            if result.returncode != 0 or "generation_metadata" not in result.stdout:
                print(f"Failed to fetch manifest for {pack_id}")
                continue
            
            manifest = json.loads(result.stdout)
            gen_meta = manifest.get("generation_metadata", {})
            
            payload = {
                "pack_type": gen_meta.get("pack_type", "chapter"),
                "grade": gen_meta.get("grade"),
                "subject": gen_meta.get("subject"),
                "chapter": gen_meta.get("chapter"),
                "language": gen_meta.get("language", "english")
            }
            
            # Post generation
            post_cmd = [
                "docker", "exec", "pihub-pack-service", "curl", "-s", "-X", "POST",
                "http://localhost:8030/packs/generate",
                "-H", "Content-Type: application/json",
                "-d", json.dumps(payload)
            ]
            
            resp = subprocess.run(post_cmd, capture_output=True, text=True)
            print(f"[{i+1}/{len(packs_to_regenerate)}] Regenerated {pack_id}: {resp.stdout[:100]}...")
            time.sleep(0.1)
        except Exception as e:
            print(f"Failed to regenerate {pack_id}: {e}")

if __name__ == '__main__':
    main()
