import { useState, useContext } from "react";
import { AuthContext } from "../Context/AuthContext";
import { useNavigate } from "react-router-dom";

export default function Register() {
    const [username, setUsername] = useState("");
    const [password, setPassword] = useState("");
    const { setUser } = useContext(AuthContext);
    const navigate = useNavigate();

    const handleRegister = async (e) => {
        e.preventDefault();
        const response = await fetch("http://localhost:8000/auth/register", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username, password })
        });

        if (response.ok) {
            // Auto-login after successful registration
            await fetch("http://localhost:8000/auth/login", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ username, password }),
                credentials: "include"
            });
            
            const meRes = await fetch("http://localhost:8000/auth/me", { credentials: "include" });
            const userData = await meRes.json();
            setUser(userData);
            navigate("/");
        } else {
            const err = await response.json();
            alert(`Registration failed: ${err.detail}`);
        }
    };

    return (
        <form onSubmit={handleRegister}>
            <h2>Register</h2>
            <input placeholder="Username (min 3 chars)" onChange={(e) => setUsername(e.target.value)} required />
            <input type="password" placeholder="Password (min 8 chars)" onChange={(e) => setPassword(e.target.value)} required />
            <button type="submit">Submit</button>
        </form>
    );
}