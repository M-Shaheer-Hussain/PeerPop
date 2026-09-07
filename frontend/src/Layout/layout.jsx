import StatusChecker from "../StatusChecker/StatusChecker";
import { Link, Outlet } from "react-router-dom";
import { useContext } from "react";
import { AuthContext } from "../Context/AuthContext";

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
                <Outlet />
            </main>
        </div>
    );
}
export default Layout;