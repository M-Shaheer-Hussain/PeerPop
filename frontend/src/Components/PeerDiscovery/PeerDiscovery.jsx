import { useState, useEffect } from "react";

function PeerDiscovery() {
    const [availDevices, setAvailDevices] = useState([]);
    const [error, setError] = useState(null);

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

    return (
        <div>
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
                        <p>🟢 {device.status}</p>
                    </div>
                ))}
            </div>
        </div>
    );
}

export default PeerDiscovery;