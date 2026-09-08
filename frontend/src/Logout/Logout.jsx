import { useEffect, useContext } from "react";
import { useNavigate } from "react-router-dom";
import { AuthContext } from "../Context/AuthContext";

export default function Logout() {
    const { setUser } = useContext(AuthContext);
    const navigate = useNavigate();

    useEffect(() => {
        fetch("http://localhost:8000/auth/logout", {
            method: "POST",
            credentials: "include"
        }).then(() => {
            setUser(null);
            navigate("/login");
        }).catch((err) => {
            console.error("Logout failed", err);
        });
    }, [navigate, setUser]);

    return <p>Logging out...</p>;
}