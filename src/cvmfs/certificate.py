# -*- coding: utf-8 -*-
"""
Created by René Meusel
This file is part of the CernVM File System auxiliary tools.
"""

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding


class Certificate:
    """ Wraps an X.509 certificate object as stored in CVMFS repositories """

    def __init__(self, certificate_file):
        self._certificate_file = certificate_file
        cert_data = self._certificate_file.read()
        if isinstance(cert_data, str):
            cert_data = cert_data.encode()
        self.openssl_certificate = x509.load_pem_x509_certificate(cert_data)

    def __str__(self):
        return "<Certificate " + self.get_fingerprint() + ">"

    def __repr__(self):
        return self.__str__()

    def get_openssl_certificate(self):
        """ return the certificate as cryptography.x509.Certificate object """
        return self.openssl_certificate

    def get_fingerprint(self, algorithm='sha1'):
        """ returns the fingerprint of the X509 certificate """
        if algorithm == 'sha1':
            hash_algo = hashes.SHA1()
        elif algorithm == 'sha256':
            hash_algo = hashes.SHA256()
        else:
            raise ValueError(f"Unsupported hash algorithm: {algorithm}")
        fp = self.openssl_certificate.fingerprint(hash_algo)
        return ':'.join(f'{b:02X}' for b in fp)

    def verify(self, signature, message):
        """ verify a given signature to an expected 'message' string """
        pubkey = self.openssl_certificate.public_key()
        try:
            pubkey.verify(
                signature,
                message.encode(),
                padding.PKCS1v15(),
                hashes.SHA1()
            )
            return True
        except Exception:
            return False
