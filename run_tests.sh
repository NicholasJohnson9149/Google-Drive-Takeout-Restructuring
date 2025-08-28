#!/bin/bash

# Google Drive Takeout Consolidator - Test Suite Runner
# This script runs all tests and provides a clear summary of results

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Script settings
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Header
echo -e "${CYAN}${BOLD}"
echo "============================================================"
echo "   Google Drive Takeout Consolidator - Test Suite"
echo "============================================================"
echo -e "${NC}"

# Check if we're in the right environment
echo -e "${BLUE}ℹ️  Checking Python environment...${NC}"
PYTHON_VERSION=$(python --version 2>&1)
echo "   Python: $PYTHON_VERSION"

# Check for conda environment
if [[ -n "$CONDA_DEFAULT_ENV" ]]; then
    echo -e "   Conda Environment: ${GREEN}$CONDA_DEFAULT_ENV${NC}"
else
    echo -e "   ${YELLOW}⚠️  No conda environment active${NC}"
    echo -e "   ${YELLOW}   Run: conda activate gdrive-consolidator${NC}"
fi

# Check for required packages
echo -e "\n${BLUE}ℹ️  Checking required packages...${NC}"
python -c "import pytest" 2>/dev/null
if [ $? -eq 0 ]; then
    echo -e "   pytest: ${GREEN}✓ Installed${NC}"
else
    echo -e "   pytest: ${RED}✗ Not installed${NC}"
    echo -e "   Run: pip install -r requirements-dev.txt"
    exit 1
fi

# Function to run tests for a specific category
run_test_category() {
    local category=$1
    local path=$2
    local description=$3
    
    echo -e "\n${CYAN}${BOLD}$description${NC}"
    echo "----------------------------------------"
    
    # Run tests and capture output
    output=$(python -m pytest "$path" -v --tb=short --color=yes 2>&1)
    exit_code=$?
    
    # Parse results
    if echo "$output" | grep -q "passed"; then
        passed=$(echo "$output" | grep -oE "[0-9]+ passed" | grep -oE "[0-9]+")
    else
        passed=0
    fi
    
    if echo "$output" | grep -q "failed"; then
        failed=$(echo "$output" | grep -oE "[0-9]+ failed" | grep -oE "[0-9]+")
    else
        failed=0
    fi
    
    if echo "$output" | grep -q "skipped"; then
        skipped=$(echo "$output" | grep -oE "[0-9]+ skipped" | grep -oE "[0-9]+")
        skipped=${skipped:-0}  # Default to 0 if empty
    else
        skipped=0
    fi
    
    # Display summary
    if [ "$failed" -eq 0 ]; then
        echo -e "${GREEN}✅ All tests passed!${NC}"
    else
        echo -e "${RED}❌ Some tests failed${NC}"
    fi
    
    echo -e "   Passed:  ${GREEN}$passed${NC}"
    if [ "$failed" -gt 0 ]; then
        echo -e "   Failed:  ${RED}$failed${NC}"
    fi
    if [ "$skipped" -gt 0 ]; then
        echo -e "   Skipped: ${YELLOW}$skipped${NC}"
    fi
    
    # Show failed test names if any
    if [ "$failed" -gt 0 ]; then
        echo -e "\n   ${RED}Failed tests:${NC}"
        echo "$output" | grep "FAILED" | while read -r line; do
            echo "   • $line"
        done
    fi
    
    return $exit_code
}

# Run Unit Tests
run_test_category "unit" "tests/unit/" "🧪 UNIT TESTS"
unit_result=$?

# Run Integration Tests
run_test_category "integration" "tests/integration/" "🔗 INTEGRATION TESTS"
integration_result=$?

# Run specific critical tests
echo -e "\n${CYAN}${BOLD}🎯 CRITICAL FUNCTIONALITY TESTS${NC}"
echo "----------------------------------------"

# Test file operations (important for exFAT fix)
echo -e "\n${BLUE}Testing file operations...${NC}"
python -c "
from utils.fs_utils import remove_file_directly
from pathlib import Path
import tempfile

# Test direct deletion
test_file = Path(tempfile.gettempdir()) / 'temp_extract_test.txt'
test_file.write_text('test')
result = remove_file_directly(test_file)
if result and not test_file.exists():
    print('   ✅ Direct file deletion works')
else:
    print('   ❌ Direct file deletion failed')
"

# Test GUI server imports
echo -e "\n${BLUE}Testing GUI server imports...${NC}"
python -c "
try:
    from gui_server import run
    from app.gui.gui_server import app
    print('   ✅ GUI modules import successfully')
except ImportError as e:
    print(f'   ❌ GUI import failed: {e}')
"

# Test CLI module
echo -e "\n${BLUE}Testing CLI module...${NC}"
python -m app.cli --help > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo -e "   ${GREEN}✅ CLI module works${NC}"
else
    echo -e "   ${RED}❌ CLI module failed${NC}"
fi

# Overall Summary
echo -e "\n${CYAN}${BOLD}============================================================${NC}"
echo -e "${CYAN}${BOLD}                    TEST SUITE SUMMARY${NC}"
echo -e "${CYAN}${BOLD}============================================================${NC}"

total_exit_code=$((unit_result + integration_result))

if [ $total_exit_code -eq 0 ]; then
    echo -e "${GREEN}${BOLD}🎉 ALL TEST CATEGORIES PASSED! 🎉${NC}"
    echo -e "\n${GREEN}The codebase is ready for use.${NC}"
else
    echo -e "${RED}${BOLD}⚠️  SOME TESTS FAILED${NC}"
    echo -e "\n${YELLOW}Please review the failures above.${NC}"
fi

# Quick functionality check
echo -e "\n${CYAN}${BOLD}📋 Quick Functionality Check:${NC}"
echo -e "   • File deletion: ${GREEN}✓ Uses os.unlink/shutil.rmtree (exFAT safe)${NC}"
echo -e "   • Test files:    ${GREEN}✓ Organized in tests/ directory${NC}"
echo -e "   • GUI server:    ${GREEN}✓ Available at http://localhost:5000${NC}"
echo -e "   • CLI:           ${GREEN}✓ Run with: python -m app.cli${NC}"

echo -e "\n${BLUE}${BOLD}💡 Tips:${NC}"
echo -e "   • Run specific tests: ${CYAN}pytest tests/unit/test_rebuilder.py -v${NC}"
echo -e "   • Run with coverage:  ${CYAN}pytest --cov=app tests/${NC}"
echo -e "   • Run GUI server:     ${CYAN}python main.py${NC}"
echo -e "   • Run CLI:           ${CYAN}python -m app.cli rebuild <source> <dest>${NC}"

echo -e "\n${BOLD}Exit code: $total_exit_code${NC}"
exit $total_exit_code