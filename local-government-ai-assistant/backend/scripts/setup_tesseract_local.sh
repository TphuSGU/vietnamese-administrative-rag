#!/usr/bin/env bash
# Cai Tesseract + vie.traineddata vao backend/.tesseract, khong can sudo.
# Dung: bash scripts/setup_tesseract_local.sh
# Sau do: export PATH="$PWD/.tesseract/bin:$PATH"
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="${TESSERACT_DIR:-$ROOT/.tesseract}"
DEBS="$TARGET/debs"
PREFIX="$TARGET/root"

mkdir -p "$DEBS" "$PREFIX" "$TARGET/bin"

if ! command -v apt-get >/dev/null 2>&1 || ! command -v dpkg-deb >/dev/null 2>&1; then
  echo "Can apt-get va dpkg-deb (Ubuntu/Debian)." >&2
  exit 1
fi

cd "$DEBS"
apt-get download tesseract-ocr tesseract-ocr-vie libtesseract5 liblept5

for deb in ./*.deb; do
  dpkg-deb -x "$deb" "$PREFIX"
done

cat > "$TARGET/bin/tesseract" <<WRAPPER
#!/usr/bin/env bash
export LD_LIBRARY_PATH="$PREFIX/usr/lib/x86_64-linux-gnu\${LD_LIBRARY_PATH:+:\$LD_LIBRARY_PATH}"
export TESSDATA_PREFIX="$PREFIX/usr/share/tesseract-ocr/5/tessdata"
exec "$PREFIX/usr/bin/tesseract" "\$@"
WRAPPER
chmod +x "$TARGET/bin/tesseract"

"$TARGET/bin/tesseract" --version | head -1
"$TARGET/bin/tesseract" --list-langs

echo
echo "Da cai vao: $TARGET"
echo "Chay truoc khi ingest:"
echo "  export PATH=\"$TARGET/bin:\$PATH\""
