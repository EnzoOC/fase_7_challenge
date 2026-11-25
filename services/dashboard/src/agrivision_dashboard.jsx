import { useState, useRef } from "react";
import CampoIoT from "./campo_iot";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend, LineChart, Line, AreaChart, Area, RadarChart,
  Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis
} from "recharts";

// ─── Constants ──────────────────────────────────────────────────────────────
const CULTURES = ["Tomate", "Batata", "Pimentão", "Milho", "Uva"];
const REGIONS  = ["Zona Norte", "Zona Sul", "Zona Leste", "Zona Oeste", "Centro"];
const MONTHS   = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"];
const DISEASE_COLORS = {
  "Saudável": "#4ade80", "Mancha Bacteriana": "#fbbf24",
  "Requeima": "#f87171", "Ferrugem Comum": "#fb923c", "Podridão Negra": "#c084fc",
};

// ─── CSV Parser ──────────────────────────────────────────────────────────────
// Reads output/resultados_classificacao.csv from classifier_agrivision_v5.py
function parseCSV(text) {
  const lines = text.trim().split(/\r?\n/);
  if (lines.length < 2) return [];
  const headers = lines[0].split(",").map(h => h.trim().replace(/^\uFEFF/, ""));
  return lines.slice(1).map((line, i) => {
    const cols = [];
    let cur = "", inQ = false;
    for (const ch of line) {
      if (ch === '"') { inQ = !inQ; }
      else if (ch === "," && !inQ) { cols.push(cur); cur = ""; }
      else cur += ch;
    }
    cols.push(cur);
    const row = {};
    headers.forEach((h, idx) => { row[h] = (cols[idx] || "").trim(); });

    const cultura   = row["cultura"] || "-";
    const condicao  = (row["condicao_real"] || "").replace("Saudavel", "Saudável");
    const det       = row["categoria_detectada"] || "";
    const label     = (det === "Saudavel" || det === "Saudável") ? "Saudável" : "Doente";
    const confianca = parseFloat(row["confianca_pct"]) || 0;
    const correct   = row["classificacao_correta"] === "Sim";
    const ts        = row["timestamp"] || "";
    const month     = ts ? (MONTHS[parseInt(ts.slice(5,7),10)-1] || "Jan") : "Jan";
    const fname     = row["nome_arquivo"] || "";
    const hash      = [...fname].reduce((a,c) => a + c.charCodeAt(0), 0);
    const region    = REGIONS[hash % REGIONS.length];
    return { id:i+1, cultura, condicao, label, confianca, month, region, correct,
             arquivo: fname, origem: row["pasta_origem_kaggle"] || "-" };
  }).filter(r => r.cultura !== "-");
}

// ─── Simulated fallback ──────────────────────────────────────────────────────
const DISEASES_SIM = {
  "Tomate": ["Saudável","Mancha Bacteriana","Requeima"],
  "Batata": ["Saudável","Requeima"],
  "Pimentão": ["Saudável"],
  "Milho": ["Saudável","Ferrugem Comum"],
  "Uva": ["Saudável","Podridão Negra"],
};
function generateSim(n=100) {
  const seed=[0.417,0.720,0.000,0.302,0.147,0.092,0.186,0.345,0.397,0.539,
              0.617,0.706,0.021,0.969,0.832,0.212,0.182,0.183,0.304,0.524];
  let si=0; const rng=()=>{ const v=seed[si%seed.length]; si++; return v; };
  return Array.from({length:n},(_,i)=>{
    const cultura  = CULTURES[Math.floor(rng()*CULTURES.length)];
    const condicao = DISEASES_SIM[cultura][Math.floor(rng()*DISEASES_SIM[cultura].length)];
    const label    = condicao==="Saudável"?"Saudável":"Doente";
    return {id:i+1,cultura,condicao,label,
      confianca:70+Math.floor(rng()*29),
      month:MONTHS[Math.floor(rng()*12)],
      region:REGIONS[Math.floor(rng()*REGIONS.length)],
      correct:rng()>0.12};
  });
}
const SIM_DATA = generateSim(100);

// ─── Colors ──────────────────────────────────────────────────────────────────
const C = {
  bg:"#0d1a0f", surface:"#122016", card:"#162b1c", border:"#1e3d26",
  accent:"#4ade80", accentDim:"#22c55e", gold:"#fbbf24", red:"#f87171",
  blue:"#60a5fa", purple:"#c084fc", text:"#d1fae5", textDim:"#6ee7b7",
  textMuted:"#374a3b",
};

function KpiCard({ icon, label, value, sub, color="#4ade80" }) {
  return (
    <div style={{ background:C.card, border:`1px solid ${C.border}`, borderRadius:16,
      padding:"24px 28px", display:"flex", flexDirection:"column", gap:8,
      position:"relative", overflow:"hidden" }}>
      <div style={{ position:"absolute", top:-20, right:-20, width:80, height:80,
        borderRadius:"50%", background:color, opacity:0.08 }} />
      <span style={{ fontSize:26 }}>{icon}</span>
      <div style={{ fontSize:36, fontWeight:900, color, fontFamily:"'Courier New',monospace", letterSpacing:-1 }}>{value}</div>
      <div style={{ fontSize:13, color:C.textDim, fontWeight:600, textTransform:"uppercase", letterSpacing:1 }}>{label}</div>
      {sub && <div style={{ fontSize:12, color:C.textMuted }}>{sub}</div>}
    </div>
  );
}

