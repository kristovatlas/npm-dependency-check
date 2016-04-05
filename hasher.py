"""Creates message digests of files."""

import hashlib

def hash_file(filename):
    """Get hash of file contents."""
    return sha256_file(filename)

def sha256_file(filename):
    """Get SHA-256 hash of a file's contents.

    Args:
        filename (str): The relative or absolute path of the target file.

    This matches the output of `openssl dgst -sha256` for both small and very
    large files, and takes a comparable amount of time.

    From:
    http://stackoverflow.com/questions/3431825/generating-a-md5-checksum-of-a-file
    """
    hash_sha256 = hashlib.sha256()
    with open(filename, 'rb') as in_file:
        for chunk in iter(lambda: in_file.read(4096), b""):
            hash_sha256.update(chunk)
    return hash_sha256.hexdigest()
