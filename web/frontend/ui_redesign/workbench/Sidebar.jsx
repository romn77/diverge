// Diverge Workbench — Sidebar component
// Exports: Sidebar to window

const DivergeMark = ({ size = 28, color = "currentColor" }) => (
  <svg viewBox="0 0 96 96" width={size} height={size} fill="none" aria-hidden="true">
    <path d="M21.5 65.5a34.5 34.5 0 1 1 53 0" stroke={color} strokeWidth="6" strokeLinecap="round"/>
    <path d="M48 78V45M48 45 31 28M48 45l17-17" stroke={color} strokeWidth="6" strokeLinecap="round" strokeLinejoin="round"/>
    <path d="M26.5 23.5 42 28l-11 11-1.5-8.5-8.5-1.5 5.5-5.5Z" fill={color}/>
    <path d="M69.5 23.5 54 28l11 11 1.5-8.5 8.5-1.5-5.5-5.5Z" fill={color}/>
    <path d="M48 78c-8.8-7.8-18.6-12.1-31.4-12.1M48 78c8.8-7.8 18.6-12.1 31.4-12.1M48 72.8c-10.2-6.4-21.1-9.2-32.8-8.3M48 72.8c10.2-6.4 21.1-9.2 32.8-8.3M48 67.6c-9.1-4.4-18.4-6.4-28-5.8M48 67.6c9.1-4.4 18.4-6.4 28-5.8" stroke={color} strokeWidth="3.6" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
);

const icons = {
  Analysis: () => (
    <svg viewBox="0 0 20 20" width="18" height="18" fill="none">
      <path d="M4.75 14.25 8 10.5l2.25 2.25L15.25 6.5" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M4.75 4.75h10.5v10.5H4.75z" stroke="currentColor" strokeWidth="1.4"/>
    </svg>
  ),
  Screener: () => (
    <svg viewBox="0 0 20 20" width="18" height="18" fill="none">
      <rect x="4" y="4" width="12" height="12" rx="3" stroke="currentColor" strokeWidth="1.6"/>
      <path d="M7 7.5h6M7 10h6M7 12.5h4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"/>
    </svg>
  ),
  Assets: () => (
    <svg viewBox="0 0 20 20" width="18" height="18" fill="none">
      <path d="M4.5 6.5h11M4.5 10h11M4.5 13.5h11" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"/>
      <rect x="3.75" y="4.75" width="12.5" height="10.5" rx="2.5" stroke="currentColor" strokeWidth="1.4"/>
    </svg>
  ),
  Journal: () => (
    <svg viewBox="0 0 20 20" width="18" height="18" fill="none">
      <path d="M6 4.75h7.5A1.75 1.75 0 0 1 15.25 6.5v8.75H6A1.75 1.75 0 0 0 4.25 17V6.5A1.75 1.75 0 0 1 6 4.75Z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round"/>
      <path d="M7.5 8.25h4.5M7.5 11h4.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"/>
    </svg>
  ),
  Activity: () => (
    <svg viewBox="0 0 20 20" width="18" height="18" fill="none">
      <path d="M4.5 10h2.75l1.5-3 2.5 6 1.5-3H15.5" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"/>
      <rect x="3.75" y="4.75" width="12.5" height="10.5" rx="2.5" stroke="currentColor" strokeWidth="1.4"/>
    </svg>
  ),
};

const NAV_SECTIONS = [
  { title: "Research", items: [
    { id: "home", label: "Analysis", meta: "Reports and search", icon: "Analysis" },
    { id: "screener", label: "Screener", meta: "Runs and candidates", icon: "Screener" },
  ]},
  { title: "Portfolio", items: [
    { id: "assets", label: "Assets", meta: "Ledger and exposure", icon: "Assets" },
    { id: "journal", label: "Journal", meta: "Trade review", icon: "Journal" },
  ]},
];

