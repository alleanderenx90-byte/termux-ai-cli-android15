"""Guard tests: dependencies and docs must match what the code actually uses.

These caught real drift - the installer pulled torch (~2 GB on a phone) and
five unused packages, requirements.txt listed four packages nothing imports,
and the README advertised a Hugging Face feature that never existed.

Run with:  python -m pytest -q     (from the repository root)
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
INSTALLER = ROOT / "install.sh"
REQUIREMENTS = ROOT / "requirements.txt"

# Packages that are part of the standard library or injected by the test
# harness - not install requirements.
STDLIB_OR_LOCAL = {
    "os", "sys", "argparse", "pathlib", "io", "types", "json", "re",
    "dotenv", "llama_cpp", "openai", "anthropic",   # third-party, mapped below
    "ai_cli", "local_llm",
}

# import name -> pip package name, for the third-party imports we make.
IMPORT_TO_PACKAGE = {
    "dotenv": "python-dotenv",
    "openai": "openai",
    "anthropic": "anthropic",
    "llama_cpp": "llama-cpp-python",
}


def _imports_in(path):
    """Top-level module names imported by a file."""
    text = path.read_text()
    names = set()
    for match in re.finditer(r"^\s*(?:import|from)\s+([a-zA-Z_][a-zA-Z0-9_]*)", text, re.M):
        names.add(match.group(1))
    return names


def _requirements_packages():
    return {
        line.split(">=")[0].split("==")[0].strip()
        for line in REQUIREMENTS.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    }


@pytest.fixture(scope="module")
def third_party_imports():
    """Packages the scripts import that are not stdlib or local modules."""
    found = set()
    for script in sorted(SCRIPTS.glob("*.py")):
        for name in _imports_in(script):
            if name in IMPORT_TO_PACKAGE:
                found.add(IMPORT_TO_PACKAGE[name])
    return found


@pytest.fixture(scope="module")
def installer_pip_packages():
    """Package names from the dependency `pip install` block of install.sh only.

    Scoped to that block on purpose: a repo-wide regex also matches the
    `pkg install` system packages (git, curl, cmake, ...), the
    `pip install --upgrade pip setuptools wheel` line, and bash variable
    assignments, none of which belongs in this comparison.
    """
    text = INSTALLER.read_text()
    start = text.index("Installing AI CLI packages")
    block = text[start:text.index("\n\n", start)]
    return {
        name
        for name in re.findall(r"^\s{2}([a-z][a-z0-9-]+)\s*\\?$", block, re.M)
    }


def test_requirements_covers_every_import(third_party_imports, installer_pip_packages):
    """Every imported package must be installable - except llama-cpp-python,
    which the README installs separately because it needs a compiler."""
    listed = _requirements_packages()
    expected = third_party_imports - {"llama-cpp-python"}
    missing = expected - listed
    assert not missing, f"imported but missing from requirements.txt: {sorted(missing)}"
    # ...and the installer must actually install what is imported.
    installer_missing = expected - installer_pip_packages
    assert not installer_missing, (
        f"imported but the installer never installs it: {sorted(installer_missing)}"
    )


def test_requirements_lists_no_unused_packages(third_party_imports):
    """No dead weight - each entry costs time and storage on a phone."""
    listed = _requirements_packages()
    unused = listed - third_party_imports
    assert not unused, f"in requirements.txt but never imported: {sorted(unused)}"


def test_installer_installs_no_unused_packages(third_party_imports, installer_pip_packages):
    unused = installer_pip_packages - third_party_imports
    assert not unused, f"the installer installs these but nothing imports them: {sorted(unused)}"


def test_installer_and_requirements_agree(installer_pip_packages):
    """The two dependency lists must not drift apart.

    llama-cpp-python is the one documented exception: it needs a compiler, so
    requirements.txt leaves it out and the README installs it separately.
    """
    listed = _requirements_packages() | {"llama-cpp-python"}
    assert installer_pip_packages == listed, (
        f"installer has {sorted(installer_pip_packages - listed)} that requirements.txt lacks, "
        f"and requirements.txt has {sorted(listed - installer_pip_packages)} the installer lacks"
    )


def test_readme_advertises_no_missing_feature():
    """The README must not promise a provider or feature the code lacks."""
    readme = (ROOT / "README.md").read_text()
    claims = {
        "hugging face": re.compile(r"hugging\s*face", re.I),
        "transformers": re.compile(r"transformers", re.I),
    }
    for label, pattern in claims.items():
        # Allowed only as a download URL or an install instruction for the
        # optional local path - never as a claimed feature.
        for line in readme.splitlines():
            if pattern.search(line):
                assert "wget" in line or "pip install" in line, (
                    f"README mentions {label} outside an install/download line: {line.strip()!r}"
                )


def test_env_example_matches_installer_env():
    """Every variable the installer writes into .env must exist in .env.example.

    Only the heredoc that generates .env counts - PROJECT_DIR and friends are
    bash variables, not things a user would configure.
    """
    example = set(re.findall(r"^([A-Z_]+)=", (ROOT / ".env.example").read_text(), re.M))
    text = INSTALLER.read_text()
    block = text[text.index("<< 'EOF'") : text.index("EOF\n", text.index("<< 'EOF'"))]
    written = set(re.findall(r"^([A-Z_]+)=", block, re.M))
    missing = written - example
    assert not missing, f"installer writes these but .env.example omits them: {sorted(missing)}"
