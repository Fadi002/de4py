from de4py.engines.analyzers import (
    detect_packer, unpack_file, get_file_hashs,
    sus_strings_lookup, all_strings_lookup
)


def run_detect_packer(file_path):
    """Detects the packer/protector of a given file."""
    return detect_packer(file_path)


def run_unpack_file(file_path):
    """Attempts to unpack a file and returns the operation status."""
    return unpack_file(file_path)


def run_get_file_hashs(file_path):
    """Calculates and returns common cryptographic hashes for a file."""
    return get_file_hashs(file_path)


def run_sus_strings_lookup(file_path):
    """Performs a regex-based lookup for suspicious strings."""
    return sus_strings_lookup(file_path)


def run_all_strings_lookup(file_path):
    """Extracts all printable strings from a binary file."""
    return all_strings_lookup(file_path)
