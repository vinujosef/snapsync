#!/usr/bin/env bash
set -euo pipefail

COMMAND_NAME="${COMMAND_NAME:-snapsync}"
INSTALL_DIR="${INSTALL_DIR:-/usr/local/bin}"
SKIP_DEPS="${SKIP_DEPS:-false}"

if [[ "${1:-}" == "--user" ]]; then
  INSTALL_DIR="${HOME}/.local/bin"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
MAIN_FILE="${PROJECT_ROOT}/src/snapsync/main.py"
VENV_PYTHON="${PROJECT_ROOT}/.venv/bin/python"
PYTHON_BIN="python3"
TARGET="${INSTALL_DIR}/${COMMAND_NAME}"

if [[ ! -f "${MAIN_FILE}" ]]; then
  echo "Could not find SnapSync main file at: ${MAIN_FILE}" >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required but was not found on PATH." >&2
  exit 1
fi

if [[ ! -x "${VENV_PYTHON}" ]]; then
  echo "Creating virtual environment at ${PROJECT_ROOT}/.venv"
  python3 -m venv "${PROJECT_ROOT}/.venv"
fi

if [[ "${SKIP_DEPS}" != "true" && -f "${PROJECT_ROOT}/requirements.txt" ]]; then
  echo "Installing Python requirements"
  "${VENV_PYTHON}" -m pip install -r "${PROJECT_ROOT}/requirements.txt"
fi

if [[ -x "${VENV_PYTHON}" ]]; then
  PYTHON_BIN="${VENV_PYTHON}"
fi

mkdir -p "${INSTALL_DIR}"

if [[ ! -w "${INSTALL_DIR}" ]]; then
  echo "${INSTALL_DIR} is not writable."
  echo "Re-run with sudo:"
  echo "  sudo ${BASH_SOURCE[0]}"
  echo ""
  echo "Or install for only your user:"
  echo "  ${BASH_SOURCE[0]} --user"
  exit 1
fi

cat > "${TARGET}" <<SH
#!/usr/bin/env bash
exec "${PYTHON_BIN}" "${MAIN_FILE}" "\$@"
SH

chmod +x "${TARGET}"

echo "Installed ${COMMAND_NAME} -> ${TARGET}"
echo "Python: ${PYTHON_BIN}"
echo ""
echo "Try it from any media folder:"
echo "  cd \"/path/to/source/folder\""
echo "  ${COMMAND_NAME}"

if [[ ":${PATH}:" != *":${INSTALL_DIR}:"* ]]; then
  echo ""
  echo "Note: ${INSTALL_DIR} is not currently on PATH."
  echo "Add this to your shell config if needed:"
  echo "  export PATH=\"${INSTALL_DIR}:\$PATH\""
fi
