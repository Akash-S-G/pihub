# Quick Start Guide - Curriculum Builder

## 30-Second Overview

PIHUB now supports **precompiled curriculum distribution**. Build your entire curriculum once, distribute to many clients.

```bash
# Build everything in one command
cd backend/curriculum-builder
python build_complete_curriculum.py

# Done! Check the results
ls -lh complete_build/

# Build a single subject
python build_subject.py --subject maths

# Or run it from the repo root
python backend/curriculum-builder/build_subject.py --subject maths
```

## Installation

```bash
# 1. Ensure Python virtual environment is activated
cd /home/akash/Desktop/PIHUB
source .venv/bin/activate

# 2. No additional dependencies - uses standard library + existing pihub imports
# 3. Ready to use!
```

## Common Commands

### Full Curriculum Build
```bash
python build_complete_curriculum.py
```

### Build Specific Grade
```bash
python build_complete_curriculum.py --grade 7
```

### Plan Only (Dry Run)
```bash
python build_complete_curriculum.py --dry-run
```

### Custom Output Directory
```bash
python build_complete_curriculum.py --output /shared/curriculum
```

### Parallel Processing
```bash
python build_complete_curriculum.py --parallel 8
```

### Verbose Output
```bash
python build_complete_curriculum.py --verbose
```

## Output Files

| File | Size | Purpose |
|------|------|---------|
| curriculum_scan.json | 83 KB | Complete curriculum index |
| curriculum_manifest.json | 117 KB | Master curriculum structure |
| pack_registry.json | 118 KB | Pack discovery registry |
| enrichment_registry.json | 12 KB | Educational resources |
| compilation_report.json | 49 KB | Build status report |
| build_reports/build_report_<timestamp>.json | varies | Per-run build report |
| build_reports/build_report_index.json | varies | Subject index for reports |

`build_report.json` is still written as the latest compatibility copy.

## Next: Bulk Compilation

The foundation is ready. Next phase:

```bash
# Integration with pack-service to actually compile packs
# See Phase 2 in IMPLEMENTATION.md
```

## Troubleshooting

**Permission denied on /shared?**
```bash
python build_complete_curriculum.py --output ./local_build
```

**TEXTBOOKS not found?**
```bash
python build_complete_curriculum.py --textbooks-root /path/to/TEXTBOOKS
```

**Want to see what would build?**
```bash
python build_complete_curriculum.py --dry-run --verbose
```

## Documentation

- **[README.md](README.md)** - Complete feature documentation
- **[IMPLEMENTATION.md](IMPLEMENTATION.md)** - Architecture and design decisions

---

**Status**: ✅ Foundation Complete - Ready for Phase 2 Integration
