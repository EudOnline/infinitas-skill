#!/usr/bin/env bash
# Security audit script for infinitas-skill
# Checks for known vulnerabilities in Python dependencies
#
# Usage:
#   ./scripts/security-audit.sh [--fix] [--json]
#
# Options:
#   --fix    Attempt to auto-fix vulnerabilities (upgrade packages)
#   --json   Output results in JSON format
#
# Exit codes:
#   0  No vulnerabilities found
#   1  Vulnerabilities found
#   2  pip-audit not installed

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

FIX_MODE=false
JSON_MODE=false

for arg in "$@"; do
    case $arg in
        --fix) FIX_MODE=true ;;
        --json) JSON_MODE=true ;;
        *) echo "Unknown option: $arg"; exit 2 ;;
    esac
done

# Check if pip-audit is installed
if ! command -v pip-audit &> /dev/null; then
    if [ -f "$PROJECT_ROOT/.venv/bin/pip-audit" ]; then
        PIP_AUDIT="$PROJECT_ROOT/.venv/bin/pip-audit"
    else
        echo -e "${RED}Error: pip-audit not found${NC}"
        echo "Install with: pip install pip-audit"
        exit 2
    fi
else
    PIP_AUDIT="pip-audit"
fi

echo "=========================================="
echo " Security Audit - infinitas-skill"
echo "=========================================="
echo ""

# Run pip-audit
echo "Checking for known vulnerabilities..."
echo ""

if [ "$JSON_MODE" = true ]; then
    AUDIT_OUTPUT=$($PIP_AUDIT --format json 2>&1) || true
    echo "$AUDIT_OUTPUT"
else
    AUDIT_OUTPUT=$($PIP_AUDIT 2>&1) || true
    echo "$AUDIT_OUTPUT"
fi

# Check exit code
AUDIT_EXIT=$?
if [ $AUDIT_EXIT -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✓ No known vulnerabilities found${NC}"
    exit 0
else
    echo ""
    echo -e "${RED}✗ Vulnerabilities found${NC}"

    if [ "$FIX_MODE" = true ]; then
        echo ""
        echo "Attempting to fix vulnerabilities..."
        $PIP_AUDIT --fix
        FIX_EXIT=$?
        if [ $FIX_EXIT -eq 0 ]; then
            echo -e "${GREEN}✓ Vulnerabilities fixed${NC}"
            echo "Remember to update requirements files and test."
        else
            echo -e "${YELLOW}⚠ Some vulnerabilities could not be auto-fixed${NC}"
            echo "Manual intervention may be required."
        fi
    else
        echo ""
        echo "Run with --fix to attempt automatic remediation."
    fi

    exit 1
fi