function NavLink({ item, active, onClick }) {
  const Icon = icons[item.icon];
  return (
    <button onClick={() => onClick(item.id)} style={{
      display:"flex", alignItems:"center", gap:10, borderRadius:20, border:"1px solid",
      padding:"10px 10px", width:"100%", cursor:"pointer", textAlign:"left", background:"none",
      fontFamily:"inherit",
      borderColor: active ? "var(--primary)" : "rgba(22,34,51,0.06)",
      background: active ? "var(--primary-soft)" : "rgba(255,255,255,0.68)",
      boxShadow: active ? "0 14px 30px rgba(28,36,48,0.1)" : "none",
      transition:"all 150ms ease",
    }}>
      <div style={{
        width:36, height:36, flexShrink:0, borderRadius:10, border:"1px solid",
        borderColor: active ? "rgba(93,116,112,0.24)" : "var(--border)",
        background:"white", display:"grid", placeItems:"center",
        color: active ? "var(--primary-strong)" : "#64748b",
      }}>
        <Icon />
      </div>
      <div>
        <div style={{fontSize:13, fontWeight:600, color: active ? "var(--primary-strong)" : "#1e293b"}}>{item.label}</div>
        <div style={{fontSize:11, color:"#64748b", marginTop:1}}>{item.meta}</div>
      </div>
    </button>
  );
}

function Sidebar({ active, onNavigate, activeTaskCount = 0 }) {
  return (
    <aside style={{
      width:216, flexShrink:0, display:"flex", flexDirection:"column",
      height:"100%", borderRight:"1px solid var(--border)",
      background:"linear-gradient(180deg,rgba(255,253,248,0.98) 0%,rgba(245,242,236,0.94) 100%)",
      padding:"18px 14px", overflowY:"auto",
    }}>
      {/* Header */}
      <div style={{display:"flex",alignItems:"center",gap:10,paddingBottom:14,borderBottom:"1px solid var(--border)",marginBottom:16}}>
        <div style={{width:38,height:38,borderRadius:"50%",border:"1px solid var(--border)",background:"var(--surface)",display:"grid",placeItems:"center",boxShadow:"0 8px 18px rgba(18,28,41,0.07)"}}>
          <DivergeMark size={28} color="#1c2430" />
        </div>
        <span style={{fontFamily:"var(--font-heading)",fontSize:"1.1rem",fontWeight:600,color:"var(--text)",letterSpacing:"-0.01em"}}>Diverge</span>
      </div>

      {/* Nav sections */}
      <nav style={{flex:1,display:"flex",flexDirection:"column",gap:16}}>
        {NAV_SECTIONS.map(section => (
          <section key={section.title}>
            <div style={{fontSize:10,fontWeight:700,letterSpacing:"0.24em",textTransform:"uppercase",color:"#94a3b8",padding:"0 8px",marginBottom:6}}>{section.title}</div>
            <div style={{display:"flex",flexDirection:"column",gap:5}}>
              {section.items.map(item => (
                <NavLink key={item.id} item={item} active={active === item.id} onClick={onNavigate} />
              ))}
            </div>
          </section>
        ))}
      </nav>

      {/* Operations */}
      <div style={{borderTop:"1px solid var(--border)",paddingTop:14,marginTop:12}}>
        <div style={{fontSize:10,fontWeight:700,letterSpacing:"0.24em",textTransform:"uppercase",color:"#94a3b8",padding:"0 8px",marginBottom:6}}>Operations</div>
        <button onClick={() => onNavigate("activity")} style={{
          display:"flex",alignItems:"center",justifyContent:"space-between",gap:10,
          borderRadius:20,border:"1px solid",padding:"10px 10px",width:"100%",cursor:"pointer",
          fontFamily:"inherit",textAlign:"left",background:"none",
          borderColor: active === "activity" ? "var(--accent)" : "var(--border)",
          background: active === "activity" ? "var(--accent-soft)" : "rgba(255,255,255,0.76)",
          transition:"all 150ms ease",
        }}>
          <div style={{display:"flex",alignItems:"center",gap:10}}>
            <div style={{width:36,height:36,flexShrink:0,borderRadius:10,border:"1px solid var(--border)",background:"white",display:"grid",placeItems:"center",color:"#64748b"}}>
              {React.createElement(icons.Activity)}
            </div>
            <div>
              <div style={{fontSize:13,fontWeight:600,color:"#1e293b"}}>Activity</div>
              <div style={{fontSize:11,color:"#64748b",marginTop:1}}>{activeTaskCount > 0 ? `${activeTaskCount} active` : "No active work"}</div>
            </div>
          </div>
          {activeTaskCount > 0 && (
            <span style={{borderRadius:"999px",background:"var(--accent)",padding:"2px 8px",fontSize:10,fontWeight:700,letterSpacing:"0.14em",textTransform:"uppercase",color:"white"}}>{activeTaskCount}</span>
          )}
        </button>
      </div>
    </aside>
  );
}

Object.assign(window, { Sidebar, DivergeMark });
