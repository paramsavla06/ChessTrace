#!/usr/bin/env bash
set -e

echo "==> Installing Python dependencies..."
pip install -r requirements.txt

echo "==> Cloning and compiling Stockfish from source (this guarantees CPU compatibility)..."
git clone --depth 1 -b sf_16.1 https://github.com/official-stockfish/Stockfish.git stockfish_src
cd stockfish_src/src
make -j2 build ARCH=x86-64
cd ../..
mv stockfish_src/src/stockfish stockfish_bin
chmod +x stockfish_bin
rm -rf stockfish_src

echo "==> Stockfish installed at ./stockfish_bin"
echo "==> Build complete!"
