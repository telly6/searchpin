#!/usr/bin/env python3
"""
Package one embedding model as a self-contained tar.gz for GitHub Releases.

Usage:
  python3 package_models.py BAAI/bge-small-zh-v1.5

Downloads the model via fastembed (HF mirror), then repacks as a flat tar.gz.
Upload the output to a GitHub Release tagged 'models-v1' and SearchEngine
downloads from there automatically via direct HTTP (no HF API needed).

Output: packaged_models/{model_slug}.tar.gz
"""

import os
import sys
import shutil
import tarfile
from pathlib import Path

if not os.environ.get("HF_ENDPOINT"):
    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

MODEL_FILE_MAP = {
    "BAAI/bge-small-zh-v1.5": "model_optimized.onnx",
    "BAAI/bge-small-en-v1.5": "model_optimized.onnx",
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2": "model_optimized.onnx",
}

OUTPUT_DIR = Path("packaged_models")


def package_model(model_name):
    from fastembed import TextEmbedding

    model_file = MODEL_FILE_MAP.get(model_name, "model_optimized.onnx")
    needs_subdir = "/" in model_file
    slug = model_name.split("/")[-1]

    print(f"Packaging: {model_name}")
    print(f"  file={model_file}, subdir={needs_subdir}")

    print("  downloading via fastembed (HF mirror)...")
    model = TextEmbedding(model_name=model_name, lazy_load=True)
    model_dir = Path(model.model._model_dir)
    print(f"  cached at: {model_dir}")

    required_extensions = {".json", ".onnx", ".txt"}
    files = [f for f in sorted(model_dir.rglob("*"))
             if f.is_file() and f.suffix in required_extensions]

    OUTPUT_DIR.mkdir(exist_ok=True)
    pkg_dir = OUTPUT_DIR / f"fast-{slug}"
    if pkg_dir.exists():
        shutil.rmtree(pkg_dir)
    pkg_dir.mkdir()

    for f in files:
        if needs_subdir and f.name == Path(model_file).name:
            sub = pkg_dir / Path(model_file).parent
            sub.mkdir(exist_ok=True)
            (sub / f.name).write_bytes(f.read_bytes())
        else:
            (pkg_dir / f.name).write_bytes(f.read_bytes())

    targz_path = OUTPUT_DIR / f"{slug}.tar.gz"
    with tarfile.open(targz_path, "w:gz") as tar:
        for f in sorted(pkg_dir.rglob("*")):
            if f.is_file():
                tar.add(f, arcname=str(f.relative_to(OUTPUT_DIR)))

    shutil.rmtree(pkg_dir)

    size_mb = targz_path.stat().st_size / 1024 / 1024
    print(f"  done: {targz_path.name} ({size_mb:.1f}MB)")
    return targz_path


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 package_models.py <model_name>")
        print("Available models:")
        for m in MODEL_FILE_MAP:
            print(f"  {m}")
        sys.exit(1)

    model_name = sys.argv[1]
    if model_name not in MODEL_FILE_MAP:
        print(f"Unknown model: {model_name}")
        print("Available:", list(MODEL_FILE_MAP.keys()))
        sys.exit(1)

    print(f"HF Endpoint: {os.environ.get('HF_ENDPOINT')}")
    path = package_model(model_name)
    print(f"\nUpload {path} to GitHub Release 'models-v1'")


if __name__ == "__main__":
    main()
