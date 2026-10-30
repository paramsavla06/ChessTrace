#!/usr/bin/env bash
set -e

echo "==> Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "==> Checking build environment for Stockfish..."
if command -v make >/dev/null 2>&1 && command -v g++ >/dev/null 2>&1; then
    if [ ! -f "stockfish_bin" ]; then
        echo "==> Compiling lightweight Stockfish 11 from source (free-tier safe, no NNUE OOM)..."
        rm -rf stockfish_src
        if git clone --depth 1 -b sf_11 https://github.com/official-stockfish/Stockfish.git stockfish_src; then
            cd stockfish_src/src
            make -j2 build ARCH=x86-64 || true
            cd ../..
            if [ -f "stockfish_src/src/stockfish" ]; then
                mv stockfish_src/src/stockfish stockfish_bin
                chmod +x stockfish_bin
                echo "==> Stockfish binary installed at ./stockfish_bin"
            fi
            rm -rf stockfish_src
        else
            echo "==> Git clone failed, will use ML heuristic engine."
        fi
    else
        echo "==> Stockfish binary already present at ./stockfish_bin"
    fi
else
    echo "==> No make/g++ toolchain detected. ChessTrace will run in high-performance ML heuristic mode (free-tier optimized)."
fi

echo "==> Build complete!"
