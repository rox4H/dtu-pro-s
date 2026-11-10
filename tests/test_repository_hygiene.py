"""Guards that keep the repository English-only, consistently licensed and its documentation accurate."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKIPPED_DIRS = {
    ".git", ".venv", "venv", "node_modules", "dist", "build", ".pytest_cache", ".ruff_cache", "__pycache__",
}
# Environment variables that are read on purpose but are not part of the documented settings.
UNDOCUMENTED_VARIABLES = {"METER_SLAVE_ID", "ENV_FILE"}
MARKDOWN_LINK = re.compile(r"\]\(([^)\s]+)\)")
SPANISH_CHARACTERS = re.compile("[áéíóúñÁÉÍÓÚÑ¿¡]")

pytestmark = pytest.mark.skipif(
    not (ROOT / "pyproject.toml").is_file() or not (ROOT / "src").is_dir(),
    reason="repository layout is not available (for example when run from an installed wheel)",
)


def text_files():
    for path in sorted(ROOT.rglob("*")):
        relative = path.relative_to(ROOT)
        if not path.is_file() or SKIPPED_DIRS & set(relative.parts):
            continue
        if any(part.endswith(".egg-info") for part in relative.parts):
            continue
        try:
            yield relative.as_posix(), path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue  # binary file


def test_everything_is_written_in_english():
    offenders = [
        name
        for name, text in text_files()
        if name != "tests/test_repository_hygiene.py" and SPANISH_CHARACTERS.search(text)
    ]
    assert offenders == []


def test_both_packages_are_mit_licensed():
    if not (ROOT / "packages" / "npm-client").is_dir():
        pytest.skip("the JavaScript client is not part of this source tree")
    for license_file in (ROOT / "LICENSE", ROOT / "packages" / "npm-client" / "LICENSE"):
        text = license_file.read_text(encoding="utf-8")
        assert text.startswith("MIT License"), license_file
        assert "Permission is hereby granted, free of charge" in text
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'license = "MIT"' in pyproject
    npm = json.loads((ROOT / "packages" / "npm-client" / "package.json").read_text(encoding="utf-8"))
    assert npm["license"] == "MIT"


def test_documented_environment_variables_exist_in_the_example_file():
    if not (ROOT / ".env.example").is_file():
        pytest.skip(".env.example is not part of this source tree")
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    config = (ROOT / "src" / "hoymiles_dtu_reader" / "config.py").read_text(encoding="utf-8")
    read_by_code = set(re.findall(r'(?:getenv|_int|_float|_flag|optional_int)\(\s*"([A-Z0-9_]+)"', config))
    read_by_code |= {"DTSU666_SLAVE_ID", "DDSU666_SLAVE_ID", "METER_SLAVE_ID", "CHINT_SLAVE_ID"}
    documented = set(re.findall(r"^#?\s*([A-Z][A-Z0-9_]+)=", example, re.MULTILINE))
    internal = {"METER_SLAVE_ID", "ENV_FILE"}  # ENV_FILE selects the configuration file itself
    undocumented = sorted(name for name in read_by_code if name not in documented and name not in internal)
    assert undocumented == [], f"add these variables to .env.example: {undocumented}"


def test_configuration_guide_documents_every_environment_variable():
    guide = ROOT / "docs" / "configuration.md"
    if not guide.is_file():
        pytest.skip("docs/configuration.md is not part of this source tree")
    text = guide.read_text(encoding="utf-8")
    pattern = re.compile(r'(?:getenv|_int|_float|_flag|optional_int)\(\s*"([A-Z0-9_]+)"')
    read_by_code = set()
    for source in (ROOT / "src" / "hoymiles_dtu_reader").rglob("*.py"):
        read_by_code |= set(pattern.findall(source.read_text(encoding="utf-8")))
    read_by_code |= {"DTSU666_SLAVE_ID", "DDSU666_SLAVE_ID", "CHINT_SLAVE_ID"}
    missing = sorted(name for name in read_by_code - UNDOCUMENTED_VARIABLES if f"`{name}`" not in text)
    assert missing == [], f"document these variables in docs/configuration.md: {missing}"


def test_relative_links_in_markdown_files_point_to_existing_files():
    broken = []
    for name, text in text_files():
        if not name.endswith(".md"):
            continue
        for target in MARKDOWN_LINK.findall(text):
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            path = target.split("#", 1)[0]
            if path and not (ROOT / name).parent.joinpath(path).resolve().exists():
                broken.append(f"{name} -> {target}")
    assert broken == []
