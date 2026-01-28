import { useMemo, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

export default function App() {
  const [token, setToken] = useState("");
  const defaultEmail = useMemo(() => `user+${Date.now()}@example.com`, []);
  const [email, setEmail] = useState(defaultEmail);
  const [password, setPassword] = useState("password123");
  const [status, setStatus] = useState("");
  const [lastAnalysisId, setLastAnalysisId] = useState(null);
  const [lastReport, setLastReport] = useState(null);

  const register = async () => {
    try {
      setStatus("Регистрация...");
      const r = await fetch(`${API_BASE}/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password })
      });
      const body = await r.text();
      setStatus(r.ok ? body : `ERROR ${r.status}\n${body}`);
    } catch (e) {
      setStatus(`ERROR\n${String(e)}`);
    }
  };

  const login = async () => {
    try {
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
    } catch (e) {
      setToken("");
      setStatus(`ERROR\n${String(e)}`);
    }
  };

  const fetchReport = async (analysisId) => {
    const r = await fetch(`${API_BASE}/report/${analysisId}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {}
    });
    const text = await r.text();
    if (!r.ok) throw new Error(`Report error ${r.status}: ${text}`);
    return JSON.parse(text);
  };

  const upload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      setStatus("Загрузка...");
      setLastReport(null);
      setLastAnalysisId(null);

      const form = new FormData();
      form.append("file", file);

      const r = await fetch(`${API_BASE}/upload/document`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: form
      });

      const bodyText = await r.text();
      if (!r.ok) {
        setStatus(`ERROR ${r.status}\n${bodyText}`);
        return;
      }

      let data;
      try {
        data = JSON.parse(bodyText);
      } catch {
        data = null;
      }

      const analysisId = data?.analysis_id ?? data?.analysisId;
      if (!analysisId) {
        setStatus(`Upload OK, но не удалось разобрать analysis_id:\n${bodyText}`);
        return;
      }

      setLastAnalysisId(analysisId);
      setStatus(`Загружено. analysis_id=${analysisId}. Получаю отчёт...`);

      const report = await fetchReport(analysisId);
      setLastReport(report);
      setStatus(`Готово. analysis_id=${analysisId}`);
    } catch (e) {
      setStatus(`ERROR\n${String(e)}`);
    } finally {
      // чтобы повторная загрузка того же файла снова сработала
      e.target.value = "";
    }
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

      {lastAnalysisId ? (
        <div style={{ marginTop: 16, display: "grid", gap: 8 }}>
          <div>
            <b>analysis_id:</b> {lastAnalysisId}{" "}
            {token ? (
              <a
                href={`${API_BASE}/report/${lastAnalysisId}/pdf`}
                onClick={(ev) => {
                  // нужно прокинуть Authorization — поэтому оставляем ссылку как подсказку
                  // и рекомендуем скачивать через curl/браузер с токеном или сделать кнопку позже.
                  ev.preventDefault();
                  alert(
                    "PDF endpoint готов: /report/{id}/pdf. Для скачивания с токеном проще использовать curl или сделать кнопку с fetch+blob."
                  );
                }}
              >
                (PDF endpoint)
              </a>
            ) : null}
          </div>
          {lastReport ? (
            <>
              <h3 style={{ margin: "8px 0 0" }}>Report</h3>
              <pre
                style={{
                  background: "#111",
                  color: "#ddd",
                  padding: 12,
                  borderRadius: 8,
                  overflow: "auto"
                }}
              >
                {JSON.stringify(lastReport, null, 2)}
              </pre>
            </>
          ) : null}
        </div>
      ) : null}

      <h3>Status</h3>
      <pre style={{ background: "#111", color: "#ddd", padding: 12, borderRadius: 8, overflow: "auto" }}>
        {status}
      </pre>
    </div>
  );
}

