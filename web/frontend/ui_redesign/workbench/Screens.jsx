// Diverge Workbench — All Screen Components
// Exports: LoginScreen, HomeScreen, TaskScreen, ScreenerScreen, AssetsScreen

/* ── helpers ── */
function MetricCard({ label, value, meta }) {
  return (
    <div style={{border:"1px solid rgba(22,34,51,.08)",borderRadius:22,background:"rgba(255,255,255,0.82)",backdropFilter:"blur(10px)",boxShadow:"0 2px 0 rgba(255,255,255,.9) inset,0 16px 32px rgba(18,28,41,.06)",padding:"16px 18px"}}>
      <div style={{fontSize:10,fontWeight:700,letterSpacing:"0.2em",textTransform:"uppercase",color:"#6b7e8a"}}>{label}</div>
      <div style={{fontSize:"2rem",fontWeight:600,letterSpacing:"-0.03em",color:"#0f1923",marginTop:8,lineHeight:1}}>{value}</div>
      {meta && <div style={{fontSize:12,color:"#7a8fa0",marginTop:5}}>{meta}</div>}
    </div>
  );
}

function Badge({ children, variant = "default" }) {
  const styles = {
    default: {background:"rgba(93,116,112,.16)",borderColor:"rgba(28,36,48,.16)",color:"#111923"},
    secondary:{background:"var(--surface)",borderColor:"var(--border)",color:"var(--muted)"},
    success:  {background:"rgba(46,118,83,.08)",borderColor:"rgba(46,118,83,.2)",color:"#2e7653"},
    danger:   {background:"rgba(163,53,53,.08)",borderColor:"rgba(163,53,53,.2)",color:"#a33535"},
    info:     {background:"rgba(28,56,83,.08)",borderColor:"rgba(28,56,83,.16)",color:"var(--accent)"},
    warn:     {background:"rgba(181,121,34,.1)",borderColor:"rgba(181,121,34,.24)",color:"rgb(146,91,22)"},
    canceled: {background:"rgba(100,116,139,.1)",borderColor:"rgba(100,116,139,.22)",color:"#475569"},
  };
  return (
    <span style={{display:"inline-flex",alignItems:"center",borderRadius:9999,padding:"3px 11px",fontSize:10,fontWeight:700,letterSpacing:"0.16em",textTransform:"uppercase",border:"1px solid",...styles[variant]}}>{children}</span>
  );
}

function Btn({ children, onClick, variant = "primary", size = "default", disabled, style = {} }) {
  const base = {display:"inline-flex",alignItems:"center",justifyContent:"center",gap:6,borderRadius:9999,fontFamily:"var(--font-body)",fontWeight:600,fontSize:14,letterSpacing:"0.04em",cursor:"pointer",border:"1px solid",transition:"filter 150ms",whiteSpace:"nowrap",background:"none",...style};
  const vars = {
    primary:   {background:"var(--primary)",color:"var(--primary-foreground)",borderColor:"var(--primary)",boxShadow:"0 14px 28px rgba(28,36,48,.16)",height:44,padding:"0 20px"},
    secondary: {background:"var(--surface)",color:"var(--text)",borderColor:"var(--border)",boxShadow:"0 10px 22px rgba(18,28,41,.06)",height:44,padding:"0 20px"},
    accent:    {background:"var(--accent)",color:"white",borderColor:"var(--accent)",boxShadow:"0 14px 28px rgba(93,116,112,.18)",height:44,padding:"0 20px"},
    ghost:     {background:"transparent",color:"var(--muted)",borderColor:"transparent",height:44,padding:"0 16px"},
  };
  const sizes = {
    default: {},
    sm: {height:36,padding:"0 16px",fontSize:11,fontWeight:700,letterSpacing:"0.18em",textTransform:"uppercase"},
  };
  return (
    <button onClick={onClick} disabled={disabled}
      style={{...base,...vars[variant],...sizes[size],opacity:disabled?0.55:1,pointerEvents:disabled?"none":"auto"}}
      onMouseEnter={e=>e.currentTarget.style.filter="brightness(0.985)"}
      onMouseLeave={e=>e.currentTarget.style.filter=""}
      onMouseDown={e=>e.currentTarget.style.filter="brightness(0.96)"}
      onMouseUp={e=>e.currentTarget.style.filter="brightness(0.985)"}
    >{children}</button>
  );
}

