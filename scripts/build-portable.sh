#!/usr/bin/env bash
# Build portable binaries. Wine/pyinstaller steps use timeouts and log files (never pipe Wine stdout).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p portable
OUT_LOG="${TMPDIR:-/tmp}/xml2cf-portable-build.log"

echo "[xml2cf] installing package…"
pip install -e ".[dev]" -q

echo "[xml2cf] linux entrypoint…"
cat > portable/xml2cf <<'EOF'
#!/usr/bin/env bash
ROOT="$(cd "$(dirname "$0")" && pwd)"
export PYTHONPATH="${ROOT}/../src:${PYTHONPATH:-}"
exec python3 -m xml2cf "$@"
EOF
chmod +x portable/xml2cf

# Sync fixtures
rm -rf portable/fixtures
mkdir -p portable/fixtures
cp -a tests/fixtures/cf-empty-infobase portable/fixtures/
cp -a tests/fixtures/cf-small portable/fixtures/

echo "[xml2cf] trying PyInstaller (linux one-file)…"
if command -v pyinstaller >/dev/null 2>&1 || pip install pyinstaller -q; then
  timeout 180 pyinstaller \
    --onefile \
    --name xml2cf-linux \
    --paths src \
    --add-data "src/xml2cf/data:xml2cf/data" \
    --hidden-import v8unpack \
    -y src/xml2cf/__main__.py >>"$OUT_LOG" 2>&1 \
    && cp dist/xml2cf-linux portable/xml2cf-bin \
    && echo "[xml2cf] linux binary → portable/xml2cf-bin" \
    || echo "[xml2cf] linux pyinstaller skipped/failed (see $OUT_LOG)"
fi

echo "[xml2cf] Windows exe via Wine (optional, timeout 300s)…"
if command -v wine >/dev/null 2>&1; then
  timeout 300 bash -c '
    set -e
    wine python -m pip install pyinstaller v8unpack -q >>"'"$OUT_LOG"'" 2>&1 || true
    wine pyinstaller --onefile --name xml2cf --paths src \
      --add-data "src/xml2cf/data;xml2cf/data" \
      --hidden-import v8unpack -y src/xml2cf/__main__.py >>"'"$OUT_LOG"'" 2>&1 || true
  ' || echo "[xml2cf] Wine build timed out/failed (see $OUT_LOG)"
  if [[ -f dist/xml2cf.exe ]]; then
    cp dist/xml2cf.exe portable/xml2cf.exe
    echo "[xml2cf] windows exe → portable/xml2cf.exe"
  fi
else
  echo "[xml2cf] wine not available; portable/xml2cf.exe not built"
fi

echo "[xml2cf] done. log: $OUT_LOG"
