import { useState, useEffect } from "react";

function IncomingRequests() {
    const [incomingRequests, setIncomingRequests] = useState([]);

    useEffect(() => {
        const fetchPending = async () => {
            try {
                const res = await fetch("http://localhost:8000/pairing/pending");
                if (res.ok) {
                    setIncomingRequests(await res.json());
                }
            } catch (err) {
                console.error("Failed to fetch incoming requests", err);
            }
        };

        fetchPending();
        const intervalId = setInterval(fetchPending, 3000);
        return () => clearInterval(intervalId);
    }, []);

    const handleApprove = async (sessionId) => {
        try {
            const res = await fetch(`http://localhost:8000/pairing/approve/${sessionId}`, {
                method: "POST",
                credentials: "include"
            });

            if (res.ok) {
                alert("Device Trusted!");
                setIncomingRequests(incomingRequests.filter(req => req.session_id !== sessionId));
            } else {
                alert("Failed to approve device.");
            }
        } catch (error) {
            alert("Network error approving pairing");
        }
    };

    if (incomingRequests.length === 0) return null;

    return (
        <div>
            <h3>Incoming Pairing Requests</h3>
            {incomingRequests.map((req) => (
                <div key={req.session_id}>
                    <strong>{req.device_name}</strong> wants to pair.
                    <h2>{req.code}</h2>
                    <p>Verify this code matches the other device.</p>
                    <button onClick={() => handleApprove(req.session_id)}>Accept</button>
                </div>
            ))}
        </div>
    );
}

export default IncomingRequests;