import asyncio
import ssl
import datetime
import tempfile
import websockets
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

# ---------------------------------------------------------
# 1. GENERATE IDENTITY & X.509 CERTIFICATE
# ---------------------------------------------------------
def generate_identity_and_cert():
    print("[1] Generating Ed25519 Identity and Self-Signed X.509 Certificate...")
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    # RFC 8410: Ed25519 X.509 Subject
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, u"LocalDrop-Peer")])
    
    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).public_key(
        public_key
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.datetime.utcnow()
    ).not_valid_after(
        # Valid for 10 years
        datetime.datetime.utcnow() + datetime.timedelta(days=3650)
    ).sign(private_key, None) # Ed25519 signatures don't take a separate hash algorithm

    # Save temporarily to feed into Python's ssl module
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    
    expected_pub_key_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )

    return cert_pem, key_pem, expected_pub_key_bytes

# ---------------------------------------------------------
# 2. WEBSOCKET SERVER (Device B)
# ---------------------------------------------------------
async def echo_server(websocket):
    print("[SERVER] Connection received! Waiting for client application handshake...")
    try:
        async for message in websocket:
            print(f"[SERVER] Received: {message}")
            await websocket.send(f"Echo: {message}")
    except websockets.exceptions.ConnectionClosed:
        print("[SERVER] Client disconnected.")

async def run_server(cert_file, key_file):
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_context.load_cert_chain(certfile=cert_file, keyfile=key_file)
    
    print("[2] Starting WSS Server...")
    server = await websockets.serve(echo_server, "localhost", 8765, ssl=ssl_context)
    return server

# ---------------------------------------------------------
# 3. WEBSOCKET CLIENT (Device A)
# ---------------------------------------------------------
async def run_client(expected_pub_key_bytes):
    # DANGER: CERT_NONE disables standard CA verification (required for self-signed)
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    print("[3] Client connecting to WSS Server...")
    
    # We open the connection, but we DO NOT trust it yet. State: TLS_ESTABLISHED
    async with websockets.connect("wss://localhost:8765", ssl=ssl_context) as websocket:
        
        # --- THE EXTRACTION TRICK ---
        # Get the underlying Python SSL object
        ssl_obj = websocket.transport.get_extra_info('ssl_object')
        
        # getpeercert() returns {} because of CERT_NONE. We MUST use binary_form=True
        der_cert = ssl_obj.getpeercert(binary_form=True)
        if not der_cert:
            print("[CLIENT] ❌ FAILURE: No peer certificate presented.")
            return

        # Parse the raw DER bytes back into a cryptography object
        parsed_cert = x509.load_der_x509_certificate(der_cert)
        extracted_pub_key = parsed_cert.public_key()
        
        extracted_pub_key_bytes = extracted_pub_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )

        print("[4] Comparing Extracted Key to Pinned Key...")
        if extracted_pub_key_bytes == expected_pub_key_bytes:
            print("[CLIENT] ✅ SUCCESS: Peer TLS identity mathematically verified!")
            # State: VERIFYING_PEER_KEY -> AUTHENTICATING_PEER
            await websocket.send("PEERPOP_CONNECTION_AUTH_V1|DeviceA|SignedNonce")
            response = await websocket.recv()
            print(f"[CLIENT] App layer response: {response}")
        else:
            print("[CLIENT] ❌ FAILURE: MITM Attack Detected. Identity mismatch.")
            # Drop connection immediately

# ---------------------------------------------------------
# 4. ORCHESTRATION
# ---------------------------------------------------------
async def main():
    cert_pem, key_pem, expected_pub_key_bytes = generate_identity_and_cert()
    
    with tempfile.NamedTemporaryFile(delete=False) as cert_f, tempfile.NamedTemporaryFile(delete=False) as key_f:
        cert_f.write(cert_pem)
        key_f.write(key_pem)
        cert_file = cert_f.name
        key_file = key_f.name

    server = await run_server(cert_file, key_file)
    
    # Give server a moment to start
    await asyncio.sleep(1)
    
    await run_client(expected_pub_key_bytes)
    
    server.close()
    await server.wait_closed()

if __name__ == "__main__":
    asyncio.run(main())