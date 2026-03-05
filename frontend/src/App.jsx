import { useEffect, useState } from "react";
import { getHealth } from "./api/http";

export default function App() {
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    getHealth().then(setData).catch((e) => setErr(String(e)));
  }, []);

  return (
    <div style={{ padding: 16 }}>
      <h1>Synergia Portal</h1>
      {err ? <p>Error: {err}</p> : <pre>{JSON.stringify(data, null, 2)}</pre>}
    </div>
  );
}