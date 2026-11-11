"""
Downloads the local speech models AGROBOTAI uses (once; later runs just verify the cache).

    .venv\\Scripts\\python.exe scripts\\download_models.py          download / verify all
    .venv\\Scripts\\python.exe scripts\\download_models.py --check  only report what is missing

* openai/whisper-large-v3-turbo   speech-to-text, ~1.6 GB
* facebook/mms-tts-*              offline voices for the 12 app languages, ~145 MB each
Models go to the Hugging Face cache (%USERPROFILE%\\.cache\\huggingface).
The crop disease / pest models (models\\*.pt) ship with the project and are only checked here.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8")

PATTERNS = ["*.json", "*.safetensors", "*.txt", "*.model", "vocab*", "tokenizer*", "merges*"]


def repos() -> list[str]:
    from src.speech import LANGS, WHISPER_MODEL

    return [WHISPER_MODEL] + [v[1] for v in LANGS.values()]


def main() -> int:
    check_only = "--check" in sys.argv
    from huggingface_hub import snapshot_download

    missing = []
    for name in ("disease_model.pt", "pest_model.pt"):
        path = ROOT / "models" / name
        print(f"[{'OK' if path.exists() else 'MISSING'}] models/{name}")
        if not path.exists():
            missing.append(f"models/{name} (copy it from the project backup or retrain with train_models.py)")

    for repo in repos():
        try:
            snapshot_download(repo, allow_patterns=PATTERNS, local_files_only=True)
            print(f"[OK] {repo} (already downloaded)")
            continue
        except Exception:  # noqa: BLE001 - not in the cache yet
            pass
        if check_only:
            print(f"[MISSING] {repo}")
            missing.append(repo)
            continue
        started = time.time()
        for attempt in range(1, 4):
            try:
                print(f"[..] downloading {repo} (attempt {attempt}) ...", flush=True)
                snapshot_download(repo, allow_patterns=PATTERNS)
                print(f"[OK] {repo} downloaded in {time.time() - started:.0f} s", flush=True)
                break
            except Exception as exc:  # noqa: BLE001 - network hiccups: retry, then report
                print(f"[WARN] {repo}: {exc}")
                time.sleep(5 * attempt)
        else:
            missing.append(repo)

    if missing:
        print("\nStill missing:\n  " + "\n  ".join(missing))
        return 1
    print("\nAll AI models are present.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
