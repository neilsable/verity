'use client'
import { useState, useEffect } from 'react'
const AGENTS = [
  {icon:'🎯',name:'Orchestrator',desc:'Decomposes brief and coordinates pipeline',detail:'Breaks your research brief into parallel sub-tasks, assigns each specialist agent, manages state across the entire pipeline, and synthesises final outputs. Without it, agents would conflict and duplicate work.',metrics:['Avg decomposition: 0.8s','8 agents coordinated','99.2% pipeline success']},
  {icon:'📋',name:'Filing Agent',desc:'Ingests SEC 10-K, 10-Q, 8-K via RAG',detail:'Connects to SEC EDGAR free API, downloads the latest annual and quarterly filings, chunks them with semantic overlap, embeds into a vector store, and retrieves only the passages relevant to your query.',metrics:['3 filing types parsed','Semantic chunking 512t','Source-cited retrieval']},
  {icon:'🎙️',name:'Earnings Agent',desc:'Scores management tone and Q&A evasion',detail:'Processes earnings call transcripts, scores hedge word density, passive voice ratio, and Q&A alignment — detecting when executives avoid analyst questions. Flags anomalies vs the executive\'s own historical baseline.',metrics:['Tone scored 0–100','Q&A evasion detection','Historical baseline delta']},
  {icon:'📊',name:'Comps Agent',desc:'Live peer comparison: P/E, EV/EBITDA, margins',detail:'Pulls live fundamental data from Yahoo Finance and Financial Modeling Prep. Builds a peer group automatically based on sector and market cap. Calculates relative valuation, margin comparison, and growth differentials.',metrics:['12 metrics compared','Live data via yfinance','Auto peer selection']},
  {icon:'📰',name:'News Agent',desc:'Temporal-decay weighted sentiment scoring',detail:'Fetches recent news via NewsAPI, applies temporal decay weighting (older articles count less), scores sentiment per article, and identifies material events that could move the stock. Flags regulatory, M&A, and guidance events.',metrics:['Temporal decay model','Materiality classifier','Sentiment –1 to +1']},
  {icon:'✍️',name:'Synthesis Agent',desc:'Writes bull thesis, bear thesis, valuation',detail:'Receives structured outputs from all four data agents and writes a professional research note: executive summary, bull thesis, bear thesis, key risks, and a valuation section — in the format a sell-side analyst would produce.',metrics:['5-section structure','Bull/bear thesis','Valuation rationale']},
  {icon:'🔍',name:'Critique Agent',desc:'Red-teams every claim, assigns confidence',detail:'Takes the draft research note and verifies every factual claim against the original source documents. Flags unsupported assertions, assigns a confidence score per claim, and forces the Synthesis Agent to revise anything below threshold.',metrics:['Zero hallucination policy','Per-claim confidence','Forces revision loop']},
  {icon:'📎',name:'Citation Agent',desc:'Maps every claim to source and passage',detail:'Generates a complete citation index for the final report. Every claim is mapped to the exact document, date, page, and passage it came from — SEC filing, earnings call, or data provider. Full audit trail.',metrics:['100% claims cited','Exact page reference','Full audit trail']}
]
const CHIPS=[
  {t:'AAPL',logo:'https://assets.parqet.com/logos/symbol/AAPL'},
  {t:'NVDA',logo:'https://assets.parqet.com/logos/symbol/NVDA'},
  {t:'MSFT',logo:'https://assets.parqet.com/logos/symbol/MSFT'},
  {t:'GOOGL',logo:'https://assets.parqet.com/logos/symbol/GOOGL'},
  {t:'TSLA',logo:'https://assets.parqet.com/logos/symbol/TSLA'},
  {t:'META',logo:'https://assets.parqet.com/logos/symbol/META'},
  {t:'AMZN',logo:'https://assets.parqet.com/logos/symbol/AMZN'},
  {t:'JPM',logo:'https://assets.parqet.com/logos/symbol/JPM'},
]
const PIPE=['Orchestrator','Filing','Earnings','Comps','News','Synthesis','Critique','Citation']
export default function Home(){
  const [ticker,setTicker]=useState('')
  const [brief,setBrief]=useState('')
  const [hover,setHover]=useState(-1)
  const [step,setStep]=useState(-1)
  const [running,setRunning]=useState(false)
  useEffect(()=>{const t=setInterval(()=>setHover(h=>h<0?0:(h+1)%8),2200);return()=>clearInterval(t)},[])
  const demo=()=>{if(running)return;setRunning(true);setStep(0);let s=0;const iv=setInterval(()=>{s++;setStep(s);if(s>=PIPE.length){clearInterval(iv);setTimeout(()=>{setRunning(false);setStep(-1)},2500)}},650)}
  const pct=step<0?100:Math.round((step/PIPE.length)*100)
  const S={fontFamily:"'DM Sans',-apple-system,sans-serif",background:'#f8f7f4',color:'#0a0a0f'}
  return(<div style={S}>
    <style>{`@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500&family=DM+Mono:wght@500&display=swap');*{box-sizing:border-box;margin:0;padding:0}html{scroll-behavior:smooth}body{-webkit-font-smoothing:antialiased}@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}@keyframes fadeUp{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}.agent-detail{animation:fadeUp .2s ease}@media(max-width:900px){.hg{grid-template-columns:1fr!important}.mg{grid-template-columns:repeat(2,1fr)!important}.ag{grid-template-columns:repeat(2,1fr)!important}.rg{grid-template-columns:1fr!important}.pg{grid-template-columns:1fr!important}nav a{display:none}}`}</style>
    <nav style={{position:'fixed',top:0,left:0,right:0,zIndex:100,height:64,display:'flex',alignItems:'center',justifyContent:'space-between',padding:'0 48px',background:'rgba(248,247,244,.95)',backdropFilter:'blur(16px)',borderBottom:'1px solid #e8e6de'}}>
      <div style={{display:'flex',alignItems:'center',gap:10}}><span style={{width:8,height:8,borderRadius:'50%',background:'#c9a84c',display:'inline-block',animation:'pulse 2s infinite'}}/><span style={{fontFamily:'Georgia,serif',fontSize:22,fontWeight:600}}>VERITY</span></div>
      <div style={{display:'flex',gap:32}}>{'Agents,Reports,Research'.split(',').map(l=><a key={l} href={`#${l.toLowerCase()}`} style={{fontSize:14,color:'#3a3a4a',textDecoration:'none'}}>{l}</a>)}</div>
      <div style={{display:'flex',gap:12}}>
        <button style={{fontSize:14,background:'none',border:'1px solid #e8e6de',borderRadius:4,padding:'8px 18px',cursor:'pointer',color:'#3a3a4a'}}>Sign in</button>
        <button onClick={()=>document.getElementById('search')?.scrollIntoView({behavior:'smooth'})} style={{fontSize:14,fontWeight:500,background:'#0a0a0f',color:'#fff',border:'none',borderRadius:4,padding:'9px 20px',cursor:'pointer'}}>Get started</button>
      </div>
    </nav>
    <section style={{minHeight:'100vh',display:'flex',alignItems:'center',padding:'120px 48px 80px',position:'relative',overflow:'hidden'}}>
      <div style={{position:'absolute',inset:0,backgroundImage:'linear-gradient(rgba(10,10,15,.04) 1px,transparent 1px),linear-gradient(90deg,rgba(10,10,15,.04) 1px,transparent 1px)',backgroundSize:'48px 48px',pointerEvents:'none'}}/>
      <div style={{position:'absolute',inset:0,background:'radial-gradient(ellipse 800px 500px at 65% 50%,rgba(201,168,76,.06),transparent 60%)',pointerEvents:'none'}}/>
      <div className="hg" style={{maxWidth:1200,margin:'0 auto',width:'100%',display:'grid',gridTemplateColumns:'1fr 1fr',gap:80,alignItems:'center',position:'relative',zIndex:1}}>
        <div>
          <div style={{display:'inline-flex',alignItems:'center',gap:8,fontSize:12,fontWeight:500,letterSpacing:'.08em',textTransform:'uppercase',color:'#c9a84c',background:'rgba(201,168,76,.08)',border:'1px solid rgba(201,168,76,.2)',borderRadius:100,padding:'5px 14px',marginBottom:28}}><span style={{width:6,height:6,borderRadius:'50%',background:'#c9a84c',display:'inline-block'}}/>Institutional-Grade AI Research</div>
          <h1 style={{fontFamily:'Georgia,serif',fontSize:'clamp(44px,5.5vw,74px)',lineHeight:1.05,letterSpacing:'-.02em',marginBottom:24}}>The research<br/><span style={{color:'#2d5a8f',fontStyle:'italic'}}>infrastructure</span><br/>serious investors<br/>actually use.</h1>
          <p style={{fontSize:18,fontWeight:300,lineHeight:1.75,color:'#3a3a4a',maxWidth:480,marginBottom:40}}>Eight autonomous agents analyse SEC filings, earnings calls, peer comps, and live news — delivering a cited, red-teamed research note in minutes.</p>
          <div style={{display:'flex',gap:16,flexWrap:'wrap'}}>
            <button onClick={()=>document.getElementById('search')?.scrollIntoView({behavior:'smooth'})} style={{fontSize:15,fontWeight:500,background:'#0a0a0f',color:'#fff',border:'none',borderRadius:4,padding:'14px 28px',cursor:'pointer'}}>Research a stock →</button>
            <button onClick={demo} style={{fontSize:15,background:'none',color:'#3a3a4a',border:'1px solid #e8e6de',borderRadius:4,padding:'14px 28px',cursor:'pointer'}}>{running?'Running…':'Watch demo'}</button>
          </div>
          <div style={{display:'flex',gap:0,marginTop:48,borderTop:'1px solid #e8e6de',paddingTop:32}}>
            {[['8','Agents'],['<4min','Per report'],['100%','Cited'],['$0.18','Avg cost']].map(([v,l],i)=>(
              <div key={l} style={{flex:1,paddingRight:24,borderRight:i<3?'1px solid #e8e6de':'none',marginRight:i<3?24:0}}>
                <div style={{fontFamily:'Georgia,serif',fontSize:28,fontWeight:700,marginBottom:2}}>{v}</div>
                <div style={{fontSize:13,color:'#7a7a8a'}}>{l}</div>
              </div>
            ))}
          </div>
        </div>
        <div style={{background:'#fff',border:'1px solid #e8e6de',borderRadius:12,overflow:'hidden',boxShadow:'0 24px 64px rgba(10,10,15,.08)'}}>
          <div style={{padding:'16px 20px',borderBottom:'1px solid #e8e6de',display:'flex',alignItems:'center',justifyContent:'space-between'}}>
            <div><div style={{fontFamily:'monospace',fontSize:18,fontWeight:700,letterSpacing:'.05em'}}>NVDA</div><div style={{fontSize:12,color:'#7a7a8a',marginTop:2}}>NVIDIA Corporation</div></div>
            <span style={{fontSize:12,fontWeight:500,background:'rgba(42,155,106,.08)',color:'#2a9b6a',border:'1px solid rgba(42,155,106,.2)',borderRadius:100,padding:'4px 12px'}}>{running?`${pct}%`:'Live'}</span>
          </div>
          <div style={{padding:'12px 20px',borderBottom:'1px solid #e8e6de'}}>
            <div style={{display:'flex',justifyContent:'space-between',marginBottom:6,fontSize:12}}><span style={{color:'#3a3a4a'}}>Pipeline progress</span><span style={{fontFamily:'monospace',color:'#7a7a8a'}}>{running?`${pct}%`:'100%'}</span></div>
            <div style={{height:4,background:'#f0efe9',borderRadius:100,overflow:'hidden'}}><div style={{height:'100%',borderRadius:100,background:running?'#2d5a8f':'#2a9b6a',width:`${running?pct:100}%`,transition:'width .5s ease'}}/></div>
          </div>
          <div style={{padding:12}}>
            {PIPE.map((a,i)=>{const done=!running||i<step;const act=running&&i===step;return(
              <div key={a} style={{display:'flex',alignItems:'center',gap:10,padding:'8px 10px',borderRadius:6,background:act?'rgba(45,90,143,.05)':done&&running?'rgba(42,155,106,.03)':'transparent',marginBottom:2}}>
                <span style={{width:7,height:7,borderRadius:'50%',background:act?'#2d5a8f':(done&&running)||!running?'#2a9b6a':'#e8e6de',flexShrink:0}}/>
                <span style={{fontSize:13,fontWeight:act?500:400,color:act?'#2d5a8f':(!running||done)?'#0a0a0f':'#7a7a8a',flex:1}}>{a} Agent</span>
                <span style={{fontSize:11,color:act?'#2d5a8f':'#7a7a8a'}}>{act?'analysing…':(!running||done)?'✓':'—'}</span>
              </div>
            )})}
          </div>
        </div>
      </div>
    </section>
    <section id="search" style={{padding:'100px 48px',background:'#fff'}}>
      <div style={{maxWidth:760,margin:'0 auto'}}>
        <div style={{fontSize:11,fontWeight:500,letterSpacing:'.1em',textTransform:'uppercase',color:'#c9a84c',marginBottom:12}}>Research Engine</div>
        <h2 style={{fontFamily:'Georgia,serif',fontSize:'clamp(28px,4vw,44px)',lineHeight:1.1,letterSpacing:'-.01em',marginBottom:8}}>Enter a ticker. Get a cited research note.</h2>
        <p style={{fontSize:16,fontWeight:300,color:'#3a3a4a',marginBottom:40}}>Specify a focus or leave it to the orchestrator.</p>
        <div style={{display:'flex',gap:12,alignItems:'center',background:'#f8f7f4',border:'1.5px solid #e8e6de',borderRadius:10,padding:'8px 8px 8px 20px',marginBottom:14}}>
          <input value={ticker} onChange={e=>setTicker(e.target.value.toUpperCase().slice(0,6))} placeholder="AAPL" style={{fontFamily:'monospace',fontSize:20,fontWeight:700,width:110,background:'none',border:'none',outline:'none',color:'#0a0a0f',letterSpacing:'.05em'}}/>
          <div style={{width:1,background:'#e8e6de',alignSelf:'stretch',margin:'4px 0'}}/>
          <input value={brief} onChange={e=>setBrief(e.target.value)} placeholder="e.g. Focus on AI services revenue and margin expansion" style={{flex:1,fontSize:14,fontWeight:300,background:'none',border:'none',outline:'none',color:'#3a3a4a'}}/>
          <button style={{fontSize:14,fontWeight:500,background:ticker?'#0a0a0f':'#b0b0b0',color:'#fff',border:'none',borderRadius:6,padding:'12px 24px',cursor:ticker?'pointer':'not-allowed',whiteSpace:'nowrap'}}>Run research →</button>
        </div>
        <div style={{display:'flex',gap:8,flexWrap:'wrap'}}>
          {CHIPS.map(({t,logo})=>(
            <button key={t} onClick={()=>setTicker(t)} style={{display:'flex',alignItems:'center',gap:6,fontFamily:'monospace',fontSize:12,fontWeight:600,letterSpacing:'.04em',background:ticker===t?'rgba(45,90,143,.06)':'#f8f7f4',border:`1px solid ${ticker===t?'#2d5a8f':'#e8e6de'}`,color:ticker===t?'#2d5a8f':'#3a3a4a',borderRadius:100,padding:'5px 12px',cursor:'pointer'}}>
              <img src={logo} alt={t} width={16} height={16} style={{borderRadius:'50%',objectFit:'cover'}} onError={(e)=>{(e.target as HTMLImageElement).style.display='none'}}/>
              {t}
            </button>
          ))}
        </div>
      </div>
    </section>
    <section id="agents" style={{padding:'100px 48px',background:'#f8f7f4'}}>
      <div style={{maxWidth:1100,margin:'0 auto'}}>
        <div style={{maxWidth:560,marginBottom:60}}>
          <div style={{fontSize:11,fontWeight:500,letterSpacing:'.1em',textTransform:'uppercase',color:'#c9a84c',marginBottom:12}}>Intelligence Layer</div>
          <h2 style={{fontFamily:'Georgia,serif',fontSize:'clamp(28px,4vw,44px)',lineHeight:1.1,marginBottom:12}}>Eight specialists. One pipeline.</h2>
          <p style={{fontSize:15,fontWeight:300,color:'#3a3a4a',lineHeight:1.7}}>Each agent runs in parallel where possible. Hover any card to see exactly what it does and why it exists in the pipeline.</p>
        </div>
        <div className="ag" style={{display:'grid',gridTemplateColumns:'repeat(4,1fr)',gap:14}}>
          {AGENTS.map((a,i)=>(
            <div key={a.name} onMouseEnter={()=>setHover(i)} onMouseLeave={()=>setHover(-1)} style={{background:'#fff',border:`1px solid ${hover===i?'rgba(201,168,76,.5)':'#e8e6de'}`,borderRadius:10,padding:22,transition:'all .2s',transform:hover===i?'translateY(-4px)':'none',boxShadow:hover===i?'0 16px 40px rgba(10,10,15,.1)':'none',cursor:'default',minHeight:200}}>
              <div style={{width:40,height:40,background:hover===i?'rgba(201,168,76,.08)':'#f8f7f4',border:`1px solid ${hover===i?'rgba(201,168,76,.3)':'#e8e6de'}`,borderRadius:8,display:'flex',alignItems:'center',justifyContent:'center',fontSize:18,marginBottom:14,transition:'all .2s'}}>{a.icon}</div>
              <div style={{fontSize:14,fontWeight:500,marginBottom:6}}>{a.name}</div>
              {hover===i?(
                <div className="agent-detail">
                  <div style={{fontSize:12,fontWeight:300,color:'#3a3a4a',lineHeight:1.65,marginBottom:12}}>{a.detail}</div>
                  <div style={{display:'flex',flexDirection:'column',gap:4}}>
                    {a.metrics.map(m=>(
                      <div key={m} style={{display:'flex',alignItems:'center',gap:6,fontSize:11,color:'#2d5a8f'}}>
                        <span style={{width:4,height:4,borderRadius:'50%',background:'#2d5a8f',flexShrink:0}}/>
                        {m}
                      </div>
                    ))}
                  </div>
                </div>
              ):(
                <>
                  <div style={{fontSize:13,fontWeight:300,color:'#3a3a4a',lineHeight:1.6,marginBottom:12}}>{a.desc}</div>
                  <div style={{display:'flex',alignItems:'center',gap:5}}><span style={{width:5,height:5,borderRadius:'50%',background:'#2a9b6a'}}/><span style={{fontSize:11,fontWeight:500,color:'#2a9b6a'}}>Active</span></div>
                </>
              )}
            </div>
          ))}
        </div>
      </div>
    </section>
    <section id="reports" style={{padding:'100px 48px',background:'#0a0a0f',position:'relative',overflow:'hidden'}}>
      <div style={{position:'absolute',inset:0,background:'radial-gradient(ellipse 700px 500px at 80% 50%,rgba(201,168,76,.05),transparent)',pointerEvents:'none'}}/>
      <div className="rg" style={{maxWidth:1100,margin:'0 auto',position:'relative',display:'grid',gridTemplateColumns:'1fr 1.5fr',gap:80,alignItems:'center'}}>
        <div>
          <div style={{fontSize:11,fontWeight:500,letterSpacing:'.1em',textTransform:'uppercase',color:'#c9a84c',marginBottom:16}}>Sample Output</div>
          <h2 style={{fontFamily:'Georgia,serif',fontSize:'clamp(28px,4vw,48px)',lineHeight:1.1,letterSpacing:'-.02em',color:'#fff',marginBottom:20}}>Reports that cite every single claim.</h2>
          <p style={{fontSize:16,fontWeight:300,lineHeight:1.75,color:'rgba(255,255,255,.6)',marginBottom:32}}>No hallucinations. No unsourced assertions. Every line traced to an SEC filing, earnings call, or verified data source.</p>
          <button style={{fontSize:15,fontWeight:500,background:'#c9a84c',color:'#0a0a0f',border:'none',borderRadius:4,padding:'14px 28px',cursor:'pointer'}}>View sample report</button>
        </div>
        <div style={{background:'rgba(255,255,255,.04)',border:'1px solid rgba(255,255,255,.1)',borderRadius:12,overflow:'hidden'}}>
          <div style={{padding:'18px 22px',borderBottom:'1px solid rgba(255,255,255,.08)',display:'flex',alignItems:'center',justifyContent:'space-between'}}>
            <div style={{display:'flex',alignItems:'center',gap:10}}>
              <img src="https://assets.parqet.com/logos/symbol/NVDA" width={28} height={28} style={{borderRadius:'50%'}} alt="NVDA"/>
              <div><div style={{fontFamily:'monospace',fontSize:18,fontWeight:700,color:'#fff',letterSpacing:'.05em'}}>NVDA</div><div style={{fontSize:12,color:'rgba(255,255,255,.45)',marginTop:2}}>NVIDIA Corporation</div></div>
            </div>
            <span style={{fontSize:12,fontWeight:500,background:'rgba(42,155,106,.15)',color:'#5dd49a',border:'1px solid rgba(42,155,106,.25)',borderRadius:100,padding:'4px 12px'}}>94% confidence</span>
          </div>
          <div style={{padding:22}}>
            <div style={{fontSize:10,fontWeight:500,letterSpacing:'.1em',textTransform:'uppercase',color:'rgba(255,255,255,.3)',marginBottom:8}}>Executive Summary</div>
            <p style={{fontSize:14,fontWeight:300,lineHeight:1.75,color:'rgba(255,255,255,.75)',marginBottom:18}}>NVIDIA continues to demonstrate exceptional pricing power in AI accelerator markets, with data centre revenue growing 427% YoY in FY2024. The H100 supply-demand imbalance remains structurally supportive of gross margins above 70%.</p>
            <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:10,marginBottom:18}}>
              {[['#2a9b6a','Bull','Blackwell ramp accelerates. Sovereign AI expands TAM.'],['#e86060','Bear','AMD gains traction. Export controls create China risk.']].map(([c,l,t])=>(
                <div key={l} style={{background:'rgba(255,255,255,.03)',borderLeft:`2px solid ${c}`,borderRadius:4,padding:12}}>
                  <div style={{fontSize:10,fontWeight:500,letterSpacing:'.08em',textTransform:'uppercase',color:c,marginBottom:5}}>{l}</div>
                  <div style={{fontSize:12,fontWeight:300,color:'rgba(255,255,255,.6)',lineHeight:1.6}}>{t}</div>
                </div>
              ))}
            </div>
            {['NVDA 10-K FY2024, p.48 — Revenue breakdown','Q4 2024 Earnings Call — Jensen Huang, Feb 21','Financial Modeling Prep — Peer comparison'].map((c,i)=>(
              <div key={i} style={{display:'flex',alignItems:'center',gap:8,padding:'7px 0',borderTop:'1px solid rgba(255,255,255,.06)',fontSize:12,color:'rgba(255,255,255,.4)'}}>
                <span style={{fontFamily:'monospace',fontSize:10,fontWeight:500,background:'rgba(201,168,76,.15)',color:'#e8c96a',borderRadius:3,padding:'2px 6px',flexShrink:0}}>{i+1}</span>{c}
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
    <footer style={{padding:48,background:'#0a0a0f',display:'flex',alignItems:'center',justifyContent:'space-between',flexWrap:'wrap',gap:20}}>
      <div style={{display:'flex',alignItems:'center',gap:8}}><span style={{width:6,height:6,borderRadius:'50%',background:'#c9a84c',display:'inline-block'}}/><span style={{fontFamily:'Georgia,serif',fontSize:18,color:'#fff'}}>VERITY</span></div>
      <div style={{display:'flex',gap:28}}>{'Documentation,API,Privacy,Terms'.split(',').map(l=><a key={l} href="#" style={{fontSize:13,color:'rgba(255,255,255,.4)',textDecoration:'none'}}>{l}</a>)}</div>
      <div style={{fontSize:12,color:'rgba(255,255,255,.25)'}}>© 2026 VERITY Research Platform</div>
    </footer>
  </div>)
}
