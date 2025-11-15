"""Utility functions for the LLVM IR analysis tool."""

from pathlib import Path


def safe_name(name: str) -> str:
    """
    Convert a name to a safe filename by replacing invalid characters.
    
    Args:
        name: Original name (may contain special characters)
    
    Returns:
        Safe filename with only allowed characters
    """
    allowed = "-._abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return "".join(ch if ch in allowed else "_" for ch in name)


def read_allowed_functions(file_path: str | Path) -> set[str]:
    """
    Read function names from a file (one per line).
    
    Args:
        file_path: Path to file containing function names
    
    Returns:
        Set of function names (comments and empty lines are ignored)
    
    Raises:
        SystemExit: If file doesn't exist
    """
    p = Path(file_path)
    if not p.exists():
        raise SystemExit(f"--functions-file not found: {p}")
    raw = p.read_text(encoding="utf-8", errors="ignore").splitlines()
    return {ln.strip() for ln in raw if ln.strip() and not ln.lstrip().startswith("#")}

