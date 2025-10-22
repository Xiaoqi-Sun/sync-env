# Environment Synchronization

Synchronize python virtual environment and conda environment

1. **Automated scanning** of your codebase to find all imported packages
2. **Version comparison** between conda and venv
3. **Detailed report** showing mismatches and missing packages
4. **Auto-generated files**:
   - `requirements_from_conda.txt` - Pinned versions from your conda env
   - `sync_venv.sh` - Script to fix your venv with correct installation order

## Quick Start

### Interactive Mode

```bash

# Option 1: interactive
# show available conda environments and auto-detect venv
./quick_sync.sh

# Option 2: directly specify conda environment and venv path
./quick_sync.sh my_conda_env ./venv
```

## Outputs

After running, you'll see a report with:

###  **No Issues Found**
Your environments are in sync!

###  **Version Mismatches**
Example:
```
Package          Conda (Reference)    Venv (Current)
----------------------------------------------------
torch            2.0.1                2.1.0
numpy            1.24.3               1.24.4
```
→ These will be fixed by the sync script

###  **Missing in Venv**
Packages used in your code but not installed in venv
→ Will be installed by the sync script

###  **Not in Conda**
Packages imported but not found in conda
→ May need manual review (could be pip-installed or mapping issue)

## Running the Sync

After reviewing the report:

```bash
./sync_venv.sh
```

## Key Features

### UV Support
- Auto-detects [uv](https://github.com/astral-sh/uv)
- Falls back to pip if uv not available
- Manual override: `--package-manager {auto|uv|pip}`

### Smart Scanning
- Automatically finds all Python files in `scripts/` and `src/tcr/`
- Uses AST parsing to extract imports
- Filters out standard library modules
- Maps import names to package names (e.g., `sklearn` → `scikit-learn`)


### Conda as Source of Truth
Your working conda environment determines all versions, ensuring reproducibility.

## Files Created

| File | Purpose |
|------|---------|
| `sync_environments.py` | Main comparison tool |
| `quick_sync.sh` | Interactive wrapper for easy use |
| `requirements_from_conda.txt` | Generated: pinned versions |
| `sync_venv.sh` | Generated: sync script |
| `ENV_SYNC_README.md` | Detailed documentation |
| `EXAMPLE_COMMANDS.txt` | Command examples |
| `START_HERE.md` | This file |

## Typical Workflow

```bash
# 1. Run comparison
./quick_sync.sh

# 2. Review report

# 3. Sync venv
./sync_venv.sh

# 4. Verify (optional)
python sync_environments.py \
    --conda-env my_env \
    --venv-path ./venv \
    --no-generate-files
```

## Troubleshooting

### "Could not find Python executable in venv"
→ Check that `--venv-path` points to the venv root (contains `bin/` or `Scripts/`)

### "Conda environment not found"
→ Run `conda env list` to see available environments

### Package still mismatched after sync
→ Make sure you're using the correct venv: `which python` or `where python`

### Package shows as "not in conda"
1. It might be pip-installed in conda: `conda list | grep <package>`
2. Check if import name differs from package name
3. Add mapping to `IMPORT_TO_PACKAGE` in `sync_environments.py`

## Examples

### Basic Project Setup
```bash
./quick_sync.sh tcr ./venv
```

### Scan Additional Directories
```bash
python sync_environments.py \
    --conda-env tcr \
    --venv-path ./venv \
    --scan-paths scripts src/tcr notebooks
```

### Report Only (Don't Generate Files)
```bash
python sync_environments.py \
    --conda-env tcr \
    --venv-path ./venv \
    --no-generate-files
```

### Custom Requirements File
```bash
python sync_environments.py \
    --conda-env tcr \
    --venv-path ./venv \
    --output-requirements requirements.txt
```

## Next Steps

1. **First Time**: Run `./quick_sync.sh` to see your current status
2. **Review**: Check the report for mismatches
3. **Sync**: Run `./sync_venv.sh` if needed
4. **Commit**: Add `requirements_from_conda.txt` to version control
5. **Repeat**: Run periodically when you update conda packages

## Pro Tips

1. **Keep conda as your development environment**: Make all package changes there first
2. **Use venv for deployment/CI**: Sync it from conda when needed
3. **Version control the requirements**: Commit `requirements_from_conda.txt`
4. **Regular checks**: Run the sync check after installing new packages
5. **CI/CD integration**: Use generated requirements in your CI pipeline