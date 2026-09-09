"use client";
import {useEffect,useState} from 'react';
import {SeleryClient,formatTime,type ResearchReport} from '@selery/shared';
const client=new SeleryClient('');
export default function ReportLibrary({onSelect,refreshKey}:{onSelect:(r:ResearchReport)=>void;refreshKey?:string}) {
 const [reports,setReports]=useState<ResearchReport[]>([]),[offset,setOffset]=useState(0),[error,setError]=useState('');
 useEffect(()=>{let active=true;client.reports(10,offset).then(items=>{if(active){setReports(items);setError('');}}).catch(e=>{if(active)setError(e.message);});return()=>{active=false;};},[offset,refreshKey]);
 return <section className="panel padded" style={{gridColumn:'1 / -1'}}>
  <div className="section-title"><h2>Saved study comparison</h2><span className="muted">Page {offset/10+1}</span></div>
  <p className="muted">Compare analytical event studies. Different feeds, horizons or strategies describe different cohorts. These are not realized portfolio results.</p>
  {error&&<p role="alert">{error}</p>}
  <div style={{overflowX:'auto'}}><table><thead><tr><th>Study</th><th>Feed / horizon</th><th>Signals</th><th>Target-first rate</th><th>Created</th></tr></thead><tbody>{reports.map(report=><tr key={report.id}>
   <td><button onClick={()=>onSelect(report)}>{report.request.symbol} · {report.request.strategy}</button></td>
   <td>{report.request.feed==='iex'?'IEX only':report.request.feed.toUpperCase()} · {report.request.timeframe} · {report.request.horizon_bars} bars</td>
   <td>{report.signal_count}</td><td>{report.metrics.hit_rate==null?'Unavailable':(report.metrics.hit_rate*100).toFixed(1)+'%'}</td><td>{formatTime(report.created_at)}</td>
  </tr>)}</tbody></table></div>
  {!reports.length&&<p className="muted">No saved studies on this page.</p>}
  <div className="button-row"><button disabled={offset===0} onClick={()=>setOffset(n=>Math.max(0,n-10))}>Previous studies</button><button disabled={reports.length<10} onClick={()=>setOffset(n=>n+10)}>Next studies</button></div>
 </section>;
}
