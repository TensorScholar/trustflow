import argparse
import re
import subprocess
import tomllib
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--tag", required=True)
args = parser.parse_args()
with Path("pyproject.toml").open("rb") as handle:
    version = tomllib.load(handle)["project"]["version"]
expected = f"v{version}"
if args.tag != expected:
    raise SystemExit(f"tag mismatch: expected {expected}, got {args.tag}")

version_file = Path("src/trustflow/_version.py").read_text(encoding="utf-8")
match = re.search(r'__version__\s*=\s*"([^"]+)"', version_file)
if match is None or match.group(1) != version:
    raise SystemExit("package version does not match pyproject.toml")

citation = Path("CITATION.cff").read_text(encoding="utf-8")
if f'version: "{version}"' not in citation:
    raise SystemExit("CITATION.cff version does not match pyproject.toml")

for path in ("CHANGELOG.md", "CITATION.cff", "README.md", "SECURITY.md"):
    if not Path(path).is_file():
        raise SystemExit(f"missing release file: {path}")

status = subprocess.check_output(["git", "status", "--porcelain"], text=True)
if status:
    raise SystemExit("release worktree is not clean")
print(f"release metadata valid for {args.tag}")
