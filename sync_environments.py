import argparse
import ast
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional


# Mapping from import names to package names (for cases where they differ)
IMPORT_TO_PACKAGE = {
    "sklearn": "scikit-learn",
    "cv2": "opencv-python",
    "PIL": "Pillow",
    "yaml": "pyyaml",
    "bs4": "beautifulsoup4",
    "dotenv": "python-dotenv",
    "lightning": "pytorch-lightning",
}


class PackageExtractor(ast.NodeVisitor):
    """AST visitor to extract imported package names from Python files."""

    def __init__(self):
        self.imports: Set[str] = set()

    def visit_Import(self, node):
        """Extract package names from 'import x' statements."""
        for alias in node.names:
            # Get the top-level package name
            package = alias.name.split(".")[0]
            self.imports.add(package)
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        """Extract package names from 'from x import y' statements."""
        if node.module:
            # Get the top-level package name
            package = node.module.split(".")[0]
            self.imports.add(package)
        self.generic_visit(node)


def extract_imports_from_file(file_path: Path) -> Set[str]:
    """Extract all imported packages from a Python file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=str(file_path))

        extractor = PackageExtractor()
        extractor.visit(tree)
        return extractor.imports
    except Exception as e:
        print(f"Warning: Could not parse {file_path}: {e}", file=sys.stderr)
        return set()


def scan_codebase(paths: List[Path]) -> Set[str]:
    """Scan Python files in given paths to extract all imported packages."""
    all_imports = set()

    for base_path in paths:
        if not base_path.exists():
            print(f"Warning: Path does not exist: {base_path}", file=sys.stderr)
            continue

        # Find all Python files
        if base_path.is_file():
            python_files = [base_path]
        else:
            python_files = list(base_path.rglob("*.py"))

        print(f"Scanning {len(python_files)} Python files in {base_path}...")

        for py_file in python_files:
            imports = extract_imports_from_file(py_file)
            all_imports.update(imports)

    return all_imports


def filter_stdlib_and_local(imports: Set[str], local_packages: Set[str]) -> Set[str]:
    """Filter out standard library and local packages, keeping only external ones."""
    # Common stdlib modules (not exhaustive, but covers most cases)
    stdlib_modules = {
        "abc",
        "argparse",
        "ast",
        "asyncio",
        "base64",
        "collections",
        "contextlib",
        "copy",
        "csv",
        "datetime",
        "decimal",
        "functools",
        "glob",
        "hashlib",
        "html",
        "io",
        "itertools",
        "json",
        "logging",
        "math",
        "multiprocessing",
        "os",
        "pathlib",
        "pickle",
        "re",
        "signal",
        "statistics",
        "string",
        "subprocess",
        "sys",
        "tempfile",
        "threading",
        "time",
        "typing",
        "unittest",
        "urllib",
        "warnings",
        "weakref",
        "xml",
        "__future__",
        "dataclasses",
        "enum",
    }

    return {
        imp
        for imp in imports
        if imp not in stdlib_modules and imp not in local_packages
    }


def normalize_package_name(import_name: str) -> str:
    """Convert import name to actual package name."""
    return IMPORT_TO_PACKAGE.get(import_name, import_name)


def get_conda_packages(conda_env: str) -> Dict[str, str]:
    """Get package versions from conda environment using the actual Python interpreter."""
    print(f"\nQuerying conda environment '{conda_env}'...")

    try:
        # Use the actual Python from the conda env to get accurate package versions
        # This is more reliable than 'conda list' which can be stale or miss pip-installed packages
        result = subprocess.run(
            [
                "conda",
                "run",
                "-n",
                conda_env,
                "python",
                "-m",
                "pip",
                "list",
                "--format=json",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        packages = json.loads(result.stdout)
        return {pkg["name"].lower(): pkg["version"] for pkg in packages}

    except subprocess.CalledProcessError as e:
        print(
            f"Error: Could not query conda environment '{conda_env}'", file=sys.stderr
        )
        print(f"Error details: {e.stderr}", file=sys.stderr)
        print(
            "\nHint: Make sure the conda environment has pip installed:",
            file=sys.stderr,
        )
        print(f"  conda install -n {conda_env} pip", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Could not parse pip output from conda env", file=sys.stderr)
        sys.exit(1)


def detect_package_manager(prefer: str = "auto") -> str:
    """
    Detect which package manager to use (uv or pip).

    Args:
        prefer: 'auto', 'uv', or 'pip'

    Returns:
        'uv' or 'pip'
    """
    if prefer == "pip":
        return "pip"

    if prefer == "uv":
        # Verify uv is available
        try:
            subprocess.run(["uv", "--version"], capture_output=True, check=True)
            return "uv"
        except (subprocess.CalledProcessError, FileNotFoundError):
            print(
                "Warning: uv requested but not found, falling back to pip",
                file=sys.stderr,
            )
            return "pip"

    # Auto-detect: try uv first
    try:
        subprocess.run(["uv", "--version"], capture_output=True, check=True)
        return "uv"
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "pip"


def get_venv_packages(venv_path: Path, package_manager: str = "auto") -> Dict[str, str]:
    """Get package versions from Python venv using uv or pip."""
    print(f"\nQuerying venv at '{venv_path}'...")

    # Detect package manager
    pm = detect_package_manager(package_manager)
    print(f"Using package manager: {pm}")

    # Find the python executable in the venv
    if sys.platform == "win32":
        python_exe = venv_path / "Scripts" / "python.exe"
    else:
        python_exe = venv_path / "bin" / "python"

    if not python_exe.exists():
        print(
            f"Error: Could not find Python executable in venv at {venv_path}",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        if pm == "uv":
            # Use uv pip list (much faster!)
            result = subprocess.run(
                ["uv", "pip", "list", "--format=json"],
                capture_output=True,
                text=True,
                check=True,
                env={**os.environ, "VIRTUAL_ENV": str(venv_path.absolute())},
            )
        else:
            # Use pip list
            result = subprocess.run(
                [str(python_exe), "-m", "pip", "list", "--format=json"],
                capture_output=True,
                text=True,
                check=True,
            )

        packages = json.loads(result.stdout)
        return {pkg["name"].lower(): pkg["version"] for pkg in packages}

    except subprocess.CalledProcessError as e:
        print(f"Error: Could not query venv packages with {pm}", file=sys.stderr)
        print(f"Error details: {e.stderr}", file=sys.stderr)

        # If uv failed, suggest trying pip
        if pm == "uv":
            print("\nHint: Try running with --package-manager pip", file=sys.stderr)

        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Could not parse {pm} output", file=sys.stderr)
        sys.exit(1)


def find_package_in_list(
    package: str, package_dict: Dict[str, str]
) -> Optional[Tuple[str, str]]:
    """Find a package in the package dictionary, handling case and naming variations."""
    # Direct match
    if package in package_dict:
        return (package, package_dict[package])

    # Case-insensitive match
    package_lower = package.lower()
    if package_lower in package_dict:
        return (package_lower, package_dict[package_lower])

    # Try with underscores instead of hyphens
    package_underscore = package.replace("-", "_")
    if package_underscore in package_dict:
        return (package_underscore, package_dict[package_underscore])

    package_underscore_lower = package_underscore.lower()
    if package_underscore_lower in package_dict:
        return (package_underscore_lower, package_dict[package_underscore_lower])

    # Try with hyphens instead of underscores
    package_hyphen = package.replace("_", "-")
    if package_hyphen in package_dict:
        return (package_hyphen, package_dict[package_hyphen])

    package_hyphen_lower = package_hyphen.lower()
    if package_hyphen_lower in package_dict:
        return (package_hyphen_lower, package_dict[package_hyphen_lower])

    return None


def compare_versions(
    required_packages: Set[str],
    conda_packages: Dict[str, str],
    venv_packages: Dict[str, str],
) -> Tuple[Dict[str, Tuple[str, str]], Set[str], Set[str]]:
    """
    Compare package versions between conda and venv.

    Returns:
        - mismatches: {package: (conda_version, venv_version)}
        - missing_in_venv: packages in conda but not in venv
        - not_in_conda: packages used but not in conda
    """
    mismatches = {}
    missing_in_venv = set()
    not_in_conda = set()

    for package in required_packages:
        # Normalize package name
        package_name = normalize_package_name(package)

        # Find in conda
        conda_result = find_package_in_list(package_name, conda_packages)

        if conda_result is None:
            not_in_conda.add(package_name)
            continue

        conda_name, conda_version = conda_result

        # Find in venv
        venv_result = find_package_in_list(package_name, venv_packages)

        if venv_result is None:
            missing_in_venv.add(package_name)
            continue

        venv_name, venv_version = venv_result

        # Compare versions
        if conda_version != venv_version:
            mismatches[package_name] = (conda_version, venv_version)

    return mismatches, missing_in_venv, not_in_conda


def print_report(
    mismatches: Dict[str, Tuple[str, str]],
    missing_in_venv: Set[str],
    not_in_conda: Set[str],
    conda_packages: Dict[str, str],
    venv_packages: Dict[str, str],
):
    """Print a detailed comparison report."""
    print("\n" + "=" * 80)
    print("ENVIRONMENT SYNCHRONIZATION REPORT")
    print("=" * 80)

    if mismatches:
        print(f"\n❌ VERSION MISMATCHES ({len(mismatches)} packages):")
        print("-" * 80)
        print(f"{'Package':<30} {'Conda (Reference)':<20} {'Venv (Current)':<20}")
        print("-" * 80)
        for package, (conda_ver, venv_ver) in sorted(mismatches.items()):
            print(f"{package:<30} {conda_ver:<20} {venv_ver:<20}")
    else:
        print("\n✅ No version mismatches found!")

    if missing_in_venv:
        print(f"\n⚠️  MISSING IN VENV ({len(missing_in_venv)} packages):")
        print("-" * 80)
        for package in sorted(missing_in_venv):
            # Find the version in conda
            conda_result = find_package_in_list(package, conda_packages)
            version = conda_result[1] if conda_result else "unknown"
            print(f"  - {package:<30} (conda version: {version})")

    if not_in_conda:
        print(f"\n⚠️  NOT IN CONDA ENV ({len(not_in_conda)} packages):")
        print("-" * 80)
        print(
            "These packages are imported in the code but not found in conda environment."
        )
        print("They might be:")
        print("  1. Incorrectly mapped import names (check IMPORT_TO_PACKAGE)")
        print("  2. Packages installed via pip in conda env (not tracked by conda)")
        print("  3. Optional dependencies that aren't needed")
        print()
        for package in sorted(not_in_conda):
            print(f"  - {package}")

    print("\n" + "=" * 80)
    print(
        f"Summary: {len(conda_packages)} conda packages, {len(venv_packages)} venv packages"
    )
    print("=" * 80 + "\n")


def generate_requirements(
    required_packages: Set[str], conda_packages: Dict[str, str], output_file: Path
):
    """Generate a requirements.txt file with pinned versions from conda."""
    print(f"\nGenerating requirements file: {output_file}")

    requirements = []

    for package in sorted(required_packages):
        package_name = normalize_package_name(package)
        conda_result = find_package_in_list(package_name, conda_packages)

        if conda_result:
            name, version = conda_result
            requirements.append(f"{package_name}=={version}")
        else:
            print(
                f"Warning: {package_name} not found in conda, adding without version pin"
            )
            requirements.append(package_name)

    with open(output_file, "w") as f:
        f.write("# Auto-generated requirements from conda environment\n")
        f.write("# Generated by sync_environments.py\n\n")
        f.write("\n".join(requirements))

    print(f"✅ Requirements file generated: {output_file}")


def generate_sync_script(
    mismatches: Dict[str, Tuple[str, str]],
    missing_in_venv: Set[str],
    conda_packages: Dict[str, str],
    output_file: Path,
    venv_path: Path,
    package_manager: str = "auto",
):
    """Generate a bash script to synchronize the venv with conda versions."""
    print(f"\nGenerating sync script: {output_file}")

    # Detect package manager
    pm = detect_package_manager(package_manager)
    print(f"Sync script will use: {pm}")

    # Packages to install/upgrade
    packages_to_sync = []

    for package in sorted(missing_in_venv):
        conda_result = find_package_in_list(package, conda_packages)
        if conda_result:
            name, version = conda_result
            packages_to_sync.append((package, version, "missing"))

    for package, (conda_ver, venv_ver) in sorted(mismatches.items()):
        packages_to_sync.append((package, conda_ver, "mismatch"))

    with open(output_file, "w") as f:
        f.write("#!/bin/bash\n")
        f.write("# Auto-generated script to synchronize venv with conda environment\n")
        f.write(f"# Generated by sync_environments.py\n")
        f.write(f"# Package manager: {pm}\n\n")
        f.write("set -e  # Exit on error\n\n")

        if not packages_to_sync:
            f.write("echo 'No packages to sync!'\n")
        else:
            # Setup based on package manager
            if pm == "uv":
                f.write(f'VENV_PATH="{venv_path.absolute()}"\n')
                f.write('export VIRTUAL_ENV="$VENV_PATH"\n\n')
                f.write("# Using UV for fast package installation\n")
                install_cmd = "uv pip install"
            else:
                # Determine pip path
                if sys.platform == "win32":
                    pip_path = venv_path / "Scripts" / "pip.exe"
                else:
                    pip_path = venv_path / "bin" / "pip"
                f.write(f'VENV_PIP="{pip_path}"\n\n')
                install_cmd = '"$VENV_PIP" install'

            f.write("echo 'Starting environment synchronization...'\n")
            f.write(f"echo 'Total packages to sync: {len(packages_to_sync)}'\n\n")

            # Group by dependency order (basic heuristic)
            # Install critical packages first
            critical_packages = ["numpy", "torch", "pytorch"]
            secondary_packages = ["pytorch-lightning", "lightning", "transformers"]

            for priority_group, priority_name in [
                (critical_packages, "critical dependencies"),
                (secondary_packages, "secondary dependencies"),
                (None, "remaining packages"),
            ]:
                group_packages = []

                for package, version, reason in packages_to_sync:
                    if priority_group is None:
                        # Remaining packages
                        if not any(
                            p in package.lower()
                            for p in critical_packages + secondary_packages
                        ):
                            group_packages.append((package, version, reason))
                    else:
                        # Priority packages
                        if any(p in package.lower() for p in priority_group):
                            group_packages.append((package, version, reason))

                if group_packages:
                    f.write(
                        f"\necho '\\n--- Installing {priority_name} ({len(group_packages)} packages) ---'\n"
                    )
                    for package, version, reason in group_packages:
                        f.write(f"\necho 'Syncing {package}=={version} ({reason})'\n")
                        f.write(f'{install_cmd} "{package}=={version}"\n')

            f.write("\necho '\\n✅ Synchronization complete!'\n")
            f.write(
                'echo "Run this script\'s verification: python -c "import pkg_resources; print(\'Success!\')""\n'
            )

    # Make script executable on Unix-like systems
    if sys.platform != "win32":
        output_file.chmod(0o755)

    print(f"✅ Sync script generated: {output_file}")
    print(f"   Run with: bash {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Synchronize Python venv with conda environment"
    )
    parser.add_argument(
        "--conda-env", required=True, help="Name of the conda environment (reference)"
    )
    parser.add_argument(
        "--venv-path",
        type=Path,
        required=True,
        help="Path to the Python venv directory",
    )
    parser.add_argument(
        "--scan-paths",
        nargs="+",
        type=Path,
        default=[Path("scripts"), Path("src/tcr")],
        help="Paths to scan for imports (default: scripts src/tcr)",
    )
    parser.add_argument(
        "--local-packages",
        nargs="+",
        default=["tcr"],
        help="Local package names to exclude (default: tcr)",
    )
    parser.add_argument(
        "--output-requirements",
        type=Path,
        default=Path("requirements_from_conda.txt"),
        help="Output path for requirements.txt (default: requirements_from_conda.txt)",
    )
    parser.add_argument(
        "--output-sync-script",
        type=Path,
        default=Path("sync_venv.sh"),
        help="Output path for sync script (default: sync_venv.sh)",
    )
    parser.add_argument(
        "--no-generate-files",
        action="store_true",
        help="Skip generating requirements.txt and sync script",
    )
    parser.add_argument(
        "--package-manager",
        choices=["auto", "uv", "pip"],
        default="auto",
        help="Package manager to use (default: auto-detect, prefers uv)",
    )

    args = parser.parse_args()

    print("=" * 80)
    print("ENVIRONMENT SYNCHRONIZATION TOOL")
    print("=" * 80)
    print(f"Conda environment (reference): {args.conda_env}")
    print(f"Venv path: {args.venv_path}")
    print(f"Scan paths: {', '.join(str(p) for p in args.scan_paths)}")
    print(f"Local packages: {', '.join(args.local_packages)}")

    # Step 1: Scan codebase for imports
    print("\n" + "=" * 80)
    print("STEP 1: Scanning codebase for imported packages")
    print("=" * 80)
    all_imports = scan_codebase(args.scan_paths)
    print(f"Found {len(all_imports)} total imports")

    # Step 2: Filter out stdlib and local packages
    external_packages = filter_stdlib_and_local(all_imports, set(args.local_packages))
    print(f"Filtered to {len(external_packages)} external packages")

    # Step 3: Get package versions from conda
    print("\n" + "=" * 80)
    print("STEP 2: Extracting package versions")
    print("=" * 80)
    conda_packages = get_conda_packages(args.conda_env)
    print(f"Found {len(conda_packages)} packages in conda environment")

    # Step 4: Get package versions from venv
    venv_packages = get_venv_packages(args.venv_path, args.package_manager)
    print(f"Found {len(venv_packages)} packages in venv")

    # Step 5: Compare versions
    print("\n" + "=" * 80)
    print("STEP 3: Comparing versions")
    print("=" * 80)
    mismatches, missing_in_venv, not_in_conda = compare_versions(
        external_packages, conda_packages, venv_packages
    )

    # Step 6: Print report
    print_report(
        mismatches, missing_in_venv, not_in_conda, conda_packages, venv_packages
    )

    # Step 7: Generate output files
    if not args.no_generate_files:
        print("\n" + "=" * 80)
        print("STEP 4: Generating synchronization files")
        print("=" * 80)

        generate_requirements(
            external_packages, conda_packages, args.output_requirements
        )
        generate_sync_script(
            mismatches,
            missing_in_venv,
            conda_packages,
            args.output_sync_script,
            args.venv_path,
            args.package_manager,
        )

        print("\n" + "=" * 80)
        print("NEXT STEPS:")
        print("=" * 80)
        print(f"1. Review the sync script: {args.output_sync_script}")
        print(f"2. Run the sync script: bash {args.output_sync_script}")
        print(f"3. Alternatively, use: pip install -r {args.output_requirements}")
        print("=" * 80)


if __name__ == "__main__":
    main()
