import { useState, useEffect } from "react";
import { v4 as uuidv4 } from "uuid";
import { useFileTransfer } from "./useFileTransfer"; // Adjust this path if you saved the hook elsewhere

function FileTransfer() {
    const [trustedDevices, setTrustedDevices] = useState([]);
    const [selectedDeviceId, setSelectedDeviceId] = useState("");
    const [selectedFile, setSelectedFile] = useState(null);

    // Import the WebSocket hook state and functions
    const { streamFileToBackend, status, error, transferId, resetTransfer, setError } = useFileTransfer();

    const fetchTrustedDevices = async () => {
        try {
            const res = await fetch("http://localhost:8000/pairing/trusted", {
                credentials: "include"
            });
            if (res.ok) {
                const data = await res.json();
                setTrustedDevices(data.filter((d) => d.status === "Available"));
            }
        } catch (err) {
            // Silently ignore; PeerDiscovery already surfaces network errors.
        }
    };

    useEffect(() => {
        fetchTrustedDevices();
        const intervalId = setInterval(fetchTrustedDevices, 4000);
        return () => clearInterval(intervalId);
    }, []);

    const handleFileChange = (e) => {
        setSelectedFile(e.target.files[0] || null);
    };

    const handleSend = () => {
        if (!selectedDeviceId || !selectedFile) {
            setError("Pick a device and a file first.");
            return;
        }
        
        const newTransferId = uuidv4();
        // Trigger the WebSocket chunking stream instead of the HTTP POST
        streamFileToBackend(selectedFile, selectedDeviceId, newTransferId);
    };

    const handleReset = () => {
        resetTransfer();
        setSelectedFile(null);
    };

    return (
        <div>
            <h2>Send a File</h2>
            {trustedDevices.length === 0 && (
                <p>No trusted devices are currently online.</p>
            )}
            
            {trustedDevices.length > 0 && status === "IDLE" && (
                <>
                    <select
                        value={selectedDeviceId}
                        onChange={(e) => setSelectedDeviceId(e.target.value)}
                    >
                        <option value="">-- Select a device --</option>
                        {trustedDevices.map((device) => (
                            <option key={device.device_id} value={device.device_id}>
                                {device.device_name}
                            </option>
                        ))}
                    </select>
                    <input type="file" onChange={handleFileChange} />
                    <button onClick={handleSend} disabled={!selectedDeviceId || !selectedFile}>
                        Send File
                    </button>
                </>
            )}

            {status !== "IDLE" && (
                <div>
                    <p>Transfer ID: {transferId}</p>
                    <p>Status: {status}</p>
                    
                    {status === "CONNECTING" && <p>Waiting for the receiver to accept...</p>}
                    {status === "UPLOADING" && <p>Streaming file over WebSocket...</p>}
                    {status === "COMPLETED" && <p>✅ File sent successfully!</p>}
                    {status === "REJECTED" && <p>❌ The receiver rejected the transfer.</p>}
                    {status === "FAILED" && <p>❌ Transfer failed.</p>}
                    
                    {(status === "COMPLETED" || status === "REJECTED" || status === "FAILED") && (
                        <button onClick={handleReset}>Send Another File</button>
                    )}
                </div>
            )}
            
            {error && <p style={{ color: "red" }}>{error}</p>}
        </div>
    );
}

export default FileTransfer;