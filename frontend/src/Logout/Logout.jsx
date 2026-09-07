import { useEffect, useContext } from "react";
import { useNavigate } from "react-router-dom";
import { AuthContext } from "../Context/AuthContext";

export default function Logout() {
    const { setUser } = useContext(AuthContext);
    const navigate = useNavigate();

    useEffect(() => {
        // Hit the backend to clear the HTTP-only cookie
        fetch("http://localhost:8000/auth/logout", {
            method: "POST",
            credentials: "include"
        }).then(() => {
            // Clear the global user state
            setUser(null);
            // Redirect to the login page
            navigate("/login");
        }).catch((err) => {
            console.error("Logout failed", err);
        });
    }, [navigate, setUser]);

    return <p>Logging out...</p>;
}