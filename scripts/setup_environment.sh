#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Google Drive Consolidator Setup${NC}"
echo -e "${GREEN}========================================${NC}"

# Check if conda is installed
if ! command -v conda &> /dev/null; then
    echo -e "${RED}❌ Conda is not installed!${NC}"
    echo "Please install Miniconda or Anaconda first:"
    echo "  - Miniconda: https://docs.conda.io/en/latest/miniconda.html"
    echo "  - Anaconda: https://www.anaconda.com/products/distribution"
    exit 1
fi

echo -e "${GREEN}✅ Conda found: $(conda --version)${NC}"

# Create environment from YAML file
echo -e "\n${YELLOW}Creating conda environment 'gdrive-consolidator'...${NC}"
conda env create -f environment.yml

# Activate environment
echo -e "\n${YELLOW}Activating environment...${NC}"
eval "$(conda shell.bash hook)"
conda activate gdrive-consolidator

# Verify installation
echo -e "\n${GREEN}Verifying installation...${NC}"
python -c "import sys; print(f'Python version: {sys.version}')"
python -c "import tqdm; print('✅ tqdm installed')" 2>/dev/null || echo "⚠️  tqdm not installed"
python -c "import rich; print('✅ rich installed')" 2>/dev/null || echo "⚠️  rich not installed"
python -c "import psutil; print('✅ psutil installed')" 2>/dev/null || echo "⚠️  psutil not installed"

echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}Setup Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "To use the environment, run:"
echo -e "${YELLOW}  conda activate gdrive-consolidator${NC}"
echo ""
echo "Then you can run the scripts:"
echo "  1. Test with dry run:"
echo -e "${YELLOW}     python main_enhanced.py${NC}"
echo ""
echo "  2. Execute reconstruction:"
echo -e "${YELLOW}     python main_enhanced.py --execute${NC}"
echo ""
echo "  3. Verify results:"
echo -e "${YELLOW}     python verify_reconstruction.py <source> <dest>${NC}"
