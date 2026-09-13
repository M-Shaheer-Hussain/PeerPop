import { useState } from 'react';

export const useFileTransfer = () => {
    const [status, setStatus] = useState("IDLE");
    const [error, setError] = useState(null);
    const [transferId, setTransferId] = useState(null);

    const streamFileToBackend = (file, targetDeviceId, newTransferId) => {
        setStatus("CONNECTING");
        setError(null);
        setTransferId(newTransferId);
        
        const ws = new WebSocket(`ws://localhost:8000/transfer/ws/stream/${targetDeviceId}`);
        
        ws.onopen = () => {
            ws.send(JSON.stringify({
                transfer_id: newTransferId,
                filename: file.name,
                size: file.size
            }));
        };

        ws.onmessage = async (event) => {
            const msg = JSON.parse(event.data);
            
            if (msg.status === "ACCEPTED") {
                setStatus("UPLOADING");
                const CHUNK_SIZE = 64 * 1024;
                let offset = 0;
                
                while (offset < file.size) {
                    const slice = file.slice(offset, offset + CHUNK_SIZE);
                    const arrayBuffer = await slice.arrayBuffer();
                    ws.send(arrayBuffer);
                    offset += CHUNK_SIZE;
                }
                ws.send(new Uint8Array(0)); // Signal EOF
            } else if (msg.status === "REJECTED") {
                setStatus("REJECTED");
            } else if (msg.status === "COMPLETED") {
                setStatus("COMPLETED");
            } else if (msg.status === "FAILED") {
                setStatus("FAILED");
                setError(msg.error || "Transfer failed on backend.");
            }
        };

        ws.onerror = () => {
            setStatus("FAILED");
            setError("WebSocket connection error.");
        };
    };

    const resetTransfer = () => {
        setStatus("IDLE");
        setError(null);
        setTransferId(null);
    };

    return { streamFileToBackend, status, error, transferId, resetTransfer, setError };
};