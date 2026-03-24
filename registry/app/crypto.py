import hashlib
import json
from base64 import b64decode

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding


def verify_result_signature(public_key_b64: str, output: dict, signature_b64: str) -> bool:
    """
    Verify that `signature_b64` is a valid RSA-PKCS1v15 signature of the
    SHA-256 hash of the JSON-serialised `output` (keys sorted).

    Returns True if valid, False otherwise.
    """
    try:
        pub_der = b64decode(public_key_b64)
        public_key = serialization.load_der_public_key(pub_der)

        payload = json.dumps(output, sort_keys=True).encode()
        digest = hashlib.sha256(payload).digest()
        signature = b64decode(signature_b64)

        public_key.verify(signature, digest, padding.PKCS1v15(), hashes.SHA256())
        return True
    except (InvalidSignature, Exception):
        return False
