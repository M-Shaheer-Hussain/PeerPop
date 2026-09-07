import { BrowserRouter as BR, Routes, Route } from "react-router-dom";
import Layout from "./Layout/layout";
import Login from "./Login/Login";
import Register from "./Register/Register";
import Logout from "./Logout/Logout";
import { AuthProvider } from "./Context/AuthContext";

function App() {
  return (
    <AuthProvider>
        <BR>
            <Routes>
                <Route path="/" element={<Layout />}>
                    <Route index element={<h2>Home Page</h2>} />
                    <Route path="login" element={<Login />} />
                    <Route path="register" element={<Register />} />
                    <Route path="logout" element={<Logout />} />
                </Route>
            </Routes>
        </BR>
    </AuthProvider>
  );
}

export default App;