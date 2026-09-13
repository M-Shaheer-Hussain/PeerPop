import StatusChecker from "../StatusChecker/StatusChecker";
import RegisterDevice from "../DeviceRegisteration/DeviceRegisteration";
import { Link, Outlet } from "react-router-dom";
import { useContext } from "react";
import { AuthContext } from "../Context/AuthContext";
import PeerDiscovery from "../PeerDiscovery/PeerDiscovery";
import Dashboard from "../Dashboard/Dashboard";

function Layout() {
    const { user } = useContext(AuthContext);

    return (
        <div className="Global-layout">
            <nav>
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

            <main>
                {!user ? (
                    <Outlet />
                ) : (
                    <>
                        <Dashboard/>
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