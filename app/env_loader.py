from __future__ import annotations

import os
from pathlib import Path


def load_env_fallback(env_path: Path):
    """Надежный загрузчик .env без обязательной внешней библиотеки python-dotenv."""
    try:
        from dotenv import load_dotenv
        load_dotenv(env_path)
    except ImportError:
        pass

    if env_path.exists():
        try:
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                if k and k not in os.environ:
                    os.environ[k] = v
        except Exception:
            pass