/* ── LOGIN ── */
function LoginScreen({ onLogin }) {
  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [loading, setLoading] = React.useState(false);

  const handleSubmit = (e) => {
    e.preventDefault();
    setLoading(true);
    setTimeout(() => { setLoading(false); onLogin(); }, 900);
  };

  return (
    <div style={{minHeight:"100vh",display:"flex",alignItems:"center",justifyContent:"center",padding:"24px",background:"linear-gradient(180deg,#fbf8f2 0%,#f5f2ec 100%)"}}>
      <div className="fade-in" style={{width:"100%",maxWidth:820,border:"1px solid rgba(22,34,51,.1)",borderRadius:34,background:"rgba(255,253,248,0.96)",boxShadow:"0 40px 80px rgba(18,28,41,0.1)",overflow:"hidden",display:"grid",gridTemplateColumns:"1.1fr 0.9fr"}}>
        {/* Left brand panel */}
        <div style={{padding:"48px 40px",display:"flex",alignItems:"center",justifyContent:"center",borderRight:"1px solid rgba(28,36,48,0.07)",background:"linear-gradient(180deg,rgba(255,253,248,0.9) 0%,rgba(245,242,236,0.95) 100%)",position:"relative"}}>
          <div style={{textAlign:"center"}}>
            <DivergeMark size={160} color="#1c2430" />
            <h1 style={{fontFamily:"var(--font-heading)",fontSize:"3.5rem",fontWeight:600,color:"var(--text)",marginTop:20,letterSpacing:"-0.02em"}}>Diverge</h1>
            <p style={{fontSize:13,color:"var(--muted)",marginTop:10,letterSpacing:"0.04em"}}>Financial Research Workbench</p>
          </div>
        </div>
        {/* Right form panel */}
        <div style={{padding:"48px 40px"}}>
          <div style={{fontSize:11,fontWeight:700,letterSpacing:"0.34em",textTransform:"uppercase",color:"var(--muted)"}}>Login</div>
          <h2 style={{fontFamily:"var(--font-heading)",fontSize:"1.9rem",fontWeight:700,color:"var(--text)",marginTop:10,letterSpacing:"-0.02em"}}>Workspace credentials</h2>
          <p style={{fontSize:13,color:"var(--muted)",marginTop:8,lineHeight:1.6}}>Sign in to continue to your requested page.</p>

          <form onSubmit={handleSubmit} style={{marginTop:28,display:"flex",flexDirection:"column",gap:14}}>
            <label style={{display:"block"}}>
              <div style={{fontSize:10,fontWeight:700,textTransform:"uppercase",letterSpacing:"0.26em",color:"var(--muted)",marginBottom:6}}>Email</div>
              <input type="email" placeholder="analyst@diverge.local" value={email} onChange={e=>setEmail(e.target.value)} required />
            </label>
            <label style={{display:"block"}}>
              <div style={{fontSize:10,fontWeight:700,textTransform:"uppercase",letterSpacing:"0.26em",color:"var(--muted)",marginBottom:6}}>Password</div>
              <input type="password" placeholder="Enter your password" value={password} onChange={e=>setPassword(e.target.value)} required />
            </label>
            <Btn variant="primary" style={{width:"100%",marginTop:4}}>{loading ? "Signing in…" : "Sign In"}</Btn>
          </form>

          <div style={{marginTop:16,border:"1px dashed var(--border)",borderRadius:18,padding:"12px 14px",fontSize:12,color:"var(--muted)"}}>Need access help? Ask your workspace admin.</div>
        </div>
      </div>
    </div>
  );
}

/* ── HOME ── */
const SAMPLE_REPORTS = [
  {id:"rpt-2026-04-27-nvda-001",ticker:"NVDA",visibility:"workspace",date:"Apr 27, 2026"},
  {id:"rpt-2026-04-20-aapl-002",ticker:"AAPL",visibility:"private",date:"Apr 20, 2026"},
  {id:"rpt-2026-04-15-tsm-003",ticker:"TSM",visibility:"workspace",date:"Apr 15, 2026"},
  {id:"rpt-2026-04-10-msft-004",ticker:"MSFT",visibility:"private",date:"Apr 10, 2026"},
  {id:"rpt-2026-04-05-googl-005",ticker:"GOOGL",visibility:"private",date:"Apr 5, 2026"},
];

