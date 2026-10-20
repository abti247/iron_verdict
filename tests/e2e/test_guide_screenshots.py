"""Guide screenshots (#157).

``scripts/guide_screenshots.py`` starts the app locally and photographs the
motifs for the in-app guide in German and English as WebP: the display with
a "No Lift" result including the reasons, and the display in the layout
editor (block frames, hide toggles). The script fails if the display does
not show the requested language. The images contain example data only.
"""

import base64
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "guide_screenshots.py"
MOTIFS = ("result-reasons", "layout-editor")
LANGS = ("de", "en")
MAX_BYTES = 150_000


def test_script_writes_both_motifs_in_both_languages_as_webp(page, tmp_path):
    """Run the script into a temporary directory → for DE and EN it writes
    both motifs as WebP files that Chromium decodes at 1280×720 and that stay
    below the size budget. The German and English images differ."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--out", str(tmp_path)],
        cwd=ROOT, capture_output=True, text=True, timeout=180,
    )
    assert result.returncode == 0, result.stdout + result.stderr

    written = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*") if p.is_file())
    assert written == sorted(f"{lang}/{motif}.webp" for lang in LANGS for motif in MOTIFS)

    for name in written:
        data = (tmp_path / name).read_bytes()
        assert data[:4] == b"RIFF" and data[8:12] == b"WEBP", name
        assert len(data) < MAX_BYTES, f"{name}: {len(data)} bytes"
        size = page.evaluate(
            """async (src) => {
                const img = new Image();
                img.src = src;
                await img.decode();
                return [img.naturalWidth, img.naturalHeight];
            }""",
            "data:image/webp;base64," + base64.b64encode(data).decode(),
        )
        assert size == [1280, 720], name

    for motif in MOTIFS:
        de = (tmp_path / "de" / f"{motif}.webp").read_bytes()
        en = (tmp_path / "en" / f"{motif}.webp").read_bytes()
        assert de != en, motif
