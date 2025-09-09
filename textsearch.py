#!/usr/bin/env python3
"""
Text Search Tool with .gitignore Support

A tool that recursively searches for text occurrences in files while respecting .gitignore rules.
Always searches files with ".env" in the filename regardless of .gitignore rules.
Automatically skips binary files.
"""

import os
import sys
import argparse
import fnmatch
from pathlib import Path
from typing import List, Set, Tuple, Optional
import mimetypes


class GitignoreParser:
    """Parser for .gitignore files that determines if files should be ignored."""

    def __init__(self, gitignore_path: str):
        self.gitignore_path = Path(gitignore_path)
        self.base_dir = self.gitignore_path.parent
        self.patterns = []
        self._parse_gitignore()

    def _parse_gitignore(self):
        """Parse the .gitignore file and extract patterns."""
        if not self.gitignore_path.exists():
            return

        with open(self.gitignore_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue

                # Handle negation patterns (!) - we'll implement basic support
                negate = line.startswith('!')
                if negate:
                    line = line[1:]

                self.patterns.append((line, negate))

    def should_ignore(self, file_path: Path) -> bool:
        """Check if a file should be ignored based on .gitignore patterns."""
        # Always include files with ".env" in the filename regardless of .gitignore
        if '.env' in file_path.name:
            return False

        try:
            # Get relative path from the .gitignore directory
            rel_path = file_path.relative_to(self.base_dir)
            rel_path_str = str(rel_path).replace('\\', '/')  # Use forward slashes

            ignored = False

            for pattern, negate in self.patterns:
                # Handle different pattern types
                if pattern.endswith('/'):
                    # Directory pattern
                    pattern = pattern[:-1]
                    if file_path.is_dir():
                        if self._match_pattern(pattern, rel_path_str) or \
                           self._match_pattern(pattern, file_path.name):
                            ignored = not negate if negate else True
                elif '/' in pattern:
                    # Path pattern
                    if self._match_pattern(pattern, rel_path_str):
                        ignored = not negate if negate else True
                else:
                    # Filename pattern
                    if self._match_pattern(pattern, file_path.name) or \
                       self._match_pattern(pattern, rel_path_str):
                        ignored = not negate if negate else True

            return ignored

        except ValueError:
            # Path is not relative to base_dir
            return False

    def _match_pattern(self, pattern: str, path: str) -> bool:
        """Check if a pattern matches a path using glob-style matching."""
        # Handle special cases
        if pattern == path:
            return True

        # Use fnmatch for glob-style pattern matching
        if fnmatch.fnmatch(path, pattern):
            return True

        # Check if pattern matches any part of the path
        path_parts = path.split('/')
        for i in range(len(path_parts)):
            partial_path = '/'.join(path_parts[i:])
            if fnmatch.fnmatch(partial_path, pattern):
                return True

        return False


def is_binary_file(file_path: Path) -> bool:
    """
    Determine if a file is binary by checking its content.
    Uses multiple heuristics for better accuracy.
    """
    try:
        # Check MIME type first
        mime_type, _ = mimetypes.guess_type(str(file_path))
        if mime_type:
            if mime_type.startswith('text/'):
                return False
            if mime_type.startswith(('image/', 'video/', 'audio/', 'application/octet-stream')):
                return True

        # Read a small chunk to check for null bytes and non-text characters
        with open(file_path, 'rb') as f:
            chunk = f.read(8192)  # Read first 8KB

        if not chunk:
            return False  # Empty file is not binary

        # Check for null bytes (strong indicator of binary)
        if b'\x00' in chunk:
            return True

        # Check for high ratio of non-text bytes
        non_text_bytes = sum(1 for byte in chunk if byte < 32 and byte not in (9, 10, 13))
        if len(chunk) > 0 and (non_text_bytes / len(chunk)) > 0.3:
            return True

        return False

    except (IOError, OSError, PermissionError):
        return True  # Assume binary if we can't read it


def search_text_in_file(file_path: Path, search_texts: List[str], case_sensitive: bool = True) -> List[Tuple[int, str, str]]:
    """
    Search for texts in a file and return matches with line numbers.
    Returns list of (line_number, line_content, matched_text) tuples.
    """
    matches = []

    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line_num, line in enumerate(f, 1):
                line_stripped = line.rstrip('\n\r')
                search_line = line_stripped if case_sensitive else line_stripped.lower()

                for search_text in search_texts:
                    if search_text in search_line:
                        matches.append((line_num, line_stripped, search_text))

    except (IOError, OSError, PermissionError, UnicodeDecodeError) as e:
        print(f"Warning: Could not read {file_path}: {e}")

    return matches


def find_gitignore_parsers(directory: Path) -> dict:
    """Find all .gitignore files in the directory tree and create parsers."""
    parsers = {}

    for root, dirs, files in os.walk(directory):
        root_path = Path(root)
        if '.gitignore' in files:
            gitignore_path = root_path / '.gitignore'
            parsers[root_path] = GitignoreParser(str(gitignore_path))

    return parsers


def get_applicable_parser(file_path: Path, parsers: dict) -> Optional[GitignoreParser]:
    """Get the most specific .gitignore parser that applies to a file."""
    applicable_parser = None
    max_depth = -1

    for parser_dir, parser in parsers.items():
        try:
            # Check if the file is under this parser's directory
            file_path.relative_to(parser_dir)
            # Count depth to find most specific parser
            depth = len(file_path.relative_to(parser_dir).parts)
            if depth > max_depth:
                max_depth = depth
                applicable_parser = parser
        except ValueError:
            # File is not under this directory
            continue

    return applicable_parser


def search_directory(directory: Path, search_texts: List[str], case_sensitive: bool = True) -> dict:
    """
    Recursively search directory for text occurrences.
    Returns dict mapping file paths to their matches.
    """
    results = {}

    # Find all .gitignore parsers in the directory tree
    print(f"Scanning for .gitignore files in {directory}...")
    gitignore_parsers = find_gitignore_parsers(directory)
    print(f"Found {len(gitignore_parsers)} .gitignore files")

    files_processed = 0
    files_skipped = 0

    for root, dirs, files in os.walk(directory):
        root_path = Path(root)

        # Filter directories based on .gitignore rules
        dirs_to_remove = []
        for dir_name in dirs:
            dir_path = root_path / dir_name
            parser = get_applicable_parser(dir_path, gitignore_parsers)
            if parser and parser.should_ignore(dir_path):
                dirs_to_remove.append(dir_name)

        for dir_name in dirs_to_remove:
            dirs.remove(dir_name)

        # Process files
        for file_name in files:
            file_path = root_path / file_name

            # Check if file should be ignored by .gitignore
            parser = get_applicable_parser(file_path, gitignore_parsers)
            if parser and parser.should_ignore(file_path):
                files_skipped += 1
                continue

            # Skip binary files
            if is_binary_file(file_path):
                files_skipped += 1
                continue

            # Search for text in the file
            matches = search_text_in_file(file_path, search_texts, case_sensitive)
            if matches:
                results[str(file_path)] = matches

            files_processed += 1
            if files_processed % 100 == 0:
                print(f"Processed {files_processed} files...")

    print(f"Completed: {files_processed} files processed, {files_skipped} files skipped")
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Search for text occurrences in files while respecting .gitignore rules",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python search_tool.py "TODO" "FIXME" -d /path/to/project
  python search_tool.py "password" "secret" -d . -o results.txt
  python search_tool.py "import pandas" -d /my/python/project
        """
    )

    parser.add_argument(
        'search_texts',
        nargs='+',
        help='Text strings to search for'
    )

    parser.add_argument(
        '-d', '--directory',
        type=str,
        default='.',
        help='Directory to search (default: current directory)'
    )

    parser.add_argument(
        '-o', '--output',
        type=str,
        help='Output file to save results (default: print to console)'
    )

    parser.add_argument(
        '--case-sensitive',
        action='store_true',
        help='Perform case-sensitive search (default: case-insensitive)'
    )

    args = parser.parse_args()

    # Validate directory
    search_dir = Path(args.directory).resolve()
    if not search_dir.exists():
        print(f"Error: Directory '{search_dir}' does not exist")
        sys.exit(1)

    if not search_dir.is_dir():
        print(f"Error: '{search_dir}' is not a directory")
        sys.exit(1)

    # Prepare search texts
    search_texts = args.search_texts
    case_sensitive = args.case_sensitive
    if not case_sensitive:
        search_texts = [text.lower() for text in search_texts]

    print(f"Searching for: {', '.join(repr(text) for text in args.search_texts)}")
    print(f"In directory: {search_dir}")
    print(f"Case sensitive: {case_sensitive}")
    print()

    # Perform search
    try:
        results = search_directory(search_dir, search_texts, case_sensitive)
    except KeyboardInterrupt:
        print("\nSearch interrupted by user")
        sys.exit(1)

    # Format and output results
    if not results:
        print("No matches found.")
        return

    output_lines = []
    total_matches = 0

    output_lines.append(f"Found matches in {len(results)} files:\n")

    for file_path, matches in sorted(results.items()):
        output_lines.append(f"File: {file_path}")
        for line_num, line_content, matched_text in matches:
            output_lines.append(f"  Line {line_num}: {line_content}")
            total_matches += 1
        output_lines.append("")  # Empty line between files

    output_lines.append(f"Total matches: {total_matches}")
    output_text = "\n".join(output_lines)

    # Output results
    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(output_text)
            print(f"Results saved to: {args.output}")
        except IOError as e:
            print(f"Error saving to file: {e}")
            print(output_text)
    else:
        print(output_text)


if __name__ == "__main__":
    main()
