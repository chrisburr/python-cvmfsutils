# -*- coding: utf-8 -*-
"""
Created by René Meusel
This file is part of the CernVM File System auxiliary tools.

A CernVM-FS repository has essential 'root files' that have a defined name and
serve as entry points into the repository.

Namely the manifest (.cvmfspublished) and the whitelist (.cvmfswhitelist) that
both have class representations inheriting from RootFile and implementing the
abstract methods defined here.

Any 'root file' in CernVM-FS is a signed list of line-by-line key-value pairs
where the key is represented by a single character in the beginning of a line
directly followed by the value. The key-value part of the file is terminted
either by EOF or by a termination line (--) followed by a signature.

The signature follows directly after the termination line with a hash of the
key-value line content (without the termination line) followed by an \n and a
binary string containing the private-key signature terminated by EOF.
"""

import abc
import hashlib
import re

from ._exceptions import *


_HEX40_RE = re.compile(r"^[0-9a-f]{40}$")

# Content-hash algorithms CVMFS may suffix onto hex digests (e.g. "abcd...-shake128").
# Values are either an `hashlib` factory (for algorithms we verify signatures with) or
# None (for algorithms we only need to recognise in hash-bearing fields).
_HASH_ALGORITHMS = {
    "sha1": hashlib.sha1,
    "shake128": hashlib.shake_128,
    "rmd160": None,
}


def parse_hash_string(raw):
    """Split a CVMFS hash string into (hex_digest, algorithm).

    CVMFS writes content hashes as "<40-hex>" for SHA-1 (the historical default) and
    as "<40-hex>-<algo>" for newer algorithms such as SHAKE128. Returns the bare
    40-character hex digest and the algorithm name ("sha1" when no suffix is present).

    Raises IncompleteRootFileSignature if the hex portion is not 40 lowercase hex
    characters or the algorithm suffix is unrecognised.
    """
    raw = raw.strip()
    if "-" in raw:
        hex_part, _, algo = raw.partition("-")
    else:
        hex_part, algo = raw, "sha1"
    if not _HEX40_RE.match(hex_part):
        raise IncompleteRootFileSignature("Hash malformed: " + raw)
    if algo not in _HASH_ALGORITHMS:
        raise IncompleteRootFileSignature(
            "Unsupported hash algorithm '" + algo + "' in: " + raw
        )
    return hex_part, algo


class RootFile(metaclass=abc.ABCMeta):
    """ Base class for CernVM-FS repository's signed 'root files' """

    @abc.abstractmethod
    def _read_line(self, line):
        pass

    @abc.abstractmethod
    def _check_validity(self):
        pass

    @abc.abstractmethod
    def __init__(self, file_object):
        """ Initializes a root file object from a file pointer """
        self.has_signature = False
        for line in file_object.readlines():
            line = line.decode()
            if len(line) == 0:
                continue
            if line[0:2] == "--":
                self.has_signature = True
                break
            self._read_line(line)
        if self.has_signature:
            self._read_signature(file_object)
        self._check_validity()

    @abc.abstractmethod
    def _verify_signature(self, public_entity):
        pass


    def verify_signature(self, public_entity):
        return self.has_signature and self._verify_signature(public_entity)


    @staticmethod
    def _hash_bytes(content, algorithm):
        """Hash the key-value block (everything before the "--" terminator).

        'content' is the raw bytes of the signed portion of the root file.
        'algorithm' selects the digest function; SHAKE128 is an XOF and is
        truncated to 20 bytes (40 hex chars) to match CVMFS's SHAKE128-160.
        """
        factory = _HASH_ALGORITHMS.get(algorithm)
        if factory is None:
            raise IncompleteRootFileSignature(
                "Cannot verify signature with algorithm: " + algorithm
            )
        hash_sum = factory()
        hash_sum.update(content)
        if algorithm == "shake128":
            return hash_sum.hexdigest(20)
        return hash_sum.hexdigest()


    def _read_signature(self, file_object):
        """ Reads the signature's checksum and the binary signature string """
        file_object.seek(0)
        content = bytearray()
        while True:
            line = file_object.readline()
            if not line:
                raise IncompleteRootFileSignature("Signature not found")
            if line[0:2] == b"--":
                break
            content.extend(line)
        if not content:
            raise IncompleteRootFileSignature("Signature not found")

        self.signature_checksum = file_object.readline().decode().rstrip()
        hex_digest, algorithm = parse_hash_string(self.signature_checksum)
        self.signature_hash_algorithm = algorithm

        if self._hash_bytes(bytes(content), algorithm) != hex_digest:
            raise InvalidRootFileSignature("Signature checksum doesn't match")
        self.signature = file_object.read()
        if len(self.signature) == 0:
            raise IncompleteRootFileSignature("Binary signature not found")
