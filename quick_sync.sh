#!/bin/bash
# Quick start script for environment synchronization
# This is a helper wrapper around sync_environments.py

set -e

echo "=========================================="
echo "Environment Synchronization - Quick Start"
echo "=========================================="
echo ""

# Check if sync_environments.py exists
if [ ! -f "sync_environments.py" ]; then
    echo "Error: sync_environments.py not found in current directory"
    echo "Please run this script from the project root directory"
    exit 1
fi

# Function to list conda environments
list_conda_envs() {
    echo "Available conda environments:"
    conda env list | grep -v "^#" | awk '{print "  - " $1}'
}

# Function to detect common venv paths
detect_venv() {
    local common_names=("venv" ".venv" "env" ".env" "virtualenv")
    for name in "${common_names[@]}"; do
        if [ -d "$name" ] && [ -f "$name/bin/python" -o -f "$name/Scripts/python.exe" ]; then
            echo "$name"
            return 0
        fi
    done
    return 1
}

# Get conda environment name
if [ -z "$1" ]; then
    echo "Step 1: Select conda environment"
    echo ""
    list_conda_envs
    echo ""
    read -p "Enter conda environment name: " CONDA_ENV
else
    CONDA_ENV="$1"
fi

# Verify conda env exists
if ! conda env list | grep -q "^${CONDA_ENV} "; then
    echo "Error: Conda environment '$CONDA_ENV' not found"
    echo ""
    list_conda_envs
    exit 1
fi

echo "✓ Using conda environment: $CONDA_ENV"
echo ""

# Get venv path
if [ -z "$2" ]; then
    echo "Step 2: Select Python venv path"
    echo ""

    # Try to auto-detect venv
    DETECTED_VENV=$(detect_venv)
    if [ $? -eq 0 ]; then
        echo "Auto-detected venv at: $DETECTED_VENV"
        read -p "Use this path? [Y/n]: " USE_DETECTED
        if [[ "$USE_DETECTED" =~ ^[Yy]?$ ]]; then
            VENV_PATH="$DETECTED_VENV"
        else
            read -p "Enter venv path: " VENV_PATH
        fi
    else
        echo "No venv auto-detected in common locations (venv, .venv, env, .env)"
        read -p "Enter venv path: " VENV_PATH
    fi
else
    VENV_PATH="$2"
fi

# Verify venv exists
if [ ! -d "$VENV_PATH" ]; then
    echo "Error: Venv path '$VENV_PATH' does not exist"
    exit 1
fi

# Check for python executable
if [ ! -f "$VENV_PATH/bin/python" ] && [ ! -f "$VENV_PATH/Scripts/python.exe" ]; then
    echo "Error: No Python executable found in '$VENV_PATH'"
    echo "This doesn't appear to be a valid Python venv"
    exit 1
fi

echo "✓ Using venv path: $VENV_PATH"
echo ""

# Run the sync script
echo "=========================================="
echo "Running environment comparison..."
echo "=========================================="
echo ""

# options to add scan paths and local packages
python sync_environments.py \
    --conda-env "$CONDA_ENV" \
    --venv-path "$VENV_PATH" \
    --package-manager auto

# Check if files were generated
if [ -f "sync_venv.sh" ]; then
    echo ""
    echo "=========================================="
    echo "Next Steps:"
    echo "=========================================="
    echo "1. Review the report above"
    echo "2. Check the generated files:"
    echo "   - requirements_from_conda.txt (pinned versions)"
    echo "   - sync_venv.sh (sync script)"
    echo ""
    echo "3. To synchronize your venv, run:"
    echo "   ./sync_venv.sh"
    echo ""
    echo "4. Or manually install with:"
    echo "   $VENV_PATH/bin/pip install -r requirements_from_conda.txt"
    echo ""

    read -p "Do you want to run the sync script now? [y/N]: " RUN_SYNC
    if [[ "$RUN_SYNC" =~ ^[Yy]$ ]]; then
        echo ""
        echo "Running sync script..."
        chmod +x sync_venv.sh
        ./sync_venv.sh
        echo ""
        echo "✓ Synchronization complete!"
    fi
else
    echo ""
    echo "Note: No sync script generated (packages already synchronized?)"
fi

echo ""
echo "For more options, see: README.md"
