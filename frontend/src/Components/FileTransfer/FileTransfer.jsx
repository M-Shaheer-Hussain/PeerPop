import { useState, useEffect } from "react";

function FileTransfer() {
    const [trustedDevices, setTrustedDevices] = useState([]);
    const [selectedDeviceId, setSelectedDeviceId] = useState("");
    const [selectedFile, setSelectedFile] = useState(null);
    const [transferId, setTransferId] = useState(null);
    const [status, setStatus] = useState(null);
    const [error, setError] = useState(null);

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

    useEffect(() => {
        if (!transferId) return;
        if (status === "COMPLETED" || status === "REJECTED" || status === "FAILED") return;

        const checkStatus = async () => {
            try {
                const res = await fetch(`http://localhost:8000/transfer/status/${transferId}`);
                if (res.ok) {
                    const data = await res.json();
                    setStatus(data.status);
                    if (data.status === "FAILED" && data.error) {
                        setError(data.error);
                    }
                }
            } catch (err) {
                // Keep polling; a transient network hiccup shouldn't stop the flow.
            }
        };

        const intervalId = setInterval(checkStatus, 2000);
        return () => clearInterval(intervalId);
    }, [transferId, status]);

    const handleFileChange = (e) => {
        setSelectedFile(e.target.files[0] || null);
    };

    const handleSend = async () => {
        if (!selectedDeviceId || !selectedFile) {
            setError("Pick a device and a file first.");
            return;
        }

        setError(null);
        setStatus(null);
        setTransferId(null);

        try {
            const formData = new FormData();
            formData.append("device_id", selectedDeviceId);
            formData.append("file", selectedFile);

            const res = await fetch("http://localhost:8000/transfer/send", {
                method: "POST",
                credentials: "include",
                body: formData
            });

            if (res.ok) {
                const data = await res.json();
                setTransferId(data.transfer_id);
                setStatus(data.status);
            } else {
                const errData = await res.json();
                setError(errData.detail || "Failed to start transfer.");
            }
        } catch (err) {
            setError("Network error starting transfer.");
        }
    };

    const handleReset = () => {
        setTransferId(null);
        setStatus(null);
        setError(null);
        setSelectedFile(null);
    };

    return (
        <div>
            <h2>Send a File</h2>

            {trustedDevices.length === 0 && (
                <p>No trusted devices are currently online.</p>
            )}

            {trustedDevices.length > 0 && (
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
            )}

            <input type="file" onChange={handleFileChange} />

            <button onClick={handleSend} disabled={!selectedDeviceId || !selectedFile}>
                Send File
            </button>

            {transferId && (
                <div>
                    <p>Transfer ID: {transferId}</p>
                    <p>Status: {status}</p>

                    {status === "PENDING_APPROVAL" && (
                        <p>Waiting for the receiver to accept...</p>
                    )}
                    {status === "SENDING" && <p>Sending file...</p>}
                    {status === "COMPLETED" && <p>✅ File sent successfully!</p>}
                    {status === "REJECTED" && <p>❌ The receiver rejected the transfer.</p>}
                    {status === "FAILED" && <p>❌ Transfer failed.</p>}

                    <button onClick={handleReset}>Send Another File</button>
                </div>
            )}

            {error && <p>{error}</p>}
        </div>
    );
}

export default FileTransfer;