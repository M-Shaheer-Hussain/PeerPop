import secrets

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

# In-memory dictionary to hold short-lived pairing sessions
active_pairing_sessions = {}

def generate_nonce() -> str:
    """Generates a random cryptographic challenge."""
    return secrets.token_hex(16)

def generate_pairing_code() -> str:
    """Generates the 6-digit visual code for the human to verify."""
    return str(secrets.randbelow(1000000)).zfill(6)

def verify_signature(public_key_pem: str, message: str, signature_hex: str) -> bool:
    """Verifies that the remote device possesses the private key for its public key."""
    try:
        public_key = serialization.load_pem_public_key(public_key_pem.encode('utf-8'))
        
        if not isinstance(public_key, ed25519.Ed25519PublicKey): 
            return False
            
        signature = bytes.fromhex(signature_hex)
        # Suppress Pylance false-positive for missing RSA padding arguments
        public_key.verify(signature, message.encode('utf-8'))  # type: ignore
        return True
    except (InvalidSignature, ValueError):
        return False

def sign_message(message: str) -> str:
    """Signs a challenge using your own device's private key."""
    with open(".local_drop_key.pem", "rb") as key_file:
        private_key = serialization.load_pem_private_key(key_file.read(), password=None)
        
    if not isinstance(private_key, ed25519.Ed25519PrivateKey):
        raise ValueError("Invalid private key type.")  # noqa: TRY004
        
    # Suppress Pylance false-positive for missing RSA padding arguments
    return private_key.sign(message.encode('utf-8')).hex()  # type: ignore