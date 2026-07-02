"""One-time model download for Searchpin.

This runs as ``searchpin-setup`` after ``pip install searchpin``.
Downloads the embedding model (~118MB) so searchpin-server starts instantly.
Skips if already cached.
"""

import os
import sys
import warnings

from searchpin.config import DEFAULT_MODEL_NAME as MODEL_NAME

# 3-line colored output — no heavy deps
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
RESET = "\033[0m"
BOLD = "\033[1m"

# fastembed warns about CLS→mean pooling; harmless, suppress for clean output
warnings.filterwarnings("ignore", message=".*mean pooling.*")


def _is_cached(cache_dir):
    """Return True if the model is already in the local cache."""
    try:
        from fastembed import TextEmbedding
        TextEmbedding(model_name=MODEL_NAME, cache_dir=cache_dir, local_files_only=True)
        return True
    except Exception:
        return False


def main():
    cache_dir = os.path.expanduser("~/.cache/huggingface/hub")

    if _is_cached(cache_dir):
        print(f"{GREEN}[Searchpin] Model already cached ✓{RESET}")
        return 0

    # ── download via fastembed ──────────────────────────────
    print(f"{BOLD}[Searchpin] First-time setup: downloading embedding model (~118MB, one-time only){RESET}")
    print(f"[Searchpin] Source: https://hf-mirror.com")

    if not os.environ.get("HF_ENDPOINT"):
        os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

    try:
        from fastembed import TextEmbedding

        TextEmbedding(
            model_name=MODEL_NAME,
            cache_dir=cache_dir,
            local_files_only=False,
        )
    except Exception as e:
        print(f"\n{RED}[Searchpin] Download failed: {e}{RESET}")
        print(f"{YELLOW}[Searchpin] The model will be downloaded automatically on first searchpin-server start.{RESET}")
        print(f"{YELLOW}[Searchpin] If you are offline, connect to the internet and run `searchpin-setup` again.{RESET}")
        return 1

    # ── verify ──────────────────────────────────────────────
    if _is_cached(cache_dir):
        print(f"{GREEN}[Searchpin] Model cached ✓  searchpin-server is ready to use.{RESET}")
    else:
        print(f"{YELLOW}[Searchpin] Model downloaded but verification failed. It will retry on first use.{RESET}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
