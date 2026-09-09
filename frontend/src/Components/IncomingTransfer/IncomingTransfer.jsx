import { useState, useEffect } from "react";

function IncomingTransfers() {
    const [incomingTransfers, setIncomingTransfers] = useState([]);

    useEffect(() => {
        const fetchIncoming = async () => {
            try {
                const res = await fetch("http://localhost:8000/transfer/incoming");
                if (res.ok) {
                    setIncomingTransfers(await res.json());
                }
            } catch (err) {
                console.error("Failed to fetch incoming transfers", err);
            }
        };

        fetchIncoming();
        const intervalId = setInterval(fetchIncoming, 3000);
        return () => clearInterval(intervalId);
    }, []);

    const handleApprove = async (transferId) => {
        try {
            const res = await fetch(`http://localhost:8000/transfer/approve/${transferId}`, {
                method: "POST",
                credentials: "include"
            });

            if (res.ok) {
                setIncomingTransfers((prev) => prev.filter((t) => t.transfer_id !== transferId));
            } else {
                alert("Failed to approve transfer.");
            }
        } catch (error) {
            alert("Network error approving transfer.");
        }
    };

    const handleReject = async (transferId) => {
        try {
            const res = await fetch(`http://localhost:8000/transfer/reject/${transferId}`, {
                method: "POST",
                credentials: "include"
            });

            if (res.ok) {
                setIncomingTransfers((prev) => prev.filter((t) => t.transfer_id !== transferId));
            } else {
                alert("Failed to reject transfer.");
            }
        } catch (error) {
            alert("Network error rejecting transfer.");
        }
    };

    if (incomingTransfers.length === 0) return null;

    return (
        <div>
            <h3>Incoming File Transfers</h3>
            {incomingTransfers.map((t) => (
                <div key={t.transfer_id}>
                    <strong>{t.sender_device_name}</strong> wants to send you a file:
                    <p>{t.filename} ({(t.size / 1024).toFixed(1)} KB)</p>
                    <button onClick={() => handleApprove(t.transfer_id)}>Accept</button>
                    <button onClick={() => handleReject(t.transfer_id)}>Reject</button>
                </div>
            ))}
        </div>
    );
}

export default IncomingTransfers;