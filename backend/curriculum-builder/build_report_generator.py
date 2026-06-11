"""Generate build reports and summaries."""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional


class BuildReportGenerator:
    """Generate comprehensive build reports."""

    @staticmethod
    def create_full_report(
        build_output_dir: Path,
        textbooks_root: Optional[Path] = None,
        target_grade: Optional[int] = None,
        target_subject: Optional[str] = None,
    ) -> Dict:
        """
        Create comprehensive build report.

        Args:
            build_output_dir: Directory containing build artifacts
            textbooks_root: Path to TEXTBOOKS directory
            target_grade: If built for specific grade
            target_subject: If built for specific subject

        Returns:
            Comprehensive build report
        """
        report = {
            "build_info": {
                "timestamp": datetime.utcnow().isoformat(),
                "output_directory": str(build_output_dir),
                "target_grade": target_grade,
                "target_subject": target_subject,
            },
            "artifacts": {},
            "summary": {
                "total_packs": 0,
                "total_chapters": 0,
                "total_grades": 0,
                "total_subjects": 0,
                "total_languages": 0,
                "total_size_mb": 0,
            },
            "next_steps": [],
        }

        # Analyze each artifact
        scan_file = build_output_dir / "curriculum_scan.json"
        if scan_file.exists():
            with open(scan_file) as f:
                scan_data = json.load(f)

            report["artifacts"]["curriculum_scan"] = {
                "path": str(scan_file),
                "size_mb": scan_file.stat().st_size / (1024 * 1024),
                "pdf_count": scan_data["metadata"]["total_pdfs"],
                "grades": scan_data["metadata"]["grades"],
                "subjects": scan_data["metadata"]["subjects"],
                "languages": scan_data["metadata"]["languages"],
            }

            report["summary"]["total_chapters"] = scan_data["metadata"]["total_pdfs"]
            report["summary"]["total_grades"] = len(scan_data["metadata"]["grades"])
            report["summary"]["total_subjects"] = len(scan_data["metadata"]["subjects"])
            report["summary"]["total_languages"] = len(scan_data["metadata"]["languages"])

        manifest_file = build_output_dir / "curriculum_manifest.json"
        if manifest_file.exists():
            with open(manifest_file) as f:
                manifest_data = json.load(f)

            report["artifacts"]["curriculum_manifest"] = {
                "path": str(manifest_file),
                "size_mb": manifest_file.stat().st_size / (1024 * 1024),
                "version": manifest_data["metadata"]["version"],
                "entries": len(manifest_data["curriculum_index"]),
                "hash": manifest_data.get("_hash", "")[:16] + "...",
            }

        registry_file = build_output_dir / "pack_registry.json"
        if registry_file.exists():
            with open(registry_file) as f:
                registry_data = json.load(f)

            report["artifacts"]["pack_registry"] = {
                "path": str(registry_file),
                "size_mb": registry_file.stat().st_size / (1024 * 1024),
                "total_packs": registry_data["metadata"]["total_packs"],
                "total_size_mb": registry_data["metadata"]["total_size_bytes"] / (1024 * 1024),
                "hash": registry_data["metadata"]["registry_hash"][:16] + "...",
            }

            report["summary"]["total_packs"] = registry_data["metadata"]["total_packs"]

        enrichment_file = build_output_dir / "enrichment_registry.json"
        if enrichment_file.exists():
            with open(enrichment_file) as f:
                enrichment_data = json.load(f)

            report["artifacts"]["enrichment_registry"] = {
                "path": str(enrichment_file),
                "size_mb": enrichment_file.stat().st_size / (1024 * 1024),
                "total_mappings": enrichment_data["metadata"]["total_mappings"],
                "simulations": enrichment_data["metadata"].get("total_simulations", 0),
                "experiments": enrichment_data["metadata"].get("total_experiments", 0),
                "videos": enrichment_data["metadata"].get("total_videos", 0),
                "virtual_labs": enrichment_data["metadata"].get("total_virtual_labs", 0),
                "animations": enrichment_data["metadata"].get("total_animations", 0),
            }

        compilation_file = build_output_dir / "compilation_report.json"
        if compilation_file.exists():
            with open(compilation_file) as f:
                compilation_data = json.load(f)

            report["artifacts"]["compilation_report"] = {
                "path": str(compilation_file),
                "size_mb": compilation_file.stat().st_size / (1024 * 1024),
                "total_tasks": compilation_data["total_tasks"],
                "completed": compilation_data["completed"],
                "failed": compilation_data["failed"],
                "duration_seconds": compilation_data["duration_seconds"],
            }

        # Calculate total size
        total_size = sum(
            artifact.get("size_mb", 0) + artifact.get("total_size_mb", 0)
            for artifact in report["artifacts"].values()
        )
        report["summary"]["total_size_mb"] = total_size

        # Add next steps
        report["next_steps"] = [
            "1. Validate curriculum using validation pipeline: python validate_curriculum.py",
            "2. Verify Docker integration: docker compose build pack-service",
            "3. Test pack APIs: curl http://localhost:8030/packs/",
            "4. Distribute packs to Pi devices via sync service",
            "5. Monitor retrieval quality metrics",
        ]

        return report

    @staticmethod
    def save_report(report: Dict, output_path: Path) -> None:
        """
        Save build report to JSON.

        Args:
            report: Build report
            output_path: Path to save report
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            json.dump(report, f, indent=2)

    @staticmethod
    def print_report(report: Dict) -> None:
        """Print build report summary."""
        info = report["build_info"]
        summary = report["summary"]

        print("\n" + "=" * 70)
        print("CURRICULUM BUILD REPORT")
        print("=" * 70)
        print(f"Timestamp: {info['timestamp']}")
        print(f"Output Directory: {info['output_directory']}")

        if info["target_grade"]:
            print(f"Target Grade: {info['target_grade']}")
        if info["target_subject"]:
            print(f"Target Subject: {info['target_subject']}")

        print()
        print("SUMMARY:")
        print(f"  Total Packs: {summary['total_packs']}")
        print(f"  Total Chapters: {summary['total_chapters']}")
        print(f"  Grades: {summary['total_grades']}")
        print(f"  Subjects: {summary['total_subjects']}")
        print(f"  Languages: {summary['total_languages']}")
        print(f"  Total Size: {summary['total_size_mb']:.1f} MB")

        print()
        print("ARTIFACTS:")
        for name, artifact in report["artifacts"].items():
            path = Path(artifact["path"]).name
            size = artifact.get("size_mb", 0)
            print(f"  {name}: {path} ({size:.1f} MB)")

        print()
        print("NEXT STEPS:")
        for step in report["next_steps"]:
            print(f"  {step}")

        print()
        print("=" * 70)
