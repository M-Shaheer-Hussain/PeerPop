import React, { useState,useEffect } from "react";

function RegisterDevice() {
    const [deviceName, setDeviceName] = useState("");
    const [message, setMessage] = useState("");
    const getDeviceName=async()=>{
        try{
            const response=await fetch("http://localhost:8000/device/me");

            if (response.ok) {
                const data=await response.json();
                setDeviceName(data.device_name);
                return;
            }
            const err = await response.json();
            setMessage(`Registration failed: ${err.detail}`);
        }catch (error){
            setMessage("Device Name could not be fetched")
        }
    }

    useEffect(()=>{
        getDeviceName();
    },[])

    const handleRegister = async (e) => {
        e.preventDefault();

        try {
            const response = await fetch(
                "http://localhost:8000/device/nameupdate",
                {
                    method: "PUT",
                    headers: {
                        "Content-Type": "application/json",
                    },
                    body: JSON.stringify({
                        device_name: deviceName,
                    }),
                }
            );

            if (response.ok) {
                setMessage("Device Name Updated Successfully");
                return;
            }

            const err = await response.json();
            setMessage(`Registration failed: ${err.detail}`);

        } catch (error) {
            setMessage("Something went wrong");
        }
    };

    return (
        <form onSubmit={handleRegister}>
            <input
                className="register-device-name"
                value={deviceName}
                onChange={(e) => setDeviceName(e.target.value)}
            />

            <button type="submit">
                Press to Register
            </button>

            {message && (
                <div className="register-user-cnfrm">
                    <p>{message}</p>
                </div>
            )}
        </form>
    );
}

export default RegisterDevice;