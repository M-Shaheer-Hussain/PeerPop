import React,{useState,useEffect} from "react"
function StatusChecker(){
    const [status,setStatus]=useState("Loading");
    const [message,setMessage]=useState("Checking Backend Status...");
    const [lastchecked,setLastChecked]=useState(null);

    useEffect(()=>{
        const checkbackendhealth=async()=>{
            try{
                const response=await fetch("http://localhost:8000/health")
                const data=await response.json()

                if (response.ok){
                    setStatus("Healthy");
                    setMessage(data.message);
                }
                else{
                    setStatus("error");
                    setMessage(data.detail || "Service Unavailable");
                }
            }catch(error){
                setStatus("Error");
                setMessage("Network Error: Cannot Reach Backend")
            }
            setLastChecked(new Date().toLocaleTimeString());
        };
        checkbackendhealth();

        const intervalid=setInterval(checkbackendhealth,150000);

        return ()=>{
            clearInterval(intervalid);
        }
    },[])

    return(
        <div className="StatusChecker-healthstatus">
            <h3 className="healthstatus-heading">Current Status: {status.toUpperCase()}</h3>
            <p className="health-status-deatil">{message}</p>
            {lastchecked && (
                <p>Last Checked: {lastchecked}</p>
            )}
        </div>
    )
}
export default StatusChecker