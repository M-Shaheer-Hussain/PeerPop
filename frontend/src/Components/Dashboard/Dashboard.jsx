import PeerDiscovery from "../PeerDiscovery/PeerDiscovery"; // Adjust path based on your folder structure
import IncomingRequests from "../IncomingRequests/IncomingRequests"; // Adjust path based on your folder structure

function Dashboard() {
    return (
        <div style={{ padding: "20px" }}>
            <h2>L-Share Network</h2>
            <IncomingRequests />
            <br />
            <PeerDiscovery />
        </div>
    );
}

export default Dashboard;