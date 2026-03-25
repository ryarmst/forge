#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────
# Generate a private Certificate Authority for Forge mTLS.
# Run once. Outputs ca.key and ca.crt in the current dir.
#
# Usage:  ./init-ca.sh [output-dir]
# ─────────────────────────────────────────────────────────
set -euo pipefail

OUT="${1:-./ca}"
mkdir -p "$OUT"

if [[ -f "$OUT/ca.key" ]]; then
  echo "CA already exists at $OUT/ca.key — delete it first to regenerate."
  exit 1
fi

openssl genrsa -out "$OUT/ca.key" 4096

openssl req -new -x509 -days 3650 -key "$OUT/ca.key" -out "$OUT/ca.crt" \
  -subj "/O=Forge/CN=Forge Internal CA"

chmod 600 "$OUT/ca.key"
chmod 644 "$OUT/ca.crt"

echo ""
echo "CA created:"
echo "  Private key:   $OUT/ca.key  (keep this secret)"
echo "  Certificate:   $OUT/ca.crt  (distribute to users to trust)"
echo "  Valid for:      10 years"
