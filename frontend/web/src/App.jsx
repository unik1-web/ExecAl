import { useMemo, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

export default function App() {
  const [token, setToken] = useState("");
  const defaultEmail = useMemo(() => `user+${Date.now()}@example.com`, []);
  const [email, setEmail] = useState(defaultEmail);
  const [password, setPassword] = useState("password123");
  const [status, setStatus] = useState("");

  const register = async () => {
    setStatus("Регистрация...");
    const r = await fetch(`${API_BASE}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password })
    });
    const body = await r.text();
    setStatus(r.ok ? body : `ERROR ${r.status}\n${body}`);
  };

  const login = async () => {
    setStatus("Вход...");
    const r = await fetch(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password })
    });
    const bodyText = await r.text();
    let data;
    try {
      data = JSON.parse(bodyText);
    } catch {
      data = null;
    }
    if (!r.ok) {
      setToken("");
      setStatus(`ERROR ${r.status}\n${bodyText}`);
      return;
    }
    setToken(data?.access_token ?? "");
    setStatus(JSON.stringify(data, null, 2));
  };

  const upload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setStatus("Загрузка...");
    const form = new FormData();
    form.append("file", file);
    const r = await fetch(`${API_BASE}/upload/document`, {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: form
    });
    setStatus(await r.text());
  };

  return (
    <div style={{ maxWidth: 720, margin: "40px auto", fontFamily: "system-ui" }}>
      <h1>ExecAl (MVP)</h1>
      <p>Минимальный веб-скелет: регистрация/вход + загрузка документа.</p>

      <div style={{ display: "grid", gap: 8 }}>
        <label>
          Email{" "}
          <input value={email} onChange={(e) => setEmail(e.target.value)} style={{ width: "100%" }} />
        </label>
        <button onClick={() => setEmail(`user+${Date.now()}@example.com`)} style={{ width: "fit-content" }}>
          Generate new email
        </button>
        <label>
          Password{" "}
          <input
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            style={{ width: "100%" }}
            type="password"
          />
        </label>
        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={register}>Register</button>
          <button onClick={login}>Login</button>
        </div>
        <label>
          Upload document{" "}
          <input type="file" accept=".png,.jpg,.jpeg,.pdf" onChange={upload} />
        </label>
      </div>

      <h3>Status</h3>
      <pre style={{ background: "#111", color: "#ddd", padding: 12, borderRadius: 8, overflow: "auto" }}>
        {status}
      </pre>
    </div>
  );
}

