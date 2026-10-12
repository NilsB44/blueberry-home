"""Copy stroke data for every Chinese character used in the Mandarin course into
api/content/mandarin/strokes/, so character writing works without internet access.

The data comes from the hanzi-writer-data npm package (derived from Make Me a Hanzi,
Arphic Public License; see LICENSE-strokes.txt next to the data). Run after adding lessons:

    python scripts/vendor_strokes.py
"""

import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

import yaml

PACKAGE = "hanzi-writer-data@2.0.1"
ROOT = Path(__file__).resolve().parent.parent
COURSE = ROOT / "api" / "content" / "mandarin"
OUT = COURSE / "strokes"


def course_chars() -> set[str]:
    chars: set[str] = set()
    for f in COURSE.glob("*.yaml"):
        text = json.dumps(yaml.safe_load(f.read_text("utf-8")), ensure_ascii=False)
        chars |= {c for c in text if "一" <= c <= "鿿"}
    return chars


def main() -> int:
    chars = course_chars()
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["npm", "pack", PACKAGE, "--silent"], cwd=tmp, check=True)
        tarball = next(Path(tmp).glob("*.tgz"))
        with tarfile.open(tarball) as tar:
            tar.extractall(tmp, filter="data")
        pkg = Path(tmp) / "package"
        OUT.mkdir(exist_ok=True)
        missing = []
        for c in sorted(chars):
            src = pkg / f"{c}.json"
            if src.exists():
                shutil.copyfile(src, OUT / f"{c}.json")
            else:
                missing.append(c)
        for name in ("ARPHICPL.TXT", "LICENSE"):
            if (pkg / name).exists():
                shutil.copyfile(pkg / name, OUT / "LICENSE-strokes.txt")
                break
    print(f"{len(chars) - len(missing)} characters written to {OUT.relative_to(ROOT)}")
    if missing:
        print("No stroke data for:", "".join(missing))
    return 0


if __name__ == "__main__":
    sys.exit(main())
