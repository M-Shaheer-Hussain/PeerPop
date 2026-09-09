import { useState, useEffect } from "react";

function PeerDiscovery() {
    const [availDevices, setAvailDevices] = useState([]);
    const [error, setError] = useState(null);
    const [outgoingSession, setOutgoingSession] = useState(null);

    const fetchDetails = async () => {
        try {
            const response = await fetch("http://localhost:8000/network/nearby");
            if (response.ok) {
                const data = await response.json();
                setAvailDevices(data);
                setError(null); 
                return;
            }
            const errData = await response.json();
            setError(`Device Loading Failed: ${errData.detail || "Unknown Error"}`);
        } catch (error) {
            setError("Available Devices could not be fetched. Is the server running?");
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

            <h2>Nearby Devices</h2>
            
            {error && <p>{error}</p>}
            
            {availDevices.length === 0 && !error && (
                <p>Scanning for nearby devices...</p>
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