function HomeScreen({ onNewAnalysis, onOpenTask }) {
  const [scope, setScope] = React.useState("all");
  const [query, setQuery] = React.useState("");
  const filtered = SAMPLE_REPORTS.filter(r =>
    (!query || r.ticker.toLowerCase().includes(query.toLowerCase())) &&
    (scope === "all" || (scope === "mine" && r.visibility === "private") || (scope === "workspace" && r.visibility === "workspace"))
  );

  return (
    <main style={{flex:1,overflowY:"auto",padding:"24px 28px 40px"}}>
      <div style={{maxWidth:960,margin:"0 auto",display:"flex",flexDirection:"column",gap:20}}>
        {/* Hero card */}
        <div className="card fade-in" style={{padding:"28px 32px"}}>
          <div style={{display:"flex",alignItems:"flex-end",justifyContent:"space-between",gap:16,flexWrap:"wrap"}}>
            <div>
              <div className="kicker">Analysis</div>
              <h1 style={{fontSize:"clamp(1.8rem,3.2vw,2.8rem)",fontWeight:600,letterSpacing:"-0.025em",color:"#0f1923",marginTop:10,lineHeight:1.1}}>Analysis workspace</h1>
              <p style={{fontSize:13,color:"#566779",marginTop:10,lineHeight:1.7,maxWidth:480}}>Search reports and continue existing coverage.</p>
            </div>
            <div style={{display:"flex",gap:10,flexWrap:"wrap"}}>
              <Btn variant="primary" onClick={onNewAnalysis}>New Analysis</Btn>
              <Btn variant="secondary">View Activity</Btn>
            </div>
          </div>
          <div style={{display:"grid",gridTemplateColumns:"repeat(3,1fr)",gap:12,marginTop:20}}>
            <MetricCard label="Report Library" value={`${SAMPLE_REPORTS.length}`} meta="Total indexed reports" />
            <MetricCard label="Tracked Tickers" value={`${new Set(SAMPLE_REPORTS.map(r=>r.ticker)).size}`} meta="Coverage names in library" />
            <MetricCard label="Active Research" value="2" meta="In-flight analysis jobs" />
          </div>
          <div style={{marginTop:18,borderRadius:24,border:"1px solid var(--border)",background:"rgba(255,255,255,0.88)",padding:"16px 18px"}}>
            <div style={{fontSize:10,fontWeight:700,textTransform:"uppercase",letterSpacing:"0.22em",color:"#64748b"}}>Search reports</div>
            <input type="search" value={query} onChange={e=>setQuery(e.target.value)} placeholder="Ticker or report id" style={{marginTop:10,borderColor:"rgba(22,34,51,0.18)",background:"var(--surface-strong)"}} />
          </div>
        </div>

        {/* Two-column lower */}
        <div style={{display:"grid",gridTemplateColumns:"1.1fr 0.9fr",gap:20}}>
          {/* Report list */}
          <div className="viewer fade-in" style={{padding:"22px 24px"}}>
            <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",gap:12,marginBottom:14}}>
              <div>
                <div className="section-lbl">{query ? "Matching Reports" : "Recent Reports"}</div>
                <h2 style={{fontSize:"1.3rem",fontWeight:600,letterSpacing:"-0.02em",color:"#0f1923",marginTop:6}}>{query ? `${filtered.length} matching` : "Jump back into coverage"}</h2>
              </div>
            </div>
            <div style={{display:"flex",gap:8,flexWrap:"wrap",marginBottom:14}}>
              {["all","mine","workspace"].map(s => (
                <button key={s} onClick={()=>setScope(s)} className={"pill-tab"+(scope===s?" active":"")} style={{fontFamily:"var(--font-body)",cursor:"pointer",border:"1px solid",borderColor:scope===s?"rgba(28,56,83,.92)":"rgba(22,34,51,.1)",background:scope===s?"#1c2430":"rgba(255,255,255,.68)",color:scope===s?"#fff9f1":"#4b5a6b",borderRadius:9999,height:36,padding:"0 14px",fontSize:11,fontWeight:700,letterSpacing:"0.16em",textTransform:"uppercase"}}>
                  {s.charAt(0).toUpperCase()+s.slice(1)}
                </button>
              ))}
            </div>
            <div style={{display:"flex",flexDirection:"column",gap:8}}>
              {filtered.length === 0 ? (
                <div style={{borderRadius:22,border:"1px dashed var(--border)",background:"var(--surface-strong)",padding:"20px 18px",fontSize:13,color:"var(--muted)"}}>No reports match this search.</div>
              ) : filtered.map(r => (
                <div key={r.id} onClick={()=>onOpenTask(r)} style={{display:"flex",alignItems:"center",justifyContent:"space-between",gap:12,borderRadius:22,border:"1px solid var(--border)",background:"rgba(255,255,255,0.88)",padding:"13px 16px",cursor:"pointer",transition:"border-color 150ms"}}
                  onMouseEnter={e=>e.currentTarget.style.borderColor="rgba(93,116,112,.28)"}
                  onMouseLeave={e=>e.currentTarget.style.borderColor="rgba(28,36,48,.12)"}
                >
                  <div>
                    <div style={{display:"flex",alignItems:"center",gap:8}}>
                      <span style={{fontSize:15,fontWeight:700,color:"#0f1923"}}>{r.ticker}</span>
                      <Badge variant={r.visibility === "workspace" ? "success" : "secondary"}>{r.visibility}</Badge>
                    </div>
                    <div style={{fontFamily:"var(--font-mono)",fontSize:10,color:"#7a8fa0",marginTop:3}}>{r.id}</div>
                  </div>
                  <span style={{fontSize:10,fontWeight:700,letterSpacing:"0.16em",textTransform:"uppercase",color:"var(--accent)"}}>Open</span>
                </div>
              ))}
            </div>
          </div>

          {/* Coverage map */}
          <div style={{display:"flex",flexDirection:"column",gap:14}}>
            <div className="card fade-in" style={{padding:"20px 22px"}}>
              <div className="section-lbl">Tracked Tickers</div>
              <h2 style={{fontSize:"1.2rem",fontWeight:600,letterSpacing:"-0.02em",color:"#0f1923",marginTop:6}}>Coverage map</h2>
              <div style={{display:"flex",flexWrap:"wrap",gap:8,marginTop:14}}>
                {[...new Set(SAMPLE_REPORTS.map(r=>r.ticker))].map(t => (
                  <button key={t} onClick={()=>setQuery(t)} style={{borderRadius:9999,border:"1px solid var(--border)",background:"var(--surface)",padding:"6px 14px",fontSize:12,fontWeight:700,letterSpacing:"0.08em",color:"#334155",fontFamily:"var(--font-body)",cursor:"pointer",transition:"all 150ms"}}
                    onMouseEnter={e=>e.currentTarget.style.color="var(--primary)"}
                    onMouseLeave={e=>e.currentTarget.style.color="#334155"}
                  >{t}</button>
                ))}
              </div>
            </div>
            <div className="card fade-in" style={{padding:"20px 22px"}}>
              <div className="section-lbl">Coverage Snapshot</div>
              <div style={{marginTop:12,borderRadius:20,border:"1px solid var(--border)",background:"rgba(255,255,255,0.88)",padding:"14px 16px"}}>
                <p style={{fontSize:13,fontWeight:600,color:"#0f1923"}}>Use the analysis rail as the reports home base.</p>
                <p style={{fontSize:12,color:"#566779",marginTop:8,lineHeight:1.7}}>The library currently tracks {SAMPLE_REPORTS.length} reports across {new Set(SAMPLE_REPORTS.map(r=>r.ticker)).size} tickers.</p>
                <div style={{marginTop:10}}><Badge variant="secondary">Latest · {SAMPLE_REPORTS[0].ticker}</Badge></div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}

/* ── TASK ── */
const STAGES = ["Analysts","Research","Trading","Risk","Portfolio","Summary"];
const MOCK_EVENTS = [
  {ts:"10:42:18",agent:"Portfolio Manager",msg:"Final portfolio decision synthesized. Report generation initiated."},
  {ts:"10:41:55",agent:"Risk Analyst",msg:"Risk assessment completed. Max drawdown within acceptable bounds."},
  {ts:"10:40:22",agent:"Trader",msg:"Trade recommendation: BUY with 3-month horizon. Conviction: HIGH."},
  {ts:"10:38:11",agent:"Bear Researcher",msg:"Counter-thesis drafted. Valuation appears stretched at 28x forward."},
  {ts:"10:36:44",agent:"Bull Researcher",msg:"Bull case confirmed: NVDA's data center TAM expansion justifies premium."},
  {ts:"10:33:02",agent:"Fundamental Analyst",msg:"DCF analysis complete. Base-case fair value: $142–$158 range."},
];

function TaskScreen({ report, onBack }) {
  const ticker = report?.ticker || "NVDA";
  const stageStatus = {Analysts:"completed",Research:"completed",Trading:"completed",Risk:"completed",Portfolio:"completed",Summary:"completed"};
  return (
    <main style={{flex:1,overflowY:"auto",padding:"20px 24px 40px"}}>
      <div style={{maxWidth:900,margin:"0 auto",display:"flex",flexDirection:"column",gap:16}}>
        <div className="card fade-in" style={{padding:"24px 28px"}}>
          <div style={{display:"flex",alignItems:"flex-start",justifyContent:"space-between",gap:16,flexWrap:"wrap"}}>
            <div>
              <div className="kicker">Background Task</div>
              <h1 style={{fontFamily:"var(--font-heading)",fontSize:"2rem",fontWeight:700,color:"#0f1923",marginTop:10,letterSpacing:"-0.02em"}}>{ticker}</h1>
              <p style={{fontSize:13,color:"#566779",marginTop:6,lineHeight:1.7}}>Tracking Apr 27, 2026 research flow across analyst, debate, trading, and portfolio stages.</p>
            </div>
            <div style={{display:"flex",gap:10,flexWrap:"wrap",alignItems:"center"}}>
              <Badge variant="success">Completed</Badge>
              <Btn variant="secondary" size="sm" onClick={onBack}>← Back</Btn>
              <Btn variant="accent">View Report</Btn>
            </div>
          </div>

          <div style={{display:"grid",gridTemplateColumns:"repeat(6,1fr)",gap:10,marginTop:20}}>
            {STAGES.map(stage => (
              <div key={stage} style={{borderRadius:20,border:"1px solid rgba(46,118,83,.2)",background:"rgba(46,118,83,.07)",padding:"12px 12px"}}>
                <div style={{fontSize:9,fontWeight:700,letterSpacing:"0.22em",textTransform:"uppercase",color:"#64748b"}}>{stage}</div>
                <div style={{display:"flex",alignItems:"center",gap:6,marginTop:8}}>
                  <span style={{width:9,height:9,borderRadius:"50%",background:"var(--success)",flexShrink:0,display:"block"}}></span>
                  <span style={{fontSize:11,fontWeight:600,color:"#334155"}}>Done</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="card fade-in" style={{padding:"22px 26px"}}>
          <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",gap:12,marginBottom:16}}>
            <div>
              <div className="kicker">Event Log</div>
              <h2 style={{fontFamily:"var(--font-heading)",fontSize:"1.4rem",fontWeight:700,color:"#0f1923",marginTop:8}}>Live progress feed</h2>
            </div>
            <Badge variant="secondary">{MOCK_EVENTS.length} updates</Badge>
          </div>
          <div style={{display:"flex",flexDirection:"column",gap:8,maxHeight:300,overflowY:"auto"}}>
            {MOCK_EVENTS.map((ev,i) => (
              <div key={i} style={{borderRadius:20,border:"1px solid var(--border)",background:"var(--surface-strong)",padding:"12px 16px"}}>
                <div style={{display:"flex",gap:12,fontSize:10,fontWeight:700,letterSpacing:"0.2em",textTransform:"uppercase",color:"#94a3b8"}}>
                  <span>{ev.ts}</span><span>{ev.agent}</span>
                </div>
                <p style={{fontSize:13,color:"#334155",marginTop:6,lineHeight:1.65}}>{ev.msg}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </main>
  );
}

/* ── SCREENER ── */
const RUNS = [
  {id:"run-2026-04-27",markets:["us"],date:"Apr 27, 2026",candidates:28,status:"completed"},
  {id:"run-2026-04-20",markets:["cn","us"],date:"Apr 20, 2026",candidates:44,status:"completed"},
  {id:"run-2026-04-13",markets:["cn"],date:"Apr 13, 2026",candidates:31,status:"completed"},
];

function ScreenerScreen({ onNewScreener }) {
  return (
    <main style={{flex:1,overflowY:"auto",padding:"24px 28px 40px"}}>
      <div style={{maxWidth:900,margin:"0 auto",display:"flex",flexDirection:"column",gap:20}}>
        <div className="card fade-in" style={{padding:"28px 32px"}}>
          <div style={{display:"flex",alignItems:"flex-end",justifyContent:"space-between",gap:16,flexWrap:"wrap"}}>
            <div>
              <div style={{fontSize:11,fontWeight:700,letterSpacing:"0.24em",textTransform:"uppercase",color:"var(--accent)"}}>Screener</div>
              <h1 style={{fontSize:"clamp(1.8rem,3.2vw,2.8rem)",fontWeight:600,letterSpacing:"-0.025em",color:"#0f1923",marginTop:10,lineHeight:1.1}}>Candidate workspace</h1>
              <p style={{fontSize:13,color:"#566779",marginTop:10,lineHeight:1.7,maxWidth:420}}>Launch screens and review candidate pools.</p>
            </div>
            <div style={{display:"flex",gap:10}}>
              <Btn variant="accent" onClick={onNewScreener}>New Screener</Btn>
              <Btn variant="secondary">View Activity</Btn>
            </div>
          </div>
          <div style={{display:"grid",gridTemplateColumns:"repeat(3,1fr)",gap:12,marginTop:20}}>
            <MetricCard label="Total Runs" value={`${RUNS.length}`} meta="Historical screens" />
            <MetricCard label="Candidates" value={`${RUNS.reduce((a,r)=>a+r.candidates,0)}`} meta="Across all runs" />
            <MetricCard label="Active Tasks" value="0" meta="No screens in progress" />
          </div>
        </div>

        <div className="viewer fade-in" style={{padding:"22px 26px"}}>
          <div className="section-lbl" style={{marginBottom:6}}>Recent Runs</div>
          <h2 style={{fontSize:"1.25rem",fontWeight:600,letterSpacing:"-0.02em",color:"#0f1923",marginBottom:16}}>Screen history</h2>
          <div style={{display:"flex",flexDirection:"column",gap:10}}>
            {RUNS.map(run => (
              <div key={run.id} style={{display:"flex",alignItems:"center",justifyContent:"space-between",gap:12,borderRadius:22,border:"1px solid var(--border)",background:"rgba(255,255,255,0.88)",padding:"14px 18px",cursor:"pointer",transition:"border-color 150ms"}}
                onMouseEnter={e=>e.currentTarget.style.borderColor="rgba(93,116,112,.28)"}
                onMouseLeave={e=>e.currentTarget.style.borderColor="rgba(28,36,48,.12)"}
              >
                <div style={{display:"flex",alignItems:"center",gap:14}}>
                  <div>
                    <div style={{display:"flex",gap:6,marginBottom:4}}>
                      {run.markets.map(m => <Badge key={m} variant="secondary">{m.toUpperCase()}</Badge>)}
                    </div>
                    <div style={{fontFamily:"var(--font-mono)",fontSize:10,color:"#7a8fa0"}}>{run.id}</div>
                  </div>
                </div>
                <div style={{display:"flex",alignItems:"center",gap:12}}>
                  <span style={{fontSize:13,fontWeight:600,color:"#334155"}}>{run.candidates} candidates</span>
                  <Badge variant="success">Done</Badge>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </main>
  );
}

/* ── ASSETS ── */
const POSITIONS = [
  {ticker:"NVDA",name:"NVIDIA Corp",qty:50,cost:98.40,price:142.80,category:"stock"},
  {ticker:"AAPL",name:"Apple Inc",qty:30,cost:178.20,price:189.40,category:"stock"},
  {ticker:"BRK.B",name:"Berkshire B",qty:12,cost:350.10,price:412.60,category:"stock"},
  {ticker:"BTC",name:"Bitcoin",qty:0.25,cost:52000,price:67400,category:"crypto"},
];

function AssetsScreen() {
  const total = POSITIONS.reduce((a,p)=>a+p.qty*p.price,0);
  const cost  = POSITIONS.reduce((a,p)=>a+p.qty*p.cost,0);
  const pnl   = total - cost;
  const fmt = v => new Intl.NumberFormat("en-US",{style:"currency",currency:"USD",maximumFractionDigits:0}).format(v);
  return (
    <main style={{flex:1,overflowY:"auto",padding:"24px 28px 40px"}}>
      <div style={{maxWidth:920,margin:"0 auto",display:"flex",flexDirection:"column",gap:20}}>
        <div className="card fade-in" style={{padding:"28px 32px"}}>
          <div style={{display:"flex",alignItems:"flex-end",justifyContent:"space-between",gap:16,flexWrap:"wrap"}}>
            <div>
              <div className="kicker">Assets</div>
              <h1 style={{fontSize:"clamp(1.8rem,3vw,2.6rem)",fontWeight:600,letterSpacing:"-0.025em",color:"#0f1923",marginTop:10}}>Portfolio ledger</h1>
              <p style={{fontSize:13,color:"#566779",marginTop:10,lineHeight:1.7}}>Track positions, cost basis, and market exposure.</p>
            </div>
            <Btn variant="primary">Add Position</Btn>
          </div>
          <div style={{display:"grid",gridTemplateColumns:"repeat(3,1fr)",gap:12,marginTop:20}}>
            <MetricCard label="Market Value" value={fmt(total)} meta="Current portfolio value" />
            <MetricCard label="Unrealised P&L" value={fmt(pnl)} meta={`${((pnl/cost)*100).toFixed(1)}% total return`} />
            <MetricCard label="Positions" value={`${POSITIONS.length}`} meta="Tracked assets" />
          </div>
        </div>

        <div className="viewer fade-in" style={{padding:"22px 26px"}}>
          <div className="section-lbl" style={{marginBottom:6}}>Positions</div>
          <h2 style={{fontSize:"1.2rem",fontWeight:600,letterSpacing:"-0.02em",color:"#0f1923",marginBottom:16}}>Current holdings</h2>
          <table style={{width:"100%",borderCollapse:"collapse"}}>
            <thead>
              <tr style={{borderBottom:"1px solid var(--border)"}}>
                {["Ticker","Name","Qty","Cost","Price","Value","P&L"].map(h=>(
                  <th key={h} style={{textAlign:h==="Ticker"||h==="Name"?"left":"right",padding:"8px 10px",fontSize:10,fontWeight:700,letterSpacing:"0.16em",textTransform:"uppercase",color:"#94a3b8"}}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {POSITIONS.map(p=>{
                const val = p.qty*p.price;
                const gain = val - p.qty*p.cost;
                return (
                  <tr key={p.ticker} style={{borderBottom:"1px solid rgba(22,34,51,0.06)",transition:"background 150ms"}}
                    onMouseEnter={e=>e.currentTarget.style.background="rgba(255,255,255,0.6)"}
                    onMouseLeave={e=>e.currentTarget.style.background=""}
                  >
                    <td style={{padding:"12px 10px",fontWeight:700,color:"#0f1923",fontSize:14}}>{p.ticker}</td>
                    <td style={{padding:"12px 10px",fontSize:13,color:"#566779"}}>{p.name}</td>
                    <td style={{padding:"12px 10px",textAlign:"right",fontFamily:"var(--font-mono)",fontSize:13,color:"#334155"}}>{p.qty}</td>
                    <td style={{padding:"12px 10px",textAlign:"right",fontFamily:"var(--font-mono)",fontSize:13,color:"#566779"}}>{fmt(p.cost)}</td>
                    <td style={{padding:"12px 10px",textAlign:"right",fontFamily:"var(--font-mono)",fontSize:13,color:"#334155"}}>{fmt(p.price)}</td>
                    <td style={{padding:"12px 10px",textAlign:"right",fontFamily:"var(--font-mono)",fontSize:13,fontWeight:600,color:"#0f1923"}}>{fmt(val)}</td>
                    <td style={{padding:"12px 10px",textAlign:"right",fontFamily:"var(--font-mono)",fontSize:13,fontWeight:600,color:gain>=0?"#2e7653":"#a33535"}}>{gain>=0?"+":""}{fmt(gain)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </main>
  );
}

Object.assign(window, { LoginScreen, HomeScreen, TaskScreen, ScreenerScreen, AssetsScreen, Badge, Btn, MetricCard });
