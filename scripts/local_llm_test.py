#!/usr/bin/env python3
"""Deprecated shim - use scripts/local_llm.py instead.

Kept so existing instructions and muscle memory keep working. Everything the
old script did is available in local_llm.py with more options.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

print(
    "Note: local_llm_test.py is deprecated, use local_llm.py instead.",
    file=sys.stderr,
)

import local_llm  # noqa: E402

if __name__ == "__main__":
    sys.exit(local_llm.main())
