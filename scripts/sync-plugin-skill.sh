#!/usr/bin/env bash
# Regenerate the plugin's bundled skill from the canonical root SKILL.md and
# scripts/. The root copy is the single source of truth; the plugin copy is
# generated. Run this after editing either. CI fails if the copy is stale.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
dest="$repo_root/plugins/touchneedle/skills/touchneedle"

mkdir -p "$dest/scripts"
cp "$repo_root/SKILL.md" "$dest/SKILL.md"
# SKILL.md invokes the checker as scripts/touchneedle.py relative to itself,
# so the script has to travel with it.
cp "$repo_root/scripts/touchneedle.py" "$dest/scripts/touchneedle.py"
chmod +x "$dest/scripts/touchneedle.py"

# Keep the three hand-maintained version numbers in lockstep. pyproject.toml is
# not among them: it reads __version__ out of the module (dynamic version), so
# it cannot drift. Read the SKILL.md version only from the first frontmatter
# block, and strip any CR so a CRLF checkout cannot forge a match on
# visually-identical strings.
skill_version="$(
  sed -n '/^---[[:space:]]*$/,/^---[[:space:]]*$/ s/^version:[[:space:]]*//p' \
    "$repo_root/SKILL.md" | head -n1 | tr -d '\r'
)"
if [ -z "$skill_version" ]; then
  echo "could not parse 'version:' from SKILL.md frontmatter" >&2
  exit 1
fi

read -r plugin_version script_version <<EOF2
$(python3 - "$repo_root" <<'PY'
import json
import pathlib
import re
import sys

root = pathlib.Path(sys.argv[1])

manifest = root / "plugins/touchneedle/.claude-plugin/plugin.json"
try:
    data = json.loads(manifest.read_text(encoding="utf-8"))
except FileNotFoundError:
    sys.exit(f"missing plugin manifest: {manifest}")
except json.JSONDecodeError as e:
    sys.exit(f"invalid JSON in {manifest}: {e}")

plugin_version = data.get("version")
if not isinstance(plugin_version, str) or not plugin_version:
    sys.exit(f'invalid or missing "version" in {manifest}')

source = (root / "scripts/touchneedle.py").read_text(encoding="utf-8")
m = re.search(r'^__version__ = "([^"]+)"', source, re.M)
if not m:
    sys.exit("could not parse __version__ from scripts/touchneedle.py")

print(plugin_version, m.group(1))
PY
)
EOF2

if [ "$skill_version" != "$plugin_version" ] \
  || [ "$skill_version" != "$script_version" ]; then
  echo "version mismatch:" >&2
  echo "  SKILL.md       = $skill_version" >&2
  echo "  plugin.json    = $plugin_version" >&2
  echo "  touchneedle.py = $script_version" >&2
  exit 1
fi

echo "synced: plugin skill + version ($skill_version)"
