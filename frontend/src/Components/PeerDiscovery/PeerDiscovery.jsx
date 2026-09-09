import { useState, useEffect } from "react";

function PeerDiscovery() {
    const [availDevices, setAvailDevices] = useState([]);
    const [trustedDevices, setTrustedDevices] = useState([]);
    const [error, setError] = useState(null);
    const [outgoingSession, setOutgoingSession] = useState(null);

    const fetchDetails = async () => {
        try {
            const resNearby = await fetch("http://localhost:8000/network/nearby");
            const resTrusted = await fetch("http://localhost:8000/pairing/trusted", {
                credentials: "include" 
            });

            if (resNearby.ok && resTrusted.ok) {
                const nearbyData = await resNearby.json();
                const trustedData = await resTrusted.json();
                
                setTrustedDevices(trustedData);
                
                const trustedIds = new Set(trustedData.map(d => d.device_id));
                const untrustedNearby = nearbyData.filter(d => !trustedIds.has(d.device_id));
                
                setAvailDevices(untrustedNearby);
                setError(null);
            }
        } catch (error) {
            setError("Network error fetching devices.");
        }
    };

    useEffect(() => {
        fetchDetails();
        const intervalId = setInterval(fetchDetails, 4000);  
        return () => clearInterval(intervalId);
    }, []); 

    useEffect(() => {
        if (!outgoingSession) return;

        const checkStatus = async () => {
            try {
                const res = await fetch(`http://localhost:8000/pairing/status/outbound/${outgoingSession.session_id}`);
                if (res.ok) {
                    const data = await res.json();
                    if (data.status === "TRUSTED") {
                        alert("Pairing Successful! Device is now trusted.");
                        setOutgoingSession(null);
                    } else if (data.status === "REJECTED_OR_EXPIRED") {
                        alert("Pairing failed, rejected, or expired.");
                        setOutgoingSession(null);
                    }
                }
            } catch (err) {
                console.error("Failed to check status", err);
            }
        };

        const intervalId = setInterval(checkStatus, 2000);
        return () => clearInterval(intervalId);
    }, [outgoingSession]);

    const handlePair = async (device) => {
        try {
            const res = await fetch("http://localhost:8000/pairing/initiate", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                credentials: "include",
                body: JSON.stringify({
                    target_ip: device.ip_address,
                    target_port: device.port,
                    target_device_id: device.device_id,
                    target_device_name: device.device_name,
                    target_public_key: device.public_key
                })
            });

            if (res.ok) {
                setOutgoingSession(await res.json());
            } else {
                const errData = await res.json();
                alert(`Pairing error: ${errData.detail}`);
            }
        } catch (error) {
            alert("Network error initiating pairing");
        }
    };

    return (
        <div>
            {outgoingSession && (
                <div>
                    <h3>Waiting for Approval...</h3>
                    <p>Make sure the other device displays this code:</p>
                    <h2>{outgoingSession.code}</h2>
                    <button onClick={() => setOutgoingSession(null)}>Cancel</button>
                </div>
            )}

            {error && <p>{error}</p>}

            <h2>My Trusted Devices</h2>
            <div>
                {trustedDevices.filter(d => d.status === "Available").length === 0 && (
                    <p>No trusted devices are currently online.</p>
                )}
                
                {trustedDevices.filter(d => d.status === "Available").map((device) => (
                    <div key={device.device_id}>
                        <strong>{device.device_name}</strong>
                        <p>ID: {device.device_id.substring(0, 12)}...</p>
                        <p>✅ <strong>Trusted & Connected</strong></p>
                    </div>
                ))}
            </div>

            <h2>Available to Pair</h2>
            {availDevices.length === 0 && !error && (
                <p>Scanning for new devices...</p>
            )}

            <div>
                {availDevices.map((device) => (
                    <div key={device.device_id}>
                        <strong>{device.device_name}</strong>
                        <p>ID: {device.device_id.substring(0, 12)}...</p>
        
                        <p>
                            {device.status === "Available" ? "🟢" : "⚪"} {device.status}
                        </p>

                        {device.status === "Available" && !outgoingSession && (
                            <button onClick={() => handlePair(device)}>Pair</button>
                        )}
                    </div>
                ))}
            </div>
        </div>
    );
}

export default PeerDiscovery;