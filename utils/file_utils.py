"""
File Utilities

Helpers for reading C++ files and listing test cases.
"""

from pathlib import Path
from typing import List


def read_cpp_file(path: str) -> str:
    """
    Read a C++ source file and return its contents.

    Args:
        path: Path to the .cpp file

    Returns:
        File contents as string
    """
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    return file_path.read_text(encoding="utf-8", errors="replace")


def list_test_cases(directory: str) -> List[Path]:
    """
    List all TC*.cpp test case files in a directory, sorted by name.

    Args:
        directory: Path to directory containing test cases

    Returns:
        Sorted list of Path objects for each test case
    """
    dir_path = Path(directory)
    if not dir_path.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")
    return sorted(dir_path.glob("TC*.cpp"))


def list_solutions(directory: str) -> List[Path]:
    """
    List all SOL*.cpp solution files in a directory, sorted by name.

    Args:
        directory: Path to directory containing solutions

    Returns:
        Sorted list of Path objects for each solution
    """
    dir_path = Path(directory)
    if not dir_path.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")
    return sorted(dir_path.glob("SOL*.cpp"))
