import os

from app.database.database import localsession
from app.models.models import Device
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

PRIVATE_KEY_PATH = ".local_drop_key.pem"

def initialize_device_identity():
    db = localsession()
    try:
        # Check Device Identity: Exists?
        if os.path.exists(PRIVATE_KEY_PATH):
            return db.query(Device).filter(Device.is_local == True).first()

        # Missing? Generate Key Pair
        private_key = ed25519.Ed25519PrivateKey.generate()
        public_key = private_key.public_key()

        # Store Identity (Private Key File)
        private_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        with open(PRIVATE_KEY_PATH, "wb") as key_file:
            key_file.write(private_bytes)
        
        if os.name == 'posix':
            os.chmod(PRIVATE_KEY_PATH, 0o600)

        # Serialize Public Key
        public_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')
        
        # --- THE FIX: Purge old orphaned local identities before inserting the new one ---
        db.query(Device).filter(Device.is_local == True).delete()
        
        # Create and store the brand new local identity
        new_device = Device(
            device_name="Local-Node",
            public_key=public_bytes,
            is_local=True
        )
        db.add(new_device)
        db.commit()
        db.refresh(new_device)
        
        return new_device
        
    finally:
        db.close()