function SectionTitle({ children }) {
  return (
    <div style={{ display:"flex", alignItems:"center", gap:10, marginBottom:16 }}>
      <div style={{ width:3, height:20, background:C.accent, borderRadius:2 }} />
      <span style={{ color:C.text, fontWeight:700, fontSize:15, letterSpacing:0.5,
        textTransform:"uppercase" }}>{children}</span>
    </div>
  );
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background:C.surface, border:`1px solid ${C.border}`, borderRadius:10,
      padding:"10px 14px", fontSize:13, color:C.text }}>
      <div style={{ fontWeight:700, marginBottom:6, color:C.textDim }}>{label}</div>
      {payload.map((p,i)=>(
        <div key={i} style={{ color:p.color, display:"flex", gap:8 }}>
          <span>{p.name}:</span><span style={{ fontWeight:700 }}>{p.value}</span>
        </div>
      ))}
    </div>
  );
};

export default function AgriVisionDashboard() {
  const [filterCulture, setFilterCulture] = useState("Todas");
  const [filterRegion,  setFilterRegion]  = useState("Todas");
  const [tab,           setTab]           = useState("campo");
  const [animKey,       setAnimKey]       = useState(0);
  const [csvData,       setCsvData]       = useState(null);
  const [csvName,       setCsvName]       = useState("");
  const [csvError,      setCsvError]      = useState("");
  const [dragging,      setDragging]      = useState(false);
  const [alertasData,   setAlertasData]   = useState(null);
  const [alertasName,   setAlertasName]   = useState("");
  const [alertasError,  setAlertasError]  = useState("");
  const fileRef = useRef(null);
  const alertasFileRef = useRef(null);
  const liveTimer = useRef(null);
  const [live, setLive] = useState(false);

  const ALL_RECORDS = csvData ?? SIM_DATA;
  const isLive = !!csvData;

  function handleFile(file) {
    if (!file) return;
    if (!file.name.endsWith(".csv")) { setCsvError("Arquivo deve ser .csv"); return; }
    const reader = new FileReader();
    reader.onload = e => {
      try {
        const parsed = parseCSV(e.target.result);
        if (!parsed.length) throw new Error("Nenhum registro válido encontrado.");
        setCsvData(parsed); setCsvName(file.name); setCsvError("");
        setFilterCulture("Todas"); setFilterRegion("Todas");
        setAnimKey(k=>k+1);
      } catch(err) { setCsvError("Erro: " + err.message); }
    };
    reader.readAsText(file, "UTF-8");
  }

  function handleAlertasFile(file) {
    if (!file) return;
    if (!file.name.endsWith(".json")) { setAlertasError("Arquivo deve ser .json"); return; }
    const reader = new FileReader();
    reader.onload = e => {
      try {
        const parsed = JSON.parse(e.target.result);
        if (!parsed.alertas || !Array.isArray(parsed.alertas))
          throw new Error("JSON sem campo 'alertas'.");
        setAlertasData(parsed); setAlertasName(file.name); setAlertasError("");
        setAnimKey(k=>k+1);
      } catch(err) { setAlertasError("Erro: " + err.message); }
    };
    reader.readAsText(file, "UTF-8");
  }

  // ── Modo ao vivo: busca alertas direto da API (Fase 4 — pipeline streaming) ──
  async function fetchAlertasAPI() {
    try {
      const res = await fetch("/api/alertas.json", { cache: "no-store" });
      if (!res.ok) throw new Error("HTTP " + res.status);
      const parsed = await res.json();
      if (!parsed.alertas || !Array.isArray(parsed.alertas))
        throw new Error("Resposta sem campo 'alertas'.");
      setAlertasData(parsed); setAlertasName("API · /api/alertas.json"); setAlertasError("");
    } catch (err) {
      setAlertasError("Falha ao consultar a API (ao vivo): " + err.message);
    }
  }

  function toggleLive() {
    if (live) {
      if (liveTimer.current) clearInterval(liveTimer.current);
      liveTimer.current = null;
      setLive(false);
    } else {
      fetchAlertasAPI();
      liveTimer.current = setInterval(fetchAlertasAPI, 5000);
      setLive(true);
    }
  }

  function stopLive() {
    if (liveTimer.current) clearInterval(liveTimer.current);
    liveTimer.current = null;
    setLive(false);
  }

  const records = ALL_RECORDS.filter(r =>
    (filterCulture==="Todas" || r.cultura===filterCulture) &&
    (filterRegion ==="Todas" || r.region ===filterRegion)
  );

  const total    = records.length;
  const healthy  = records.filter(r=>r.label==="Saudável").length;
  const diseased = records.filter(r=>r.label==="Doente").length;
  const correct  = records.filter(r=>r.correct).length;
  const accuracy = total ? Math.round(correct/total*100) : 0;
  const avgConf  = total ? Math.round(records.reduce((a,b)=>a+b.confianca,0)/total) : 0;

  const pieData = [
    { name:"Saudável", value:healthy },
    { name:"Doente",   value:diseased },
  ];

  const diseaseCount = {};
  records.forEach(r => { diseaseCount[r.condicao]=(diseaseCount[r.condicao]||0)+1; });
  const diseaseData = Object.entries(diseaseCount).sort((a,b)=>b[1]-a[1])
    .map(([name,value])=>({ name, value, fill:DISEASE_COLORS[name]||C.blue }));

  const monthMap = {};
  ALL_RECORDS.forEach(r=>{
    if(!monthMap[r.month]) monthMap[r.month]={saudavel:0,doente:0};
    monthMap[r.month][r.label==="Saudável"?"saudavel":"doente"]++;
  });
  const trendData = MONTHS.map(m=>({
    month:m, Saudável:monthMap[m]?.saudavel||0, Doente:monthMap[m]?.doente||0,
  }));

  const cultureData = CULTURES.map(c=>{
    const s=records.filter(r=>r.cultura===c);
    return { cultura:c, Saudável:s.filter(r=>r.label==="Saudável").length,
             Doente:s.filter(r=>r.label==="Doente").length };
  }).filter(d=>d.Saudável+d.Doente>0);

  const regionData = REGIONS.map(reg=>{
    const s=records.filter(r=>r.region===reg);
    return { region:reg, saudavel:s.filter(r=>r.label==="Saudável").length,
             doente:s.filter(r=>r.label==="Doente").length, total:s.length };
  });

  const radarData = CULTURES.map(c=>{
    const s=ALL_RECORDS.filter(r=>r.cultura===c);
    return { cultura:c, score:s.length?Math.round(s.filter(r=>r.label==="Saudável").length/s.length*100):0 };
  });

  const TABS = ["campo","overview","doenças","tendências","regiões","automação"];
  const TAB_LABELS = { campo:"📡 Campo IoT", overview:"📊 Visão Geral", "doenças":"🦠 Doenças",
    "tendências":"📈 Tendências", "regiões":"🗺️ Regiões",
    "automação":"🤖 Automação" };

  const SEV_COLORS = {
    INFO:    C.accent, BAIXA: "#86efac", MEDIA: C.gold,
    ALTA:    "#fb923c", CRITICA: C.red,
  };
  const SEV_ORDER = { CRITICA:0, ALTA:1, MEDIA:2, BAIXA:3, INFO:4 };

  return (
    <div style={{ minHeight:"100vh", background:C.bg,
      fontFamily:"'Georgia','Times New Roman',serif", color:C.text, padding:"0 0 60px" }}>
      <style>{`
        @keyframes fadeUp{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:none}}
        .c-anim{animation:fadeUp 0.45s ease both}
        ::-webkit-scrollbar{width:6px;background:${C.bg}}
        ::-webkit-scrollbar-thumb{background:${C.border};border-radius:3px}
        .tab-btn{cursor:pointer;transition:color 0.2s}
        .tab-btn:hover{color:${C.accent}!important}
        .fsel{background:${C.card};color:${C.text};border:1px solid ${C.border};
          border-radius:8px;padding:6px 12px;font-size:13px;cursor:pointer;outline:none}
        .fsel:focus{border-color:${C.accentDim}}
        .row-h:hover{background:${C.surface}!important}
        .upload-zone{transition:all 0.2s;cursor:pointer}
        .upload-zone:hover{border-color:${C.accentDim}!important;background:#4ade8008!important}
      `}</style>

      {/* HEADER */}
      <div style={{ background:`linear-gradient(135deg,${C.surface} 0%,#0a1a0c 100%)`,
        borderBottom:`1px solid ${C.border}`, padding:"28px 40px 24px",
        display:"flex", justifyContent:"space-between", alignItems:"flex-end",
        flexWrap:"wrap", gap:20 }}>
        <div>
          <div style={{ display:"flex", alignItems:"center", gap:12, marginBottom:8 }}>
            <span style={{ fontSize:32 }}>🌿</span>
            <div>
              <div style={{ fontSize:28, fontWeight:900, color:C.accent, letterSpacing:-0.5, lineHeight:1 }}>
                AgroSmart
              </div>
              <div style={{ fontSize:11, color:C.textDim, letterSpacing:3, textTransform:"uppercase", marginTop:2 }}>
                Plataforma de Monitoramento Agrícola · AgriVision AI
              </div>
            </div>
          </div>
          {tab!=="campo" && <span style={{
            background: isLive?"#4ade8022":"#fbbf2418",
            color: isLive?C.accent:C.gold,
            border:`1px solid ${isLive?C.accent:C.gold}55`,
            borderRadius:20, padding:"3px 12px", fontSize:11, fontWeight:700,
          }}>
            {isLive ? `● DADOS REAIS · ${csvName}` : "◌ DADOS SIMULADOS · Carregue o CSV real abaixo"}
          </span>}
          {tab==="campo" && <span style={{ background:"#4ade8022", color:C.accent,
            border:`1px solid ${C.accent}55`, borderRadius:20, padding:"3px 12px", fontSize:11, fontWeight:700 }}>
            ● AO VIVO · sensores IoT + motor de decisão R1–R7
          </span>}
        </div>

        {tab!=="campo" && <div style={{ display:"flex", flexDirection:"column", gap:10, alignItems:"flex-end" }}>
          {/* Upload zone */}
          <div
            className="upload-zone"
            onDragOver={e=>{e.preventDefault();setDragging(true)}}
            onDragLeave={()=>setDragging(false)}
            onDrop={e=>{e.preventDefault();setDragging(false);handleFile(e.dataTransfer.files[0])}}
            onClick={()=>fileRef.current?.click()}
            style={{
              border:`1.5px dashed ${dragging?C.accent:C.border}`,
              borderRadius:10, padding:"10px 16px",
              display:"flex", alignItems:"center", gap:10,
              background:dragging?"#4ade8012":"transparent",
              fontSize:12, color:C.textDim,
            }}>
            <span style={{ fontSize:20 }}>📂</span>
            <div>
              <div style={{ fontWeight:700, color:C.text, fontSize:13 }}>
                resultados_classificacao.csv
              </div>
              <div style={{ fontSize:11 }}>
                Clique ou arraste · gerado pelo classifier_agrivision_v5.py
              </div>
            </div>
            {isLive && (
              <button onClick={e=>{e.stopPropagation();setCsvData(null);setCsvName("");}}
                style={{ marginLeft:6, background:"none", border:"none",
                  color:C.red, cursor:"pointer", fontSize:18, lineHeight:1 }}>×</button>
            )}
          </div>
          <input ref={fileRef} type="file" accept=".csv"
            style={{ display:"none" }} onChange={e=>handleFile(e.target.files[0])} />
          {csvError && <div style={{ fontSize:11, color:C.red }}>{csvError}</div>}

          {/* Filters */}
          <div style={{ display:"flex", gap:10, alignItems:"center", flexWrap:"wrap" }}>
            <span style={{ fontSize:11, color:C.textDim }}>Filtrar:</span>
            <select className="fsel" value={filterCulture}
              onChange={e=>{setFilterCulture(e.target.value);setAnimKey(k=>k+1)}}>
              <option value="Todas">Todas as culturas</option>
              {CULTURES.map(c=><option key={c}>{c}</option>)}
            </select>
            <select className="fsel" value={filterRegion}
              onChange={e=>{setFilterRegion(e.target.value);setAnimKey(k=>k+1)}}>
              <option value="Todas">Todas as regiões</option>
              {REGIONS.map(r=><option key={r}>{r}</option>)}
            </select>
            {(filterCulture!=="Todas"||filterRegion!=="Todas") && (
              <button className="fsel"
                onClick={()=>{setFilterCulture("Todas");setFilterRegion("Todas")}}
                style={{ color:C.red, borderColor:C.red }}>
                ✕ Limpar
              </button>
            )}
          </div>
        </div>}
      </div>

      {/* TABS */}
      <div style={{ display:"flex", padding:"0 40px",
        borderBottom:`1px solid ${C.border}`, background:C.surface }}>
        {TABS.map(t=>(
          <button key={t} className="tab-btn" onClick={()=>setTab(t)}
            style={{ background:"none", border:"none", padding:"14px 18px",
              fontSize:12, fontWeight:700, textTransform:"uppercase", letterSpacing:1,
              color:tab===t?C.accent:C.textMuted,
              borderBottom:tab===t?`2px solid ${C.accent}`:"2px solid transparent",
              marginBottom:-1 }}>
            {TAB_LABELS[t]}
          </button>
        ))}
      </div>

      <div style={{ padding:"32px 40px" }} key={animKey}>

        {/* ── TAB: CAMPO IoT (Fase 7) ── */}
        {tab==="campo" && <CampoIoT />}

        {/* ── TAB: OVERVIEW ── */}
        {tab==="overview" && <>
          <div style={{ display:"grid", gridTemplateColumns:"repeat(auto-fit,minmax(190px,1fr))",
            gap:16, marginBottom:28 }}>
            {[
              {icon:"🖼️", label:"Imagens Analisadas", value:total,        color:C.blue,   sub:`de ${ALL_RECORDS.length} total`},
              {icon:"🌱", label:"Saudáveis",          value:healthy,      color:C.accent, sub:`${total?Math.round(healthy/total*100):0}% do total`},
              {icon:"⚠️", label:"Doentes",            value:diseased,     color:C.red,    sub:`${total?Math.round(diseased/total*100):0}% do total`},
              {icon:"🎯", label:"Acurácia Modelo",    value:`${accuracy}%`, color:C.gold,  sub:"classificações corretas"},
              {icon:"💡", label:"Confiança Média",    value:`${avgConf}%`,  color:C.purple,sub:"predict_proba média"},
            ].map((k,i)=>(
              <div key={k.label} className="c-anim" style={{ animationDelay:`${i*70}ms` }}>
                <KpiCard {...k} />
              </div>
            ))}
          </div>

          <div style={{ display:"grid", gridTemplateColumns:"1fr 1.7fr", gap:20, marginBottom:20 }}>
            <div style={{ background:C.card, border:`1px solid ${C.border}`, borderRadius:16, padding:24 }}>
              <SectionTitle>Saudável vs. Doente</SectionTitle>
              <ResponsiveContainer width="100%" height={230}>
                <PieChart>
                  <Pie data={pieData} cx="50%" cy="50%" innerRadius={58} outerRadius={92}
                    paddingAngle={4} dataKey="value"
                    label={({name,percent})=>`${name} ${(percent*100).toFixed(0)}%`}
                    labelLine={{ stroke:C.textMuted }}>
                    <Cell fill={C.accent} stroke={C.bg} strokeWidth={2} />
                    <Cell fill={C.red}    stroke={C.bg} strokeWidth={2} />
                  </Pie>
                  <Tooltip content={<CustomTooltip />} />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div style={{ background:C.card, border:`1px solid ${C.border}`, borderRadius:16, padding:24 }}>
              <SectionTitle>Saúde por Cultura</SectionTitle>
              <ResponsiveContainer width="100%" height={230}>
                <BarChart data={cultureData} barGap={4}>
                  <CartesianGrid strokeDasharray="3 3" stroke={C.border} vertical={false} />
                  <XAxis dataKey="cultura" tick={{ fill:C.textDim, fontSize:12 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill:C.textMuted, fontSize:11 }} axisLine={false} tickLine={false} />
                  <Tooltip content={<CustomTooltip />} />
                  <Legend wrapperStyle={{ fontSize:12, color:C.textDim }} />
                  <Bar dataKey="Saudável" fill={C.accent} radius={[4,4,0,0]} />
                  <Bar dataKey="Doente"   fill={C.red}    radius={[4,4,0,0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div style={{ background:C.card, border:`1px solid ${C.border}`, borderRadius:16, padding:24, marginBottom:20 }}>
            <SectionTitle>Índice de Saúde por Cultura (%)</SectionTitle>
            <ResponsiveContainer width="100%" height={250}>
              <RadarChart data={radarData} cx="50%" cy="50%" outerRadius={95}>
                <PolarGrid stroke={C.border} />
                <PolarAngleAxis dataKey="cultura" tick={{ fill:C.textDim, fontSize:12 }} />
                <PolarRadiusAxis angle={30} domain={[0,100]} tick={{ fill:C.textMuted, fontSize:10 }} />
                <Radar dataKey="score" stroke={C.accent} fill={C.accent} fillOpacity={0.25} />
                <Tooltip content={<CustomTooltip />} />
              </RadarChart>
            </ResponsiveContainer>
          </div>

          <div style={{ background:C.card, border:`1px solid ${C.border}`, borderRadius:16, padding:24 }}>
            <SectionTitle>Últimas 10 Classificações</SectionTitle>
            <div style={{ overflowX:"auto" }}>
              <table style={{ width:"100%", borderCollapse:"collapse", fontSize:13 }}>
                <thead>
                  <tr style={{ borderBottom:`1px solid ${C.border}` }}>
                    {["#","Arquivo","Cultura","Condição","Resultado","Confiança","Correto"].map(h=>(
                      <th key={h} style={{ padding:"8px 12px", color:C.textDim, textAlign:"left",
                        fontWeight:700, fontSize:11, textTransform:"uppercase", letterSpacing:0.8 }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {records.slice(-10).reverse().map(r=>(
                    <tr key={r.id} className="row-h"
                      style={{ borderBottom:`1px solid ${C.textMuted}22`, transition:"background 0.15s" }}>
                      <td style={{ padding:"8px 12px", color:C.textMuted }}>{r.id}</td>
                      <td style={{ padding:"8px 12px", color:C.textMuted, fontSize:11,
                        maxWidth:140, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>
                        {r.arquivo || `img_${r.id}.jpg`}
                      </td>
                      <td style={{ padding:"8px 12px" }}>{r.cultura}</td>
                      <td style={{ padding:"8px 12px", color:DISEASE_COLORS[r.condicao]||C.text }}>{r.condicao}</td>
                      <td style={{ padding:"8px 12px" }}>
                        <span style={{ background:r.label==="Saudável"?"#4ade8022":"#f8717122",
                          color:r.label==="Saudável"?C.accent:C.red,
                          borderRadius:6, padding:"2px 10px", fontSize:11, fontWeight:700 }}>{r.label}</span>
                      </td>
                      <td style={{ padding:"8px 12px", color:r.confianca>=85?C.accent:C.gold }}>{r.confianca}%</td>
                      <td style={{ padding:"8px 12px" }}>{r.correct?"✅":"❌"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>}

        {/* ── TAB: DOENÇAS ── */}
        {tab==="doenças" && <>
          <div style={{ display:"grid", gridTemplateColumns:"1.2fr 1fr", gap:20, marginBottom:20 }}>
            <div style={{ background:C.card, border:`1px solid ${C.border}`, borderRadius:16, padding:24 }}>
              <SectionTitle>Frequência por Anomalia</SectionTitle>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={diseaseData} layout="vertical" barSize={22}>
                  <CartesianGrid strokeDasharray="3 3" stroke={C.border} horizontal={false} />
                  <XAxis type="number" tick={{ fill:C.textMuted, fontSize:11 }} axisLine={false} tickLine={false} />
                  <YAxis dataKey="name" type="category" width={155}
                    tick={{ fill:C.textDim, fontSize:12 }} axisLine={false} tickLine={false} />
                  <Tooltip content={<CustomTooltip />} />
                  <Bar dataKey="value" radius={[0,6,6,0]} name="Ocorrências">
                    {diseaseData.map((e,i)=><Cell key={i} fill={e.fill} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div style={{ background:C.card, border:`1px solid ${C.border}`, borderRadius:16, padding:24 }}>
              <SectionTitle>Distribuição</SectionTitle>
              <ResponsiveContainer width="100%" height={300}>
                <PieChart>
                  <Pie data={diseaseData} cx="50%" cy="50%" outerRadius={105}
                    paddingAngle={3} dataKey="value"
                    label={({percent})=>percent>0.05?`${(percent*100).toFixed(0)}%`:""}>
                    {diseaseData.map((e,i)=><Cell key={i} fill={e.fill} stroke={C.bg} strokeWidth={2} />)}
                  </Pie>
                  <Tooltip content={<CustomTooltip />} />
                  <Legend wrapperStyle={{ fontSize:12, color:C.textDim }} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>
          <div style={{ display:"grid", gridTemplateColumns:"repeat(auto-fit,minmax(190px,1fr))", gap:14 }}>
            {diseaseData.map(d=>{
              const pct=total?Math.round(d.value/total*100):0;
              return (
                <div key={d.name} style={{ background:C.card, border:`1px solid ${d.fill}33`,
                  borderRadius:16, padding:20 }}>
                  <div style={{ fontSize:30, fontWeight:900, color:d.fill,
                    fontFamily:"'Courier New',monospace" }}>{d.value}</div>
                  <div style={{ fontSize:13, color:C.text, margin:"6px 0 4px", fontWeight:600 }}>{d.name}</div>
                  <div style={{ fontSize:11, color:C.textDim }}>{pct}% das imagens</div>
                  <div style={{ marginTop:10, height:4, background:C.border, borderRadius:2 }}>
                    <div style={{ width:`${pct}%`, height:"100%", background:d.fill, borderRadius:2 }} />
                  </div>
                </div>
              );
            })}
          </div>
        </>}

        {/* ── TAB: TENDÊNCIAS ── */}
        {tab==="tendências" && <>
          <div style={{ background:C.card, border:`1px solid ${C.border}`, borderRadius:16, padding:24, marginBottom:20 }}>
            <SectionTitle>Ocorrências Mensais — Saudável vs. Doente</SectionTitle>
            <ResponsiveContainer width="100%" height={300}>
              <AreaChart data={trendData}>
                <defs>
                  <linearGradient id="gs" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor={C.accent} stopOpacity={0.3} />
                    <stop offset="95%" stopColor={C.accent} stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="gd" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor={C.red} stopOpacity={0.3} />
                    <stop offset="95%" stopColor={C.red} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
                <XAxis dataKey="month" tick={{ fill:C.textDim, fontSize:12 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill:C.textMuted, fontSize:11 }} axisLine={false} tickLine={false} />
                <Tooltip content={<CustomTooltip />} />
                <Legend wrapperStyle={{ fontSize:12, color:C.textDim }} />
                <Area type="monotone" dataKey="Saudável" stroke={C.accent} fill="url(#gs)" strokeWidth={2} />
                <Area type="monotone" dataKey="Doente"   stroke={C.red}    fill="url(#gd)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
          <div style={{ background:C.card, border:`1px solid ${C.border}`, borderRadius:16, padding:24 }}>
            <SectionTitle>Taxa de Doenças por Mês (%)</SectionTitle>
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={trendData.map(d=>({
                ...d, taxa:d.Saudável+d.Doente>0?Math.round(d.Doente/(d.Saudável+d.Doente)*100):0
              }))}>
                <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
                <XAxis dataKey="month" tick={{ fill:C.textDim, fontSize:12 }} axisLine={false} tickLine={false} />
                <YAxis unit="%" tick={{ fill:C.textMuted, fontSize:11 }} domain={[0,100]} axisLine={false} tickLine={false} />
                <Tooltip content={<CustomTooltip />} />
                <Line type="monotone" dataKey="taxa" stroke={C.gold} strokeWidth={2.5}
                  dot={{ fill:C.gold, r:4 }} name="Taxa Doença %" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </>}

        {/* ── TAB: AUTOMAÇÃO ── */}
        {tab==="automação" && <>
          {!alertasData && (
            <div style={{ background:C.card, border:`1.5px dashed ${C.border}`,
              borderRadius:16, padding:48, textAlign:"center" }}>
              <div style={{ fontSize:48, marginBottom:12 }}>🤖</div>
              <div style={{ fontSize:18, fontWeight:700, color:C.text, marginBottom:8 }}>
                Motor de Regras — Fase 3
              </div>
              <div style={{ fontSize:13, color:C.textDim, marginBottom:24, lineHeight:1.7 }}>
                Carregue o <code style={{ color:C.accent }}>alertas.json</code> gerado por{" "}
                <code style={{ color:C.accent }}>fase3/motor_regras.py</code> para visualizar
                <br/>os alertas e recomendações disparadas automaticamente pelas regras de decisão.
              </div>
              <div style={{ display:"flex", gap:12, justifyContent:"center", flexWrap:"wrap" }}>
                <button
                  onClick={()=>alertasFileRef.current?.click()}
                  style={{ background:C.accent, color:C.bg, border:"none", padding:"12px 28px",
                    borderRadius:8, fontWeight:700, fontSize:14, cursor:"pointer",
                    fontFamily:"inherit" }}>
                  📂 Carregar alertas.json
                </button>
                <button
                  onClick={toggleLive}
                  style={{ background:"transparent", color:C.accent,
                    border:`1px solid ${C.accent}`, padding:"12px 28px",
                    borderRadius:8, fontWeight:700, fontSize:14, cursor:"pointer",
                    fontFamily:"inherit" }}>
                  🔴 Ao vivo (API)
                </button>
              </div>
              <input ref={alertasFileRef} type="file" accept=".json"
                style={{ display:"none" }}
                onChange={e=>handleAlertasFile(e.target.files[0])} />
              {alertasError && (
                <div style={{ marginTop:14, color:C.red, fontSize:12 }}>{alertasError}</div>
              )}
              <div style={{ marginTop:32, padding:"16px 20px",
                background:C.surface, borderRadius:10, fontSize:11,
                color:C.textDim, textAlign:"left", maxWidth:560, margin:"32px auto 0" }}>
                <div style={{ color:C.text, fontWeight:700, marginBottom:6 }}>Como gerar:</div>
                <pre style={{ margin:0, color:C.textDim, fontSize:11,
                  fontFamily:"'Courier New',monospace" }}>{`cd fase3/
source .venv/bin/activate
python motor_regras.py
# saída em fase3/output/alertas.json`}</pre>
              </div>
            </div>
          )}

          {alertasData && <>
            {/* Cabeçalho do dataset de alertas */}
            <div style={{ background:C.card, border:`1px solid ${C.border}`,
              borderRadius:16, padding:20, marginBottom:20,
              display:"flex", justifyContent:"space-between",
              alignItems:"center", flexWrap:"wrap", gap:12 }}>
              <div>
                <div style={{ fontSize:12, color:C.textDim, letterSpacing:1, textTransform:"uppercase" }}>
                  Arquivo carregado
                </div>
                <div style={{ fontWeight:700, color:C.accent, fontSize:14, marginTop:2 }}>
                  📂 {alertasName}
                </div>
                <div style={{ fontSize:11, color:C.textMuted, marginTop:2 }}>
                  Gerado em {alertasData.gerado_em} · fonte: {alertasData.fonte_csv}
                </div>
              </div>
              <div style={{ display:"flex", gap:10, alignItems:"center" }}>
                {live && (
                  <span style={{ display:"flex", alignItems:"center", gap:6,
                    color:C.red, fontSize:12, fontWeight:700 }}>
                    <span style={{ width:8, height:8, borderRadius:"50%",
                      background:C.red, display:"inline-block",
                      animation:"fadeUp 1s ease infinite alternate" }} />
                    AO VIVO · atualiza a cada 5s
                  </span>
                )}
                <button
                  onClick={toggleLive}
                  style={{ background:"none",
                    border:`1px solid ${live?C.red:C.accent}55`,
                    color:live?C.red:C.accent, padding:"6px 14px", borderRadius:8,
                    cursor:"pointer", fontSize:12, fontFamily:"inherit" }}>
                  {live ? "⏸ Parar ao vivo" : "🔴 Ao vivo (API)"}
                </button>
                <button
                  onClick={()=>{ stopLive(); setAlertasData(null); setAlertasName(""); }}
                  style={{ background:"none", border:`1px solid ${C.red}55`,
                    color:C.red, padding:"6px 14px", borderRadius:8,
                    cursor:"pointer", fontSize:12, fontFamily:"inherit" }}>
                  ✕ Descartar
                </button>
              </div>
            </div>

            {/* KPIs da automação */}
            <div style={{ display:"grid",
              gridTemplateColumns:"repeat(auto-fit,minmax(170px,1fr))",
              gap:14, marginBottom:24 }}>
              <KpiCard icon="📋" label="Total de Alertas"
                value={alertasData.total_alertas} color={C.blue}
                sub={`sobre ${alertasData.total_amostras} amostras`} />
              <KpiCard icon="🚨" label="Críticos"
                value={alertasData.por_severidade?.CRITICA ?? 0}
                color={SEV_COLORS.CRITICA} sub="ação imediata" />
              <KpiCard icon="⚠️" label="Alta severidade"
                value={alertasData.por_severidade?.ALTA ?? 0}
                color={SEV_COLORS.ALTA} sub="intervenção urgente" />
              <KpiCard icon="🟡" label="Média severidade"
                value={alertasData.por_severidade?.MEDIA ?? 0}
                color={SEV_COLORS.MEDIA} sub="monitorar" />
              <KpiCard icon="✅" label="Informativos"
                value={alertasData.por_severidade?.INFO ?? 0}
                color={C.accent} sub="status saudável" />
            </div>

            {/* Lista de alertas, ordenada por severidade */}
            <div style={{ background:C.card, border:`1px solid ${C.border}`,
              borderRadius:16, padding:24, marginBottom:20 }}>
              <SectionTitle>Alertas e Recomendações Disparadas</SectionTitle>
              {alertasData.alertas.length === 0 && (
                <div style={{ padding:20, color:C.textDim, textAlign:"center" }}>
                  Nenhum alerta disparado — lavoura dentro dos parâmetros.
                </div>
              )}
              {[...alertasData.alertas]
                .sort((a,b)=>(SEV_ORDER[a.severidade]??9)-(SEV_ORDER[b.severidade]??9))
                .map((a,i)=>{
                const cor = SEV_COLORS[a.severidade] || C.textDim;
                return (
                  <div key={i} style={{
                    background:`${cor}08`,
                    border:`1px solid ${cor}44`,
                    borderLeft:`4px solid ${cor}`,
                    borderRadius:10, padding:"14px 18px", marginBottom:12 }}>
                    <div style={{ display:"flex", justifyContent:"space-between",
                      alignItems:"center", flexWrap:"wrap", gap:8, marginBottom:6 }}>
                      <div style={{ display:"flex", alignItems:"center", gap:10 }}>
                        <span style={{ fontWeight:900, color:cor, fontSize:13,
                          fontFamily:"'Courier New',monospace" }}>{a.regra_id}</span>
                        <span style={{ color:C.text, fontWeight:700, fontSize:14 }}>
                          {a.regra_nome}
                        </span>
                        <span style={{ color:C.textDim, fontSize:11 }}>
                          · {a.escopo} · <b style={{ color:C.text }}>{a.alvo}</b>
                        </span>
                      </div>
                      <span style={{ background:cor, color:C.bg,
                        borderRadius:6, padding:"2px 10px",
                        fontSize:10, fontWeight:900, letterSpacing:1 }}>
                        {a.severidade}
                      </span>
                    </div>
                    <div style={{ fontSize:13, color:C.text, marginBottom:6 }}>
                      {a.mensagem}
                    </div>
                    <div style={{ fontSize:12, color:C.textDim, lineHeight:1.6 }}>
                      <b style={{ color:C.accent }}>→ Ação:</b> {a.recomendacao}
                    </div>
                    {a.dados_suporte && Object.keys(a.dados_suporte).length > 0 && (
                      <div style={{ marginTop:8, fontSize:11,
                        color:C.textMuted, fontFamily:"'Courier New',monospace" }}>
                        {Object.entries(a.dados_suporte).map(([k,v])=>(
                          <span key={k} style={{ marginRight:14 }}>
                            {k}=<b style={{ color:C.textDim }}>{String(v)}</b>
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {/* Ações automáticas executadas */}
            <div style={{ background:C.card, border:`1px solid ${C.border}`,
              borderRadius:16, padding:24 }}>
              <SectionTitle>Ações Automáticas Executadas</SectionTitle>
              <div style={{ display:"grid",
                gridTemplateColumns:"repeat(auto-fit,minmax(220px,1fr))", gap:12 }}>
                {[
                  { icon:"📄", titulo:"Arquivos .json/.txt",
                    detalhe:`${alertasData.total_alertas * 2} arquivos individuais em fase3/output/alertas/` },
                  { icon:"🗂️", titulo:"alertas.json consolidado",
                    detalhe:"consumido por este painel" },
                  { icon:"📕", titulo:"Relatório PDF",
                    detalhe:"relatorio_intervencao_<data>.pdf" },
                  { icon:"💻", titulo:"Log no terminal",
                    detalhe:"saída estruturada do motor de regras" },
                ].map((a,i)=>(
                  <div key={i} style={{ background:C.surface,
                    border:`1px solid ${C.border}`, borderRadius:10, padding:14 }}>
                    <div style={{ fontSize:24, marginBottom:6 }}>{a.icon}</div>
                    <div style={{ fontSize:13, fontWeight:700, color:C.text }}>{a.titulo}</div>
                    <div style={{ fontSize:11, color:C.textDim, marginTop:4 }}>{a.detalhe}</div>
                  </div>
                ))}
              </div>
            </div>
          </>}
        </>}

        {/* ── TAB: REGIÕES ── */}
        {tab==="regiões" && <>
          <div style={{ display:"grid", gridTemplateColumns:"1.4fr 1fr", gap:20, marginBottom:20 }}>
            <div style={{ background:C.card, border:`1px solid ${C.border}`, borderRadius:16, padding:24 }}>
              <SectionTitle>Ocorrências por Região</SectionTitle>
              <ResponsiveContainer width="100%" height={270}>
                <BarChart data={regionData} barGap={4}>
                  <CartesianGrid strokeDasharray="3 3" stroke={C.border} vertical={false} />
                  <XAxis dataKey="region" tick={{ fill:C.textDim, fontSize:11 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill:C.textMuted, fontSize:11 }} axisLine={false} tickLine={false} />
                  <Tooltip content={<CustomTooltip />} />
                  <Legend wrapperStyle={{ fontSize:12, color:C.textDim }} />
                  <Bar dataKey="saudavel" name="Saudável" fill={C.accent} radius={[4,4,0,0]} />
                  <Bar dataKey="doente"   name="Doente"   fill={C.red}    radius={[4,4,0,0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div style={{ background:C.card, border:`1px solid ${C.border}`, borderRadius:16, padding:24 }}>
              <SectionTitle>Alerta por Região</SectionTitle>
              {regionData.map(r=>{
                const rate=r.total?Math.round(r.doente/r.total*100):0;
                const col=rate>50?C.red:rate>30?C.gold:C.accent;
                return (
                  <div key={r.region} style={{ marginBottom:16 }}>
                    <div style={{ display:"flex", justifyContent:"space-between", marginBottom:4, fontSize:13 }}>
                      <span style={{ color:C.text, fontWeight:600 }}>{r.region}</span>
                      <span style={{ color:col, fontWeight:700 }}>{rate}% doentes</span>
                    </div>
                    <div style={{ height:6, background:C.border, borderRadius:3 }}>
                      <div style={{ width:`${rate}%`, height:"100%", background:col, borderRadius:3 }} />
                    </div>
                    <div style={{ fontSize:11, color:C.textMuted, marginTop:2 }}>
                      {r.total} imagens · {r.saudavel} saudáveis · {r.doente} doentes
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <div style={{ background:C.card, border:`1px solid ${C.border}`, borderRadius:16, padding:24 }}>
            <SectionTitle>💡 Recomendações ao Agricultor</SectionTitle>
            <div style={{ display:"grid", gridTemplateColumns:"repeat(auto-fit,minmax(250px,1fr))", gap:14 }}>
              {regionData.filter(r=>r.total>0).map(r=>{
                const rate=Math.round(r.doente/r.total*100);
                const urgent=rate>50, warn=rate>30;
                return (
                  <div key={r.region} style={{
                    background:urgent?"#f8717110":warn?"#fbbf2410":"#4ade8010",
                    border:`1px solid ${urgent?C.red:warn?C.gold:C.accent}44`,
                    borderRadius:12, padding:16 }}>
                    <div style={{ fontWeight:700, color:urgent?C.red:warn?C.gold:C.accent,
                      fontSize:14, marginBottom:6 }}>
                      {urgent?"🚨":warn?"⚠️":"✅"} {r.region}
                    </div>
                    <div style={{ fontSize:12, color:C.text, lineHeight:1.7 }}>
                      {urgent
                        ? "Ação imediata. Aplicar fungicida/bactericida e isolar lotes afetados. Verificar excesso de irrigação."
                        : warn
                        ? "Monitorar com frequência. Verificar folhas e aplicar tratamento preventivo."
                        : "Lavoura saudável. Manter rotina de monitoramento semanal e irrigação adequada."
                      }
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </>}

      </div>

      <div style={{ textAlign:"center", padding:"20px 40px 0",
        color:C.textMuted, fontSize:11, borderTop:`1px solid ${C.border}` }}>
        AgroSmart · Fase 7 · IoT + Kafka + Motor R1–R7 + AgriVision AI (Random Forest · PlantVillage) ·
        {isLive ? ` Dados reais: ${csvName}` : " Dados simulados para demonstração"}
      </div>
    </div>
  );
}
