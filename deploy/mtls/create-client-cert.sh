#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────
# Generate a client certificate for mTLS access to Forge.
# Outputs a .p12 file the user imports into their browser.
#
# Usage:  ./create-client-cert.sh <username> [ca-dir] [output-dir]
#
# Examples:
#   ./create-client-cert.sh alice
#   ./create-client-cert.sh bob ./ca ./clients
# ─────────────────────────────────────────────────────────
set -euo pipefail

USERNAME="${1:?Usage: $0 <username> [ca-dir] [output-dir]}"
CA_DIR="${2:-./ca}"
OUT="${3:-./clients}"

if [[ ! -f "$CA_DIR/ca.key" || ! -f "$CA_DIR/ca.crt" ]]; then
  echo "ERROR: CA not found at $CA_DIR/. Run init-ca.sh first."
  exit 1
fi

mkdir -p "$OUT"

KEY="$OUT/${USERNAME}.key"
CRT="$OUT/${USERNAME}.crt"
P12="$OUT/${USERNAME}.p12"

openssl genrsa -out "$KEY" 2048

openssl req -new -key "$KEY" -out "$OUT/${USERNAME}.csr" \
  -subj "/O=Forge/CN=$USERNAME"

openssl x509 -req -days 365 \
  -in "$OUT/${USERNAME}.csr" \
  -CA "$CA_DIR/ca.crt" -CAkey "$CA_DIR/ca.key" -CAcreateserial \
  -out "$CRT" \
  -extfile <(printf "keyUsage=digitalSignature\nextendedKeyUsage=clientAuth")

rm -f "$OUT/${USERNAME}.csr"

echo ""
read -s -p "Set a password for the .p12 file: " P12_PASS
echo ""

openssl pkcs12 -export -out "$P12" \
  -inkey "$KEY" -in "$CRT" -certfile "$CA_DIR/ca.crt" \
  -name "Forge - $USERNAME" \
  -passout "pass:$P12_PASS"

chmod 600 "$KEY" "$P12"
chmod 644 "$CRT"

echo ""
echo "Client cert created for '$USERNAME':"
echo "  Key:          $KEY"
echo "  Certificate:  $CRT     (valid 1 year)"
echo "  PKCS12:       $P12     (import this into browser)"
echo ""
echo "User setup:"
echo "  1. Send them:  $P12  +  $CA_DIR/ca.crt"
echo "  2. They import ca.crt as a trusted CA"
echo "  3. They import ${USERNAME}.p12 as a personal certificate"
