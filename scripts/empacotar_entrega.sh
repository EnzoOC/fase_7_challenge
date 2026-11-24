#!/usr/bin/env bash
# Gera o zip da entrega (código + docs + evidências), sem dependências nem segredos.
# Uso: ./scripts/empacotar_entrega.sh   → ../AgroSmart_Fase7_Entrega.zip
set -euo pipefail
cd "$(dirname "$0")/.."
SAIDA="../AgroSmart_Fase7_Entrega.zip"
rm -f "$SAIDA"
zip -rq "$SAIDA" . \
  -x '.git/*' '.venv/*' '*/node_modules/*' '*/dist/*' '*__pycache__*' \
     '.pytest_cache/*' '.ruff_cache/*' '.coverage' 'coverage.xml' '.env' '*.zip'
echo "Gerado: $(realpath "$SAIDA") ($(du -h "$SAIDA" | cut -f1))"
unzip -l "$SAIDA" | tail -1
