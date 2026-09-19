#!/usr/bin/env bash
# 离线契约验证；不会启动、停止或修改 Docker / Redis / Milvus。
set -euo pipefail
cd "$(dirname "$0")/.."
verification_dir=$(mktemp -d "${TMPDIR:-/tmp}/tag-semantic-verify.XXXXXX")
trap 'rm -rf "$verification_dir"' EXIT
mvn test -pl ruoyi-taglibrary -am "-Dsemantic.contract.output=$verification_dir/java-snapshot.jsonl"
TAG_JAVA_CONTRACT="$verification_dir/java-snapshot.jsonl" ai-runtime/.venv/bin/python -m pytest ai-runtime/tag_semantic/tests -q --junitxml="$verification_dir/python.xml"
if [[ "${VERIFY_UI:-false}" == true ]]; then
  (cd ruoyi-ui && npm run build:prod)
fi
