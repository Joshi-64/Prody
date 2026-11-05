#!/bin/sh
# Re-runnable: copy Design's bloom parts into static (re-run after bloom_art/gen.py changes). Same ids/pivots expected.
set -e; SRC=${1:-/workspace/prody_shots/bloom_art}; DST=$(dirname "$0")/../static/shop/bloom
cp "$SRC/bloom_parts.svg" "$DST/default_grow.svg"; cp "$SRC/bloom_parts_dark.svg" "$DST/default_grow_dark.svg"
echo "copied bloom parts -> $DST/default_grow{,_dark}.svg"
