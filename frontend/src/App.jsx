import { BrowserRouter as BR, Routes, Route } from "react-router-dom";
import Layout from "./Components/Layout/layout";
import Login from "./Components/Login/Login";
import Register from "./Components/Register/RegisterUser";
import Logout from "./Components/Logout/Logout";
import RegisterDevice from "./Components/DeviceRegisteration/DeviceRegisteration";
import { AuthProvider } from "./Components/Context/AuthContext";

function App() {
  return (
    <AuthProvider>
        <BR>
            <Routes>
                <Route path="/" element={<Layout />}>
                    <Route index element={<h2>L-Share</h2>} />
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