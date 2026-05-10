#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${MARKER_MODEL_BASE_URL:-https://models.datalab.to}"
CACHE_DIR="${MARKER_MODEL_CACHE_DIR:-/root/AI-reviewer/var/model-cache/datalab/models}"
ARIA2_CONNECTIONS="${MARKER_MODEL_ARIA2_CONNECTIONS:-16}"

download_file() {
  local rel_path="$1"
  local target_dir="$CACHE_DIR/$(dirname "$rel_path")"
  local target_name
  target_name="$(basename "$rel_path")"

  mkdir -p "$target_dir"
  aria2c \
    --continue=true \
    --max-connection-per-server="$ARIA2_CONNECTIONS" \
    --split="$ARIA2_CONNECTIONS" \
    --min-split-size=1M \
    --max-tries=8 \
    --retry-wait=5 \
    --timeout=120 \
    --connect-timeout=30 \
    --summary-interval=30 \
    --allow-overwrite=true \
    --auto-file-renaming=false \
    --dir="$target_dir" \
    --out="$target_name" \
    "$BASE_URL/$rel_path"
}

download_model() {
  local model="$1"
  shift

  echo "==> $model"
  download_file "$model/manifest.json"
  for file in "$@"; do
    download_file "$model/$file"
  done
}

download_model "layout/2025_09_23" \
  ".gitattributes" \
  "README.md" \
  "specials_dict.json" \
  "training_args.bin" \
  "special_tokens_map.json" \
  "vocab_math.json" \
  "specials.json" \
  "tokenizer_config.json" \
  "preprocessor_config.json" \
  "config.json" \
  "processor_config.json" \
  "model.safetensors"

download_model "text_recognition/2025_09_23" \
  ".gitattributes" \
  "README.md" \
  "specials_dict.json" \
  "training_args.bin" \
  "special_tokens_map.json" \
  "vocab_math.json" \
  "specials.json" \
  "tokenizer_config.json" \
  "preprocessor_config.json" \
  "config.json" \
  "processor_config.json" \
  "model.safetensors"

download_model "text_detection/2025_05_07" \
  "model.safetensors" \
  "preprocessor_config.json" \
  ".gitattributes" \
  "README.md" \
  "training_args.bin" \
  "config.json"

download_model "table_recognition/2025_02_18" \
  "model.safetensors" \
  "config.json" \
  "README.md" \
  ".gitattributes" \
  "preprocessor_config.json"

download_model "ocr_error_detection/2025_02_18" \
  "model.safetensors" \
  "tokenizer_config.json" \
  "special_tokens_map.json" \
  "config.json" \
  "tokenizer.json" \
  "README.md" \
  "vocab.txt" \
  ".gitattributes"

echo "marker_models_download_complete: $CACHE_DIR"
