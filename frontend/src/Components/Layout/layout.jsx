import StatusChecker from "../StatusChecker/StatusChecker";
import RegisterDevice from "../DeviceRegisteration/DeviceRegisteration";
import { Link, Outlet } from "react-router-dom";
import { useContext } from "react";
import { AuthContext } from "../Context/AuthContext";
import PeerDiscovery from "../PeerDiscovery/PeerDiscovery";

function Layout() {
    const { user } = useContext(AuthContext);

    return (
        <div className="Global-layout">
            <nav style={{ display: "flex", gap: "10px", padding: "10px" }}>
                <Link to="/">Home</Link>

                {!user ? (
                    <>
                        <Link to="/login">Login</Link>
                        <Link to="/register">Register</Link>
                    </>
                ) : (
                    <>
                        <span>Welcome, {user.username}!</span>
                        <Link to="/logout">Logout</Link>
                    </>
                )}
            </nav>

            <StatusChecker />

            <main style={{ padding: "20px" }}>
                {!user ? (
                    <Outlet />
                ) : (
                    <>
                        <RegisterDevice />
                        <PeerDiscovery/>
                        <Outlet />
                    </>
                )}
            </main>
        </div>
    );
}

export default Layout;