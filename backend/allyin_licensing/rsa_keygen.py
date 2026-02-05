#!/usr/bin/env python3
"""
RSA Key Generation Utility for AllyIn Licensing
Generates a private/public key pair for RSA signing/verification.
"""
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
import os

def generate_rsa_keypair(private_key_path="private_key.pem", public_key_path="public_key.pem", key_size=2048):
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=key_size,
        backend=default_backend()
    )
    # Write private key
    with open(private_key_path, "wb") as f:
        f.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ))
    # Write public key
    public_key = private_key.public_key()
    with open(public_key_path, "wb") as f:
        f.write(public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ))
    print(f"RSA key pair generated:\n  Private: {private_key_path}\n  Public:  {public_key_path}")

def main():
    generate_rsa_keypair()

if __name__ == "__main__":
    main() 