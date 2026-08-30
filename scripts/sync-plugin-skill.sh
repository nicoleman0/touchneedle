#!/usr/bin/env bash
# Regenerate the plugin's bundled skill from the canonical root SKILL.md and
# scripts/, and stamp the version from __version__ (scripts/touchneedle.py)
# into the SKILL.md frontmatter and the plugin manifest. The module is the
# single source of truth for the version; every other copy of it is generated.
# Run this after editing either source, and after every version bump. CI fails
# if anything is stale.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
dest="$repo_root/plugins/touchneedle/skills/touchneedle"

mkdir -p "$dest/scripts"

version="$(python3 - "$repo_root" <<'PY'
import json
import pathlib
import re
import sys

root = pathlib.Path(sys.argv[1])

# __version__ in the module is the single source of truth. pyproject.toml
# reads it statically (dynamic version), so it cannot drift either.
source = (root / "scripts/touchneedle.py").read_text(encoding="utf-8")
m = re.search(r'^__version__ = "([^"]+)"', source, re.M)
if not m:
    sys.exit("could not parse __version__ from scripts/touchneedle.py")
version = m.group(1)

def terminator(line):
    return line[len(line.rstrip("\r\n")):]

# Stamp the frontmatter of the root SKILL.md. Only the first frontmatter block
# is touched, and the replaced line keeps its original terminator, so a CRLF
# checkout stays CRLF.
skill_path = root / "SKILL.md"
lines = skill_path.read_text(encoding="utf-8").splitlines(keepends=True)
if not lines or not re.match(r"^---[ \t]*$", lines[0].rstrip("\r\n")):
    sys.exit("SKILL.md does not open with a frontmatter block")
stamped = False
for i in range(1, len(lines)):
    content = lines[i].rstrip("\r\n")
    if re.match(r"^---[ \t]*$", content):
        break
    if content.startswith("version:"):
        old = content[len("version:"):].strip()
        lines[i] = f"version: {version}{terminator(lines[i])}"
        if old != version:
            print(f"SKILL.md: {old} -> {version}", file=sys.stderr)
        stamped = True
        break
if not stamped:
    sys.exit("no 'version:' line in the SKILL.md frontmatter")
skill_path.write_text("".join(lines), encoding="utf-8")

# Stamp the plugin manifest. The rewrite is line-local so the file's hand
# formatting survives, and the result is re-read as JSON: the stamp must land
# in the top-level "version" key or something structural has changed.
manifest = root / "plugins/touchneedle/.claude-plugin/plugin.json"
lines = manifest.read_text(encoding="utf-8").splitlines(keepends=True)
stamped = False
for i, line in enumerate(lines):
    m = re.match(r'^([ \t]*)"version"[ \t]*:[ \t]*"([^"]*)"[ \t]*(,?)(\r?\n)$', line)
    if not m:
        continue
    if m.group(2) != version:
        print(f"plugin.json: {m.group(2)} -> {version}", file=sys.stderr)
    lines[i] = f'{m.group(1)}"version": "{version}"{m.group(3)}{m.group(4)}'
    stamped = True
    break
if not stamped:
    sys.exit(f'no "version" line in {manifest}')
text = "".join(lines)
data = json.loads(text)
if data.get("version") != version:
    sys.exit(f'"version" in {manifest} is not a top-level key, or the stamp missed')
manifest.write_text(text, encoding="utf-8")

print(version)
PY
)"

# SKILL.md invokes the checker as scripts/touchneedle.py relative to itself,
# so the script has to travel with it.
cp "$repo_root/SKILL.md" "$dest/SKILL.md"
cp "$repo_root/scripts/touchneedle.py" "$dest/scripts/touchneedle.py"
chmod +x "$dest/scripts/touchneedle.py"

echo "synced: plugin skill + version ($version)"
