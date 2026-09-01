#!/usr/bin/env bash
# Move the pins. Nothing else here moves them.
#
# **A pin nobody moves is a vulnerability kept on ice** — worse than no pin at all. A machine
# used to do this; it does not any more (DECISIONS.md `dependabot-runs-nowhere-here`), so the
# job is a person's, and this script is what that person runs.
#
#   bash pins/bump.sh --list      # the directories this moves, one per line
#   bash pins/bump.sh --subject   # the commit subject it will ask you for
#   bash pins/bump.sh --check     # say what would move, write nothing (needs the network)
#   bash pins/bump.sh             # move them, check them, print the commit to make
#
# The directories are found, never listed: whatever `pins/*/requirements.in` matches is what
# gets moved, so a new pins directory is covered the day it arrives.
#
# **Compile from the repository root, always.** The `# via -r pins/<dir>/requirements.in`
# annotation carries the path pip-compile was given, and
# `test_the_compiled_pins_are_compiled_from_the_source_beside_them` reads exactly that string.
# Compiling from inside a pins directory writes `# via -r requirements.in` instead and the gate
# goes red with nothing wrong with the pins — which is how the machine used to leave them.
set -euo pipefail

# The subject `lint_commits` accepts, held to that by tests/test_instruments_dogfood.py.
SUBJECT='build(deps): move the pinned tools'
COMPILE_FLAGS=(--allow-unsafe --generate-hashes --strip-extras --quiet)

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$root"

sources() { find pins -mindepth 2 -maxdepth 2 -name requirements.in | sort; }

case "${1:-}" in
  --list)
    sources | while read -r source; do dirname "$source"; done
    exit 0
    ;;
  --subject)
    printf '%s\n' "$SUBJECT"
    exit 0
    ;;
esac

command -v pip-compile > /dev/null || {
  echo "** pip-compile is not on this machine — it comes from pip-tools, and this script"
  echo "   will not install anything for you: what installs the tools is your decision."
  exit 2
}

if [ "${1:-}" = "--check" ]; then
  echo "== what would move (nothing is written) =="
  sources | while read -r source; do
    echo "-- $source"
    pip-compile "${COMPILE_FLAGS[@]}" --upgrade --dry-run \
      --output-file="${source%.in}.txt" "$source" 2>&1 | grep -E '^[a-zA-Z0-9._-]+==' || true
  done
  exit 0
fi

[ -z "$(git status --porcelain)" ] || {
  echo "** the working tree is not clean — the diff below would be mixed with your own work"
  exit 1
}
[ "$(git branch --show-current)" != "main" ] || {
  echo "** on main: make a branch first, this repository takes changes through pull requests"
  exit 1
}

before=$(mktemp) && trap 'rm -f "$before"' EXIT
git diff --stat > "$before"

echo "== moving =="
sources | while read -r source; do
  echo "-- $source"
  pip-compile "${COMPILE_FLAGS[@]}" --upgrade --output-file="${source%.in}.txt" "$source"
done

echo "== the annotations still name the path we compiled from =="
failed=0
sources | while read -r source; do
  compiled="${source%.in}.txt"
  if grep -q "via -r $source" "$compiled"; then
    echo "   $compiled: ok"
  else
    echo "** $compiled: its annotations lost the path — compile from the repository root"
    failed=1
  fi
done
[ "$failed" -eq 0 ] || exit 1

echo "== what moved =="
git diff -U0 -- 'pins/*/requirements.txt' | grep -E '^[+-][a-zA-Z0-9._-]+==' | sort -t= -k1 || \
  echo "   nothing — every pin was already the newest that resolves"

echo "== the checks that read these files =="
.venv/bin/python -m pytest -q --no-header tests/test_instruments_dogfood.py tests/test_shipped_requirements.py 2>&1 | tail -2

cat <<COMMIT

== to keep it ==
   git add pins
   git commit -s -m '$SUBJECT'

Read the diff first. If a tool moved, install it before you trust the suite:
   .venv/bin/python -m pip install --require-hashes -r pins/dev/requirements.txt
COMMIT
