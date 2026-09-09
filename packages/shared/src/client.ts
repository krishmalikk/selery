import { z } from 'zod';
import { WatchlistResponseSchema, ChartResponseSchema, NewsResponseSchema, SettingsSchema, StrategyInfoSchema, ResearchReportSchema, JobSchema, SizingResponseSchema, OutcomeSummarySchema, JournalEntrySchema, AlertSchema, ChatResponseSchema } from './contracts';
import type { Timeframe, Feed, SizingRequest, ResearchRequest, ChatRequest, JournalEntry } from './contracts';

export class ApiError extends Error { constructor(public status:number,message:string){super(message);} }
export class SeleryClient {
  constructor(public baseUrl:string, private getToken:()=>string|null = ()=>null) {}
  async request<T>(path:string,schema:z.ZodType<T>,init:RequestInit={}):Promise<T>{
    const token=this.getToken();
    const response=await fetch(`${this.baseUrl}/api/v1${path}`,{...init,credentials:'include',headers:{'Content-Type':'application/json',...(token?{Authorization:`Bearer ${token}`} : {}),...init.headers}});
    if(!response.ok){const body=await response.json().catch(()=>({detail:'Request failed'}));throw new ApiError(response.status,typeof body.detail==='string'?body.detail:JSON.stringify(body.detail));}
    return schema.parse(await response.json());
  }
  login(password:string){return this.request('/auth/login',z.object({token:z.string(),expires_in:z.number()}),{method:'POST',body:JSON.stringify({password})});}
  logout(){return this.request('/auth/logout',z.object({ok:z.boolean()}),{method:'POST'});}
  watchlist(){return this.request('/watchlist',WatchlistResponseSchema);}
  chart(symbol:string,timeframe:Timeframe='5m',feed:Feed='iex'){return this.request(`/chart/${encodeURIComponent(symbol)}?timeframe=${timeframe}&feed=${feed}`,ChartResponseSchema);}
  news(){return this.request('/news',NewsResponseSchema);}
  settings(){return this.request('/settings',SettingsSchema);}
  strategies(){return this.request('/strategies',z.array(StrategyInfoSchema));}
  outcomes(){return this.request('/outcomes',z.array(OutcomeSummarySchema));}
  journal(){return this.request('/journal',z.array(JournalEntrySchema));}
  saveJournal(entry:Pick<JournalEntry,'symbol'|'thesis'|'outcome'|'reflection'> & Partial<Pick<JournalEntry,'id'|'chart_snapshot'>>){return this.request('/journal',JournalEntrySchema,{method:'POST',body:JSON.stringify(entry)});}
  alerts(){return this.request('/alerts',z.array(AlertSchema));}
  readAlert(id:string){return this.request(`/alerts/${encodeURIComponent(id)}/read`,z.object({ok:z.boolean()}),{method:'POST'});}
  size(input:SizingRequest){return this.request('/research/size',SizingResponseSchema,{method:'POST',body:JSON.stringify(input)});}
  research(input:ResearchRequest){return this.request('/research',ResearchReportSchema,{method:'POST',body:JSON.stringify(input)});}
  report(id:string){return this.request(`/research/${encodeURIComponent(id)}`,ResearchReportSchema);}
  chat(input:ChatRequest){return this.request('/chat',ChatResponseSchema,{method:'POST',body:JSON.stringify(input)});}
  jobs(){return this.request('/jobs',z.array(JobSchema));}
  domain(){return this.request('/domain/SPY',z.record(z.unknown()));}
  modelStatus(){return this.request('/models',z.record(z.unknown()));}
  async streamTicket(){return this.request('/auth/stream-ticket',z.object({ticket:z.string()}),{method:'POST'});}
}
