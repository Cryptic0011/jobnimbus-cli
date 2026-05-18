#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_DIR="$SCRIPT_DIR/agent-harness"
SKILL_SOURCE="$PACKAGE_DIR/cli_anything/jobnimbus/skills/SKILL.md"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Error: python3 is required but was not found on PATH." >&2
  exit 1
fi

if ! python3 -m pip --version >/dev/null 2>&1; then
  echo "Error: python3 -m pip is required but is not available." >&2
  exit 1
fi

PYTHON_BIN="$(command -v python3)"
USER_BASE="$("$PYTHON_BIN" - <<'PY'
import site
print(site.getuserbase())
PY
)"
USER_BIN="$USER_BASE/bin"

echo "Installing cli-anything-jobnimbus as a user-level Python package..."
PIP_INSTALL_ARGS=(install --user --upgrade "$PACKAGE_DIR")
if ! "$PYTHON_BIN" -m pip "${PIP_INSTALL_ARGS[@]}"; then
  echo "Retrying with --break-system-packages for externally-managed Python..."
  "$PYTHON_BIN" -m pip install --user --upgrade --break-system-packages "$PACKAGE_DIR"
fi

install_skill() {
  local agent_name="$1"
  local home_dir="$2"
  if [[ -d "$home_dir" ]]; then
    local skill_dir="$home_dir/skills/jobnimbus-read-cli"
    mkdir -p "$skill_dir"
    cp "$SKILL_SOURCE" "$skill_dir/SKILL.md"
    echo "Installed $agent_name skill to $skill_dir"
  else
    echo "Skipped $agent_name skill install because $home_dir does not exist."
  fi
}

install_skill "Claude" "$HOME/.claude"
install_skill "Codex" "${CODEX_HOME:-$HOME/.codex}"
install_skill "OpenClaw" "$HOME/.openclaw"

# Install a stable `jn` wrapper into ~/.local/bin, which is on PATH for most
# shells. This avoids relying on the Python user bin (which is version-keyed,
# e.g. .../Python/3.14/bin, and silently drops off PATH after a Python upgrade).
LOCAL_BIN="$HOME/.local/bin"
mkdir -p "$LOCAL_BIN"
cat > "$LOCAL_BIN/jn" <<'WRAPPER'
#!/usr/bin/env bash
# Wrapper for the JobNimbus Read-Only CLI. Survives Python version bumps
# as long as the cli-anything-jobnimbus package is installed for python3.
exec python3 -m cli_anything.jobnimbus "$@"
WRAPPER
chmod +x "$LOCAL_BIN/jn"
echo "Installed 'jn' wrapper to $LOCAL_BIN/jn"

echo
echo "Install complete."
echo "Python command: $PYTHON_BIN"
echo "CLI command: $LOCAL_BIN/jn"

if [[ ":$PATH:" != *":$LOCAL_BIN:"* ]]; then
  echo
  echo "Add this to your shell profile if 'jn' is not found in a new terminal:"
  echo "  export PATH=\"$LOCAL_BIN:\$PATH\""
fi

echo
echo "Next step:"
echo "  export JOBNIMBUS_API_KEY=\"your-api-key\""
echo "  jn --help"
