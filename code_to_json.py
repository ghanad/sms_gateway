import argparse
import json
import os
from pathlib import Path

# Directories to exclude from traversal
EXCLUDE_DIRS = {
    '.git',
    'node_modules',
    'lib',
    'venv',
    'dist',
    'build',
    '__pycache__',
    '.pytest_cache',
}

# Individual files to exclude (relative paths or file names)
EXCLUDE_FILES = {
    'package-lock.json',
    'yarn.lock',
    'pnpm-lock.yaml',
    'output.json'
}

# File extensions considered source code
CODE_EXTENSIONS = {
    '.py', '.js', '.ts', '.tsx', '.jsx', '.java', '.go', '.rb', '.php', '.c',
    '.cpp', '.h', '.hpp', '.cs', '.sh', '.rs', '.swift', '.kt', '.scala',
    '.html', '.css', '.scss', '.svelte', '.vue', '.yaml', '.yml', '.json',
}


def is_code_file(path: Path) -> bool:
    """Return True if path points to a code file."""
    return path.suffix in CODE_EXTENSIONS


def is_excluded_file(path: Path, root: Path) -> bool:
    """Return True if path should be excluded based on name or relative path."""
    rel = path.relative_to(root).as_posix()
    return path.name in EXCLUDE_FILES or rel in EXCLUDE_FILES


def generate_tree(root: Path) -> str:
    """Generate an ASCII tree for the project starting at root."""
    lines = [root.name]

    def inner(directory: Path, prefix: str = "") -> None:
        entries = [
            e for e in sorted(directory.iterdir())
            if (
                e.is_dir() and e.name not in EXCLUDE_DIRS and not e.name.startswith('.')
            )
            or (
                e.is_file()
                and is_code_file(e)
                and not is_excluded_file(e, root)
            )
        ]
        count = len(entries)
        for index, entry in enumerate(entries):
            connector = "└── " if index == count - 1 else "├── "
            lines.append(f"{prefix}{connector}{entry.name}")
            if entry.is_dir():
                extension = "    " if index == count - 1 else "│   "
                inner(entry, prefix + extension)

    inner(root)
    return "\n".join(lines)


def collect_files(root: Path) -> dict[str, str]:
    """Collect source code files under root and return mapping of path to contents."""
    files: dict[str, str] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        # Modify dirnames in place to skip excluded directories
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS and not d.startswith('.')]
        for filename in filenames:
            file_path = Path(dirpath) / filename
            if is_code_file(file_path) and not is_excluded_file(file_path, root):
                rel_path = file_path.relative_to(root).as_posix()
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        files[rel_path] = f.read()
                except Exception:
                    # Skip files that cannot be read as text
                    pass
    return files


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert project source code to JSON")
    parser.add_argument("root", nargs="?", default=".", help="Project root directory")
    parser.add_argument("-o", "--output", default="output.json", help="Output JSON file (defaults to output.json)")
    args = parser.parse_args()

    root_path = Path(args.root).resolve()
    tree_str = generate_tree(root_path)
    files = collect_files(root_path)

    result = {"tree": tree_str, "files": files}

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
