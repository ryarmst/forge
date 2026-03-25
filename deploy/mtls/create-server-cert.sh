#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────
# Generate a server certificate signed by the Forge CA.
# Supports IP addresses and/or domain names as SANs.
#
# Usage:  ./create-server-cert.sh <ip-or-domain> [ca-dir] [output-dir]
#
# Examples:
#   ./create-server-cert.sh 204.168.161.59
#   ./create-server-cert.sh forge.example.com
#   ./create-server-cert.sh 204.168.161.59 ./ca ./server
# ─────────────────────────────────────────────────────────
set -euo pipefail

HOST="${1:?Usage: $0 <ip-or-domain> [ca-dir] [output-dir]}"
CA_DIR="${2:-./ca}"
OUT="${3:-./server}"

if [[ ! -f "$CA_DIR/ca.key" || ! -f "$CA_DIR/ca.crt" ]]; then
  echo "ERROR: CA not found at $CA_DIR/. Run init-ca.sh first."
  exit 1
fi

mkdir -p "$OUT"

# Build SAN entry — detect IP vs hostname
if [[ "$HOST" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  SAN="IP:$HOST"
else
  SAN="DNS:$HOST"
fi

openssl genrsa -out "$OUT/server.key" 2048

openssl req -new -key "$OUT/server.key" -out "$OUT/server.csr" \
  -subj "/O=Forge/CN=$HOST"

openssl x509 -req -days 825 \
  -in "$OUT/server.csr" \
  -CA "$CA_DIR/ca.crt" -CAkey "$CA_DIR/ca.key" -CAcreateserial \
  -out "$OUT/server.crt" \
  -extfile <(printf "subjectAltName=$SAN\nkeyUsage=digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth")

rm -f "$OUT/server.csr"
chmod 600 "$OUT/server.key"
chmod 644 "$OUT/server.crt"

echo ""
echo "Server cert created for $HOST:"
echo "  Key:          $OUT/server.key"
echo "  Certificate:  $OUT/server.crt"
echo "  Valid for:     825 days"
echo "  Signed by:    $CA_DIR/ca.crt"
