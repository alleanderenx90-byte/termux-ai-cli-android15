#!/usr/bin/env bash
set -euo pipefail

# Termux AI CLI - Uninstaller
# Removes everything install.sh created under ~/ai-projects.
#
# It does NOT remove the Termux packages (python, git, cmake, ...) that
# install.sh installed, because other tools on the device may depend on
# them. Remove those by hand if you want them gone.

PROJECT_DIR="${1:-$HOME/ai-projects}"

echo "================================================="
echo "Termux AI CLI - Uninstaller"
echo "================================================="
echo "Target: $PROJECT_DIR"
echo ""

if [ ! -d "$PROJECT_DIR" ]; then
  echo "Nothing to remove: $PROJECT_DIR does not exist."
  exit 0
fi

# Warn before deleting the .env, since it holds the user's API keys and
# there is no way to recover them.
if [ -f "$PROJECT_DIR/.env" ]; then
  echo "WARNING: $PROJECT_DIR/.env exists and holds your API keys."
  echo "         Deleting it means you must re-enter them after reinstalling."
fi

echo ""
echo "The following will be removed:"
for item in ai-env termux-ai-cli models .env; do
  [ -e "$PROJECT_DIR/$item" ] && echo "  - $item"
done

echo ""
printf "Continue? [y/N] "
read -r reply
case "$reply" in
  y|Y|yes|YES) ;;
  *) echo "Aborted, nothing was removed."; exit 0 ;;
esac

rm -rf "$PROJECT_DIR/ai-env" "$PROJECT_DIR/termux-ai-cli"
rm -rf "$PROJECT_DIR/models"
rm -f "$PROJECT_DIR/.env"
rm -f "$PROJECT_DIR/ai_cli.py" "$PROJECT_DIR/local_llm.py"

# Remove the project directory only if we emptied it - the user may have
# put their own files in there.
rmdir "$PROJECT_DIR" 2>/dev/null && echo "Removed $PROJECT_DIR (it was empty)." \
  || echo "Kept $PROJECT_DIR - it still contains other files."

echo ""
echo "Done. Termux packages (python, git, cmake, ...) were left in place."
echo "Remove them manually if you no longer need them:"
echo "  pkg uninstall python git cmake clang"
