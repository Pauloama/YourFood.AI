#!/usr/bin/env python3
"""Export and bundle versioned model artifacts for production deployment.

Usage:
    python scripts/export_models.py --source artifacts --destination artifacts/exported
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from absa.logging_config import get_logger, setup_logging

logger = get_logger(__name__)


def get_git_commit() -> str:
    """Attempt to get current git commit hash."""
    try:
        out = subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL)
        return out.decode().strip()
    except Exception:
        return "unknown"


def get_environment_info() -> dict[str, str]:
    """Capture library versions."""
    packages = ["torch", "transformers", "scikit-learn", "fastapi", "pydantic"]
    info = {"python": sys.version}
    for pkg in packages:
        try:
            info[pkg] = importlib.metadata.version(pkg)
        except Exception:
            info[pkg] = "not_installed"
    return info


def export_artifact_bundle(
    src_dir: Path,
    dest_dir: Path,
    model_name: str,
    version: str,
) -> Path:
    """Standardize exported artifact folder structure."""
    target_dir = dest_dir / model_name / version
    target_dir.mkdir(parents=True, exist_ok=True)

    # Copy model and tokenizer
    best_model = src_dir / "best_model"
    if (best_model / "model").exists():
        shutil.copytree(best_model / "model", target_dir / "model", dirs_exist_ok=True)
        shutil.copytree(best_model / "tokenizer", target_dir / "tokenizer", dirs_exist_ok=True)
    elif (src_dir / "model").exists():
        shutil.copytree(src_dir / "model", target_dir / "model", dirs_exist_ok=True)
        shutil.copytree(src_dir / "tokenizer", target_dir / "tokenizer", dirs_exist_ok=True)

    # Copy json/yaml metadata files
    for fname in ["labels.json", "thresholds.json", "taxonomy.json", "training_config.yaml", "val_metrics.json", "metrics.json", "metadata.json"]:
        fpath = src_dir / fname
        if fpath.exists():
            shutil.copy(fpath, target_dir / fname)

    # Write export metadata
    meta = {
        "model_name": model_name,
        "version": version,
        "exported_at": datetime.now().isoformat(),
        "git_commit": get_git_commit(),
        "environment": get_environment_info(),
    }
    with open(target_dir / "export_info.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    logger.info("exported_bundle_success", target=str(target_dir))
    return target_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Export model artifacts")
    parser.add_argument("--source", default="artifacts", help="Source artifacts dir")
    parser.add_argument("--destination", default="artifacts/exported", help="Export destination dir")
    args = parser.parse_args()

    setup_logging(level="INFO")
    src = Path(args.source)
    dst = Path(args.destination)

    aspect_src = src / "aspect-detector" / "bertimbau-aspects-v1"
    sentiment_src = src / "sentiment-classifier" / "bertimbau-aspect-sentiment-v1"

    if aspect_src.exists():
        export_artifact_bundle(aspect_src, dst, "aspect-detector", "bertimbau-aspects-v1")
    if sentiment_src.exists():
        export_artifact_bundle(sentiment_src, dst, "sentiment-classifier", "bertimbau-aspect-sentiment-v1")

    print(f"Export completed to {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
