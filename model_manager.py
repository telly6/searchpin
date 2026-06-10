#!/usr/bin/env python3
"""
Model manager for MiniSearch.
Lists all fastembed-supported embedding models, detects cache status,
downloads and deletes models from local cache.
"""

import os
import shutil
import sys
import tarfile
import urllib.request
from pathlib import Path

MODEL_STORE_DIR = Path(os.path.join(os.path.dirname(__file__), "mini_search_models"))

# GitHub Releases URL for model tar.gz files
GITHUB_MODELS_BASE = (
    "https://github.com/telly6/claude-proxy/releases/download/models-v1"
)

# Only expose these models in the UI. First model is the default and auto-downloaded.
ALLOWED_MODELS = [
    "BAAI/bge-small-zh-v1.5",
    "BAAI/bge-small-en-v1.5",
    "BAAI/bge-large-en-v1.5",
    "jinaai/jina-embeddings-v2-base-zh",
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
]

MODEL_RECOMMENDATIONS = {
    "BAAI/bge-small-zh-v1.5": (
        "默认首选，覆盖中英文混合搜索。"
        "92MB 极轻量，在 C-MTEB 中文基准上达到同尺寸最佳水平，"
        "适合大多数日常搜索场景。"
    ),
    "BAAI/bge-small-en-v1.5": (
        "纯英文搜索最轻量方案。"
        "仅 68MB，384 维向量，推理速度最快，"
        "适合纯英文内容为主、对启动速度要求高的场景。"
    ),
    "BAAI/bge-large-en-v1.5": (
        "英文高质量方案。"
        "1024 维向量保留更多语义细节，MTEB 检索任务同系列最高分，"
        "适合对搜索结果质量要求高、愿意用磁盘空间换精度的场景。"
    ),
    "jinaai/jina-embeddings-v2-base-zh": (
        "中英混合长文本方案。"
        "支持 8192 token 上下文，处理长网页搜索结果不会截断，"
        "适合搜索内容偏长文、技术文档、论文摘要等场景。"
    ),
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2": (
        "多语言通用兜底方案。"
        "覆盖 50+ 语言，384 维轻量但覆盖面广，"
        "适合非中英文场景，或需要同时搜索多语言内容的场景。"
    ),
}


def list_all_models():
    """Return all supported embedding models with cache status."""
    from fastembed import TextEmbedding

    models = []
    for m in TextEmbedding.list_supported_models():
        name = m["model"]
        if name not in ALLOWED_MODELS:
            continue
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
    slug = model_info["model"].split("/")[-1]

    # GitHub-downloaded or URL-source models (fast-{slug} directory)
    fast_dir = _fastembed_cache_dir() / f"fast-{slug}"
    if fast_dir.exists() and (fast_dir / model_file).exists():
        return True
    if fast_dir.exists() and Path(model_file).parent.name:
        # Handle subdirectory paths like onnx/model.onnx
        if (fast_dir / model_file).exists():
            return True

    # HuggingFace Hub models (models--org--model/snapshots/...)
    if sources.get("hf"):
        dir_name = "models--" + sources["hf"].replace("/", "--")
        model_dir = _fastembed_cache_dir() / dir_name
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
    """Download embedding model: try GitHub first, then HuggingFace."""
    from fastembed import TextEmbedding

    if not os.environ.get("HF_ENDPOINT"):
        os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

    name = model_info["model"]
    slug = name.split("/")[-1]
    model_dir = _fastembed_cache_dir() / f"fast-{slug}"

    def _report(msg):
        if progress_callback:
            progress_callback(0, msg)
        print(f"[MiniSearch] {msg}", file=sys.stderr, flush=True)

    # Already cached?
    if model_dir.exists() and any(model_dir.iterdir()):
        _report(f"模型已缓存: {slug}")
        model_info["cached"] = True
        return

    # Try GitHub download
    targz_path = model_dir.parent / f"{slug}.tar.gz"
    url = f"{GITHUB_MODELS_BASE}/{slug}.tar.gz"

    try:
        _report(f"从 GitHub 下载 {slug}...")
        req = urllib.request.Request(url, headers={
            "User-Agent": "MiniSearch/1.0",
        })
        with urllib.request.urlopen(req, timeout=120) as resp:
            if resp.status == 200:
                total = int(resp.headers.get("Content-Length", 0))
                downloaded = 0
                chunks = []
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    chunks.append(chunk)
                    downloaded += len(chunk)
                    if total and progress_callback:
                        pct = int(downloaded / total * 90)
                        progress_callback(pct, f"下载中 ({downloaded/1024/1024:.0f}/{total/1024/1024:.0f}MB)...")
                body = b"".join(chunks)
                targz_path.write_bytes(body)
            else:
                raise Exception(f"HTTP {resp.status}")

        _report("解压中...")
        if progress_callback:
            progress_callback(90, "解压中...")
        with tarfile.open(targz_path, "r:gz") as tar:
            tar.extractall(path=model_dir.parent)
        targz_path.unlink()

        if progress_callback:
            progress_callback(100, "下载完成")
        model_info["cached"] = True
        return
    except Exception as e:
        _report(f"GitHub 下载失败: {e}，尝试 HuggingFace...")
        if targz_path.exists():
            targz_path.unlink()
        if model_dir.exists():
            shutil.rmtree(model_dir)

    # Fall back to HuggingFace
    try:
        _report(f"从 HuggingFace 下载 {slug}...")
        TextEmbedding(model_name=name, lazy_load=True)
        if progress_callback:
            progress_callback(100, "下载完成")
        model_info["cached"] = True
    except Exception as e:
        raise Exception(f"无法下载模型 {slug}: {e}")


def _fastembed_cache_dir():
    """Unified cache directory matching fastembed's native location."""
    return Path(os.path.expanduser("~/.cache/huggingface/hub"))


def delete_model(model_info):
    """Remove a model from all local cache locations."""
    sources = model_info["sources"]
    slug = model_info["model"].split("/")[-1]
    cache = _fastembed_cache_dir()

    # fast-{slug} directory (GitHub or URL-source models)
    fast_dir = cache / f"fast-{slug}"
    if fast_dir.exists():
        shutil.rmtree(fast_dir)

    # HuggingFace Hub models
    if sources.get("hf"):
        dir_name = "models--" + sources["hf"].replace("/", "--")
        model_dir = cache / dir_name
        if model_dir.exists():
            shutil.rmtree(model_dir)

    model_info["cached"] = False


def get_cached_size_mb(model_info):
    """Get cached model size on disk in MB."""
    sources = model_info["sources"]
    slug = model_info["model"].split("/")[-1]
    cache = _fastembed_cache_dir()

    def _dir_size(d):
        total = 0
        if d.exists():
            for f in d.rglob("*"):
                if f.is_file():
                    total += f.stat().st_size
        return total

    # fast-{slug} directory (GitHub or URL-source models)
    fast_dir = cache / f"fast-{slug}"
    size = _dir_size(fast_dir)
    if size > 0:
        return round(size / (1024 * 1024), 1)

    # HuggingFace Hub models
    if sources.get("hf"):
        dir_name = "models--" + sources["hf"].replace("/", "--")
        return round(_dir_size(cache / dir_name) / (1024 * 1024), 1)

    return 0.0
