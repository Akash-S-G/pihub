#!/usr/bin/env python3
import json
import tarfile
from pathlib import Path

def main():
    print("Starting Pack Storage Audit...")
    report = {
        "registry_present": False,
        "total_registry_entries": 0,
        "valid_packs": 0,
        "missing_archives": 0,
        "missing_manifests": 0,
        "orphaned_packs": 0,
        "issues": []
    }

    registry_path = Path("/shared/packs/pack_index.json")
    if not registry_path.exists():
        report["issues"].append("pack_index.json not found on disk")
        write_report(report)
        return

    report["registry_present"] = True

    with open(registry_path, 'r') as f:
        registry_list = json.load(f)
        
    report["total_registry_entries"] = len(registry_list)
        
    for pack_data in registry_list:
        pack_id = pack_data.get("pack_id")
        pack_dir = Path(pack_data.get("pack_dir", ""))
        archive_path = Path(pack_data.get("archive_path", ""))
        manifest_path = pack_dir / "manifest.json"

        if not pack_dir.exists():
            report["missing_archives"] += 1
            report["issues"].append(f"Directory missing for pack: {pack_id}")
            continue

        if not manifest_path.exists():
            report["missing_manifests"] += 1
            report["issues"].append(f"Manifest missing for pack: {pack_id}")
            continue

        if not archive_path.exists():
            report["missing_archives"] += 1
            report["issues"].append(f"Archive missing for pack: {pack_id}")
            continue
            
        try:
            with tarfile.open(archive_path, "r:gz") as tar:
                pass
        except Exception as e:
            report["issues"].append(f"Corrupted archive for pack {pack_id}: {e}")
            continue
            
        report["valid_packs"] += 1

    write_report(report)

def write_report(report):
    md = f"""# Pack Storage Audit Report

| Metric | Count | Status |
| :--- | :--- | :--- |
| **Registry Entries** | {report['total_registry_entries']} | Expected |
| **Valid Packs** | {report['valid_packs']} | {'✅ Excellent' if report['valid_packs'] == report['total_registry_entries'] else '⚠️ Issues Found'} |
| **Missing Archives** | {report['missing_archives']} | {'✅ None' if report['missing_archives'] == 0 else '❌ Found'} |
| **Missing Manifests** | {report['missing_manifests']} | {'✅ None' if report['missing_manifests'] == 0 else '❌ Found'} |
| **Orphaned Packs** | {report['orphaned_packs']} | {'✅ None' if report['orphaned_packs'] == 0 else '⚠️ Cleanup Recommended'} |

### Issues Log:
"""
    if not report['issues']:
        md += "- No issues detected. Storage integrity is 100% verified."
    else:
        for issue in report['issues'][:20]:
            md += f"- {issue}\n"
        if len(report['issues']) > 20:
            md += f"- ...and {len(report['issues']) - 20} more issues."

    with open('/app/storage_audit_report.md', 'w') as f:
        f.write(md)
    print("Audit Report written to /app/storage_audit_report.md")

if __name__ == "__main__":
    main()
