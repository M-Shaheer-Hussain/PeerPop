import datetime
import tempfile
import os
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from typing import cast

# Path to your existing Ed25519 key
KEY_PATH = ".local_drop_key.pem"

def generate_tls_certificates():
    """
    Loads the persistent Ed25519 key and generates a dynamic X.509 TLS certificate.
    Returns the file paths to the temporary cert and key files needed by Python's ssl module.
    """
    if not os.path.exists(KEY_PATH):
        raise FileNotFoundError(f"Missing {KEY_PATH}. Ensure Phase 3 identity is initialized.")

    # 1. Load the existing Ed25519 Private Key and cast it explicitly for the type checker
    with open(KEY_PATH, "rb") as key_file:
        private_key = cast(
            ed25519.Ed25519PrivateKey, 
            serialization.load_pem_private_key(key_file.read(), password=None)
        )

    public_key = private_key.public_key()

    # 2. Build the X.509 Certificate
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, u"LocalDrop-Peer")
    ])
    
    now = datetime.datetime.now(datetime.timezone.utc)
    
    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).public_key(
        public_key
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        now
    ).not_valid_after(
        now + datetime.timedelta(days=3650)
    ).sign(private_key, None) # type: ignore

    # 3. Serialize to PEM
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )

    # 4. Write to temporary files (Python's SSL context requires file paths)
    cert_file = tempfile.NamedTemporaryFile(delete=False, suffix=".crt")
    key_file = tempfile.NamedTemporaryFile(delete=False, suffix=".key")
    
    cert_file.write(cert_pem)
    key_file.write(key_pem)
    
    cert_file.close()
    key_file.close()

    return cert_file.name, key_file.name