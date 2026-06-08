#!/usr/bin/env python3
"""
Model manager for MiniSearch.
Lists all fastembed-supported embedding models, detects cache status,
downloads and deletes models from local cache.
"""

import os
import shutil
from pathlib import Path

CACHE_DIR = Path(os.path.expanduser("~/.cache/huggingface/hub"))


def list_all_models():
    """Return all supported embedding models with cache status."""
    from fastembed import TextEmbedding

    models = []
    for m in TextEmbedding.list_supported_models():
        name = m["model"]
        info = {
            "model": name,
            "dim": m.get("dim", 0),
            "size_gb": m.get("size_in_GB", 0),
            "size_mb": int(m.get("size_in_GB", 0) * 1024),
            "description": m.get("description", ""),
            "license": m.get("license", ""),
            "sources": m.get("sources", {}),
            "model_file": m.get("model_file", "model_optimized.onnx"),
        }
        info["cached"] = _is_cached(info)
        info["tags"] = _derive_tags(name, m.get("description", ""))
        models.append(info)
    return models


def _is_cached(model_info):
    """Check if a model is already downloaded to local cache."""
    sources = model_info["sources"]
    model_file = model_info["model_file"]

    # GCS / URL source models
    if sources.get("url"):
        deprecated = sources.get("_deprecated_tar_struct", False)
        prefix = "fast-" if deprecated else ""
        slug = model_info["model"].split("/")[-1]
        model_dir = CACHE_DIR / f"{prefix}{slug}"
        if model_dir.exists() and (model_dir / model_file).exists():
            return True

    # HuggingFace Hub models
    if sources.get("hf"):
        dir_name = "models--" + sources["hf"].replace("/", "--")
        model_dir = CACHE_DIR / dir_name
        snapshots = model_dir / "snapshots"
        if snapshots.is_dir():
            for snap in snapshots.iterdir():
                if (snap / model_file).is_file():
                    return True

    return False


def _derive_tags(name, description):
    """Derive display tags from model name and description."""
    tags = []
    lower = (name + " " + description).lower()
    if "zh" in lower or "chinese" in lower or "multilingual" in lower:
        if "zh" in lower:
            tags.append("中文")
        elif "multilingual" in lower:
            tags.append("多语言")
    if "english" in lower or "en-v" in lower:
        if "small-en" in lower or "base-en" in lower or "large-en" in lower:
            tags.append("英文")
    if "code" in lower:
        tags.append("代码")
    if "clip" in lower:
        tags.append("图文")
    if "recommended" in lower:
        tags.append("推荐")
    if not tags:
        tags.append("通用")
    if "small" in lower.lower() or "xs" in lower.lower():
        tags.insert(0, "小型")
    elif "large" in lower.lower() or "m3" in lower.lower():
        tags.insert(0, "大型")
    return tags


def download_model(model_info, progress_callback=None):
    """Download a model in the background. Calls progress_callback(percent, stage_msg)."""
    from fastembed import TextEmbedding

    name = model_info["model"]

    def _report(msg):
        if progress_callback:
            progress_callback(0, msg)

    _report("开始下载...")

    # fastembed's TextEmbedding __init__ downloads automatically.
    # Using lazy_load=True avoids loading the ONNX model into memory.
    TextEmbedding(
        model_name=name,
        lazy_load=True,
    )

    if progress_callback:
        progress_callback(100, "下载完成")

    model_info["cached"] = True


def delete_model(model_info):
    """Remove a model from the local cache."""
    sources = model_info["sources"]
    model_file = model_info["model_file"]

    # GCS / URL source models
    if sources.get("url"):
        deprecated = sources.get("_deprecated_tar_struct", False)
        prefix = "fast-" if deprecated else ""
        slug = model_info["model"].split("/")[-1]
        model_dir = CACHE_DIR / f"{prefix}{slug}"
        if model_dir.exists():
            shutil.rmtree(model_dir)

    # HuggingFace Hub models
    if sources.get("hf"):
        dir_name = "models--" + sources["hf"].replace("/", "--")
        model_dir = CACHE_DIR / dir_name
        if model_dir.exists():
            shutil.rmtree(model_dir)

    model_info["cached"] = False


def get_cached_size_mb(model_info):
    """Get cached model size on disk in MB."""
    sources = model_info["sources"]
    model_file = model_info["model_file"]

    def _dir_size(d):
        total = 0
        if d.exists():
            for f in d.rglob("*"):
                if f.is_file():
                    total += f.stat().st_size
        return total

    # GCS
    if sources.get("url"):
        deprecated = sources.get("_deprecated_tar_struct", False)
        prefix = "fast-" if deprecated else ""
        slug = model_info["model"].split("/")[-1]
        return round(_dir_size(CACHE_DIR / f"{prefix}{slug}") / (1024 * 1024), 1)

    # HF
    if sources.get("hf"):
        dir_name = "models--" + sources["hf"].replace("/", "--")
        return round(_dir_size(CACHE_DIR / dir_name) / (1024 * 1024), 1)

    return 0.0
