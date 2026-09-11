import IncomingRequests from "../IncomingRequests/IncomingRequests"; // Adjust path based on your folder structure
import IncomingTransfers from "../IncomingTransfer/IncomingTransfer";
import FileTransfer from "../FileTransfer/FileTransfer";

function Dashboard() {
    return (
        <div style={{ padding: "20px" }}>
            <h2>L-Share Network</h2>
            <IncomingRequests />
            <br />
            <IncomingTransfers />
            <br />
            <FileTransfer />
            <br />
        </div>
    );
}

export default Dashboard;