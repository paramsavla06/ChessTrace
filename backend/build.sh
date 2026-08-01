#!/usr/bin/env bash
set -e

echo "==> Installing Python dependencies..."
pip install -r requirements.txt

echo "==> Downloading Stockfish Linux binary..."
curl -L -o stockfish.tar https://github.com/official-stockfish/Stockfish/releases/latest/download/stockfish-ubuntu-x86-64.tar
tar -xf stockfish.tar
mv stockfish/stockfish-ubuntu-x86-64 stockfish_bin
chmod +x stockfish_bin
rm -rf stockfish stockfish.tar

echo "==> Stockfish installed at ./stockfish_bin"
echo "==> Build complete!"
