// Aba "Campo IoT" — telemetria ao vivo dos talhões + status operacional da plataforma (Fase 7).
// Consome a API AgroSmart (/api/telemetria, /api/status, /api/notificacoes, /api/stats).
import { useEffect, useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine, Legend,
} from "recharts";

const C = {
  surface:"#122016", card:"#162b1c", border:"#1e3d26", accent:"#4ade80", gold:"#fbbf24",
  orange:"#fb923c", red:"#f87171", blue:"#60a5fa", purple:"#c084fc", text:"#d1fae5",
  textDim:"#6ee7b7", textMuted:"#4b6352",
};
const STATUS_COR = { IDEAL:C.accent, ALERTA:C.gold, "CRÍTICO":C.red };
const LINHAS = [C.accent, C.blue, C.gold, C.purple, C.orange];
const CANAL = { whatsapp:"💬 WhatsApp", app:"📱 App", email:"✉️ E-mail" };

async function getJSON(url) {
  const r = await fetch(url, { cache:"no-store" });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

const hora = ts => ts ? new Date(ts).toLocaleTimeString("pt-BR") : "—";

function Titulo({ children }) {
  return (
    <div style={{ display:"flex", alignItems:"center", gap:10, margin:"28px 0 14px" }}>
      <div style={{ width:3, height:20, background:C.accent, borderRadius:2 }} />
      <span style={{ color:C.text, fontWeight:700, fontSize:15, textTransform:"uppercase", letterSpacing:0.5 }}>
        {children}
      </span>
    </div>
  );
}

function Pilula({ ok, children }) {
  const cor = ok ? C.accent : C.gold;
  return (
    <span style={{ border:`1px solid ${cor}66`, background:`${cor}1a`, color:cor, borderRadius:20,
      padding:"3px 12px", fontSize:12, fontWeight:700, whiteSpace:"nowrap" }}>{children}</span>
  );
}

export default function CampoIoT() {
  const [tele, setTele] = useState(null);
  const [status, setStatus] = useState(null);
  const [notif, setNotif] = useState([]);
  const [stats, setStats] = useState(null);
  const [erro, setErro] = useState("");

  useEffect(() => {
    let vivo = true;
    async function atualizar() {
      try {
        const [t, s, n, st] = await Promise.all([
          getJSON("/api/telemetria?historico=40"), getJSON("/api/status"),
          getJSON("/api/notificacoes?limit=12"), getJSON("/api/stats"),
        ]);
        if (!vivo) return;
        setTele(t); setStatus(s); setNotif(n); setStats(st); setErro("");
      } catch (e) {
        if (vivo) setErro(`API indisponível (${e.message}). Suba a plataforma com "docker compose up -d".`);
      }
    }
    atualizar();
    const id = setInterval(atualizar, 3000);
    return () => { vivo = false; clearInterval(id); };
  }, []);

  // Série do gráfico: uma linha por talhão, indexada pela ordem da leitura.
  const serie = [];
  const talhoes = [...new Set((tele?.historico ?? []).map(h => h.talhao))].sort();
  if (tele) {
    const porT = {};
    tele.historico.forEach(h => { (porT[h.talhao] ??= []).push(h); });
    const n = Math.max(0, ...Object.values(porT).map(v => v.length));
    for (let i = 0; i < n; i++) {
      const p = { i };
      talhoes.forEach(t => {
        const h = porT[t][porT[t].length - n + i];
        if (h) { p[t] = Number(h.indice_estresse); p.hora = hora(h.ts_coleta); }
      });
      serie.push(p);
    }
  }

  return (
    <div>
      {erro && (
        <div style={{ background:"#f8717118", border:`1px solid ${C.red}55`, color:C.red,
          borderRadius:10, padding:"12px 16px", marginBottom:16, fontSize:13 }}>⚠️ {erro}</div>
      )}

      {/* Status operacional */}
      <div style={{ background:C.card, border:`1px solid ${C.border}`, borderRadius:14, padding:"16px 20px",
        display:"flex", gap:14, flexWrap:"wrap", alignItems:"center" }}>
        <span style={{ fontWeight:800, fontSize:14 }}>Plataforma:</span>
        <Pilula ok={status?.status === "operacional"}>
          {status ? (status.status === "operacional" ? "● OPERACIONAL" : "● DEGRADADA") : "…"}
        </Pilula>
        {status && Object.entries(status.etapas).map(([k, v]) => (
          <Pilula key={k} ok={v === "ok"}>{k.replaceAll("_", " ")}: {v}</Pilula>
        ))}
        <span style={{ marginLeft:"auto", fontSize:12, color:C.textDim }}>
          {status ? `${status.dispositivos_ativos} nós ativos · ${status.leituras_ultimo_min} leituras/min · `
            + `${status.rejeitadas_10min} rejeitadas (10 min)` : ""}
        </span>
        <a href="http://localhost:3000" target="_blank" rel="noreferrer"
          style={{ color:C.blue, fontSize:12, fontWeight:700 }}>📈 Grafana ↗</a>
      </div>

      {stats && (
        <div style={{ display:"grid", gridTemplateColumns:"repeat(auto-fill,minmax(160px,1fr))", gap:12, marginTop:14 }}>
          {[
            ["Leituras processadas", stats.total_leituras, C.blue],
            ["Rejeitadas (dado inválido)", stats.leituras_rejeitadas, C.gold],
            ["Alertas R7 emitidos", stats.alertas_r7, C.orange],
            ["Notificações enviadas", stats.notificacoes_enviadas, C.accent],
            ["Casos no event log", stats.casos_event_log, C.purple],
          ].map(([l, v, cor]) => (
            <div key={l} style={{ background:C.card, border:`1px solid ${C.border}`, borderRadius:12, padding:"12px 16px" }}>
              <div style={{ fontSize:26, fontWeight:900, color:cor, fontFamily:"'Courier New',monospace" }}>
                {Number(v).toLocaleString("pt-BR")}
              </div>
              <div style={{ fontSize:11, color:C.textDim, textTransform:"uppercase", letterSpacing:0.8 }}>{l}</div>
            </div>
          ))}
        </div>
      )}

      <Titulo>📡 Talhões — última leitura</Titulo>
      <div style={{ display:"grid", gridTemplateColumns:"repeat(auto-fill,minmax(220px,1fr))", gap:14 }}>
        {(tele?.ultimas ?? []).map(u => {
          const cor = STATUS_COR[u.status_solo] ?? C.textDim;
          return (
            <div key={u.device_id} style={{ background:C.card, border:`1px solid ${cor}55`, borderRadius:14,
              padding:"16px 18px", borderTop:`4px solid ${cor}` }}>
              <div style={{ display:"flex", justifyContent:"space-between", alignItems:"baseline" }}>
                <span style={{ fontWeight:900, fontSize:18 }}>{u.talhao}</span>
                <span style={{ color:cor, fontWeight:800, fontSize:12 }}>{u.status_solo}</span>
              </div>
              <div style={{ fontSize:12, color:C.textDim, marginBottom:10 }}>{u.regiao} · {u.cultura}</div>
              <div style={{ fontSize:30, fontWeight:900, color:cor, fontFamily:"'Courier New',monospace" }}>
                {Number(u.indice_estresse).toFixed(1)}
              </div>
              <div style={{ fontSize:11, color:C.textMuted, marginBottom:10 }}>índice de estresse hídrico</div>
              <div style={{ display:"flex", justifyContent:"space-between", fontSize:13 }}>
                <span>🌡️ {Number(u.temperatura_c).toFixed(1)}°C</span>
                <span>💧 {Number(u.umidade_solo_pct).toFixed(0)}%</span>
                <span>☀️ {Number(u.luminosidade_pct).toFixed(0)}%</span>
              </div>
              <div style={{ fontSize:11, color:C.textMuted, marginTop:8 }}>{u.device_id} · {hora(u.ts_coleta)}</div>
            </div>
          );
        })}
      </div>

      <Titulo>📈 Índice de estresse hídrico — tempo real</Titulo>
      <div style={{ background:C.card, border:`1px solid ${C.border}`, borderRadius:14, padding:"16px 8px 8px" }}>
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={serie}>
            <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
            <XAxis dataKey="hora" stroke={C.textDim} fontSize={11} minTickGap={40} />
            <YAxis stroke={C.textDim} fontSize={11} domain={[0, "auto"]} />
            <Tooltip contentStyle={{ background:C.surface, border:`1px solid ${C.border}`, color:C.text }} />
            <Legend />
            <ReferenceLine y={40} stroke={C.gold} strokeDasharray="6 4" label={{ value:"ALERTA", fill:C.gold, fontSize:11 }} />
            <ReferenceLine y={60} stroke={C.red} strokeDasharray="6 4" label={{ value:"CRÍTICO", fill:C.red, fontSize:11 }} />
            {talhoes.map((t, i) => (
              <Line key={t} type="monotone" dataKey={t} stroke={LINHAS[i % LINHAS.length]} dot={false}
                strokeWidth={2} isAnimationActive={false} />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>

      <Titulo>🔔 Últimas notificações enviadas ao produtor</Titulo>
      <div style={{ background:C.card, border:`1px solid ${C.border}`, borderRadius:14, overflow:"hidden" }}>
        <table style={{ width:"100%", borderCollapse:"collapse", fontSize:13 }}>
          <thead>
            <tr style={{ background:C.surface, color:C.textDim, textAlign:"left" }}>
              {["Hora", "Canal", "Regra", "Severidade", "Alvo", "Tentativas"].map(h => (
                <th key={h} style={{ padding:"10px 14px", fontWeight:700 }}>{h}</th>))}
            </tr>
          </thead>
          <tbody>
            {notif.length === 0 && (
              <tr><td colSpan={6} style={{ padding:16, color:C.textMuted }}>Nenhuma notificação ainda.</td></tr>
            )}
            {notif.map(n => (
              <tr key={n.id} style={{ borderTop:`1px solid ${C.border}` }}>
                <td style={{ padding:"9px 14px" }}>{hora(n.enviada_em)}</td>
                <td style={{ padding:"9px 14px" }}>{CANAL[n.canal] ?? n.canal}</td>
                <td style={{ padding:"9px 14px", fontWeight:700 }}>{n.regra_id}</td>
                <td style={{ padding:"9px 14px", color:n.severidade === "CRITICA" ? C.red : C.gold }}>{n.severidade}</td>
                <td style={{ padding:"9px 14px" }}>{n.alvo}</td>
                <td style={{ padding:"9px 14px", color:n.tentativas > 1 ? C.gold : C.text }}>{n.tentativas}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
