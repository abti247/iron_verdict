import importlib.util
import pathlib
import subprocess
import sys

import pytest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "changelog_section.py"

_spec = importlib.util.spec_from_file_location("changelog_section", SCRIPT)
changelog_section = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(changelog_section)
extract_section = changelog_section.extract_section

CHANGELOG = """# Changelog

Intro text.

## [Unreleased]

### Added

### Fixed

## [0.2.0] - 2026-10-10

### Added
- New thing

### Fixed
- Old bug

[0.2.0]: https://github.com/abti247/iron_verdict/compare/v0.1.4-beta...v0.2.0

## [0.1.4-beta] - 2026-05-20

### Added
- Older thing

[0.1.4-beta]: https://github.com/abti247/iron_verdict/compare/v0.1.3-beta...v0.1.4-beta
"""


def test_extract_section_returns_heading_body_and_compare_link():
    section = extract_section(CHANGELOG, "0.2.0")
    assert section == (
        "## [0.2.0] - 2026-10-10\n"
        "\n"
        "### Added\n"
        "- New thing\n"
        "\n"
        "### Fixed\n"
        "- Old bug\n"
        "\n"
        "[0.2.0]: https://github.com/abti247/iron_verdict/compare/v0.1.4-beta...v0.2.0\n"
    )


def test_extract_section_last_section_runs_to_end_of_file():
    section = extract_section(CHANGELOG, "0.1.4-beta")
    assert section.startswith("## [0.1.4-beta] - 2026-05-20\n")
    assert section.endswith("compare/v0.1.3-beta...v0.1.4-beta\n")


def test_extract_section_does_not_match_version_prefix():
    with pytest.raises(LookupError):
        extract_section(CHANGELOG, "0.1.4")


def test_extract_section_missing_version_raises():
    with pytest.raises(LookupError):
        extract_section(CHANGELOG, "9.9.9")


def test_extract_section_without_entries_raises():
    with pytest.raises(LookupError):
        extract_section(CHANGELOG, "Unreleased")


def test_extract_section_handles_crlf_line_endings():
    section = extract_section(CHANGELOG.replace("\n", "\r\n"), "0.2.0")
    assert section.startswith("## [0.2.0] - 2026-10-10\n")
    assert "\r" not in section


def test_cli_prints_section_and_fails_for_unknown_version(tmp_path):
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(CHANGELOG, encoding="utf-8")

    ok = subprocess.run(
        [sys.executable, str(SCRIPT), "0.2.0", "--changelog", str(changelog)],
        capture_output=True, text=True,
    )
    assert ok.returncode == 0
    assert ok.stdout == extract_section(CHANGELOG, "0.2.0")

    missing = subprocess.run(
        [sys.executable, str(SCRIPT), "9.9.9", "--changelog", str(changelog)],
        capture_output=True, text=True,
    )
    assert missing.returncode == 1
    assert "9.9.9" in missing.stderr


def test_repository_changelog_has_released_section():
    root = SCRIPT.parents[1]
    text = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    assert extract_section(text, "0.1.4-beta").startswith("## [0.1.4-beta]")
