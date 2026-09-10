import { z } from 'zod';
import { ConversationSchema, ConversationDetailSchema } from './contracts';
import { PasskeyStatusSchema, PasskeyOptionsSchema, PasskeyInfoSchema, SessionResponseSchema } from './contracts';
import { PublicSourceSchema, PublicTraderPageSchema, PublicActivityPageSchema, PublicActivityDetailSchema, PublicRefreshResultSchema } from './contracts';
import { WatchlistResponseSchema, ChartResponseSchema, NewsResponseSchema, SettingsSchema, StrategyInfoSchema, ResearchReportSchema, JobSchema, SizingResponseSchema, OutcomeSummarySchema, JournalEntrySchema, AlertSchema, ChatResponseSchema } from './contracts';
import type { Timeframe, Feed, SizingRequest, ResearchRequest, ChatRequest, JournalEntry } from './contracts';

export class ApiError extends Error { constructor(public status:number,message:string){super(message);} }
// During a staggered web/API rollout, older responses omit only the additive
// chat-v2 metadata. Fill those explicit unavailable values before strict validation.
function chatCompatibility(path:string,value:any):unknown {
  const citation=(item:any)=>item && typeof item==='object' ? {provider:null,feed:null,available_at:null,observation:null,...item} : item;
  const conversation=(item:any)=>item && typeof item==='object' ? {signal:null,chart_start:null,chart_end:null,summary:null,summary_at:null,...item} : item;
  if(path==='/chat' && value && typeof value==='object')return {...value,citations:Array.isArray(value.citations)?value.citations.map(citation):value.citations};
  if(!path.startsWith('/conversations'))return value;
  if(Array.isArray(value))return value.map(conversation);
  if(value && typeof value==='object' && 'conversation' in value)return {...value,conversation:conversation(value.conversation),messages:Array.isArray(value.messages)?value.messages.map((item:any)=>({...item,phase:item.phase??null,citations:Array.isArray(item.citations)?item.citations.map(citation):item.citations})):value.messages};
  return value && typeof value==='object' && 'title' in value ? conversation(value) : value;
}
export class SeleryClient {
  constructor(public baseUrl:string, private getToken:()=>string|null = ()=>null) {}
  async request<T>(path:string,schema:z.ZodType<T>,init:RequestInit={}):Promise<T>{
    const token=this.getToken();
    const response=await fetch(`${this.baseUrl}/api/v1${path}`,{...init,credentials:'include',headers:{'Content-Type':'application/json',...(token?{Authorization:`Bearer ${token}`} : {}),...init.headers}});
    if(!response.ok){const body=await response.json().catch(()=>({detail:'Request failed'}));throw new ApiError(response.status,typeof body.detail==='string'?body.detail:JSON.stringify(body.detail));}
    return schema.parse(chatCompatibility(path,await response.json()));
  }
  login(password:string){return this.request('/auth/login',z.object({token:z.string(),expires_in:z.number()}),{method:'POST',body:JSON.stringify({password})});}
  passkeyStatus(){return this.request('/auth/passkeys/status',PasskeyStatusSchema);}
  passkeys(){return this.request('/auth/passkeys',z.array(PasskeyInfoSchema));}
  passkeyRegisterOptions(password:string,name:string){return this.request('/auth/passkeys/register/options',PasskeyOptionsSchema,{method:'POST',body:JSON.stringify({password,name})});}
  passkeyRegisterVerify(ceremony_id:string,credential_json:string){return this.request('/auth/passkeys/register/verify',PasskeyInfoSchema,{method:'POST',body:JSON.stringify({ceremony_id,credential_json})});}
  passkeyLoginOptions(){return this.request('/auth/passkeys/login/options',PasskeyOptionsSchema,{method:'POST'});}
  passkeyLoginVerify(ceremony_id:string,credential_json:string){return this.request('/auth/passkeys/login/verify',SessionResponseSchema,{method:'POST',body:JSON.stringify({ceremony_id,credential_json})});}
  removePasskey(id:string){return this.request('/auth/passkeys/'+encodeURIComponent(id)+'/delete',z.object({ok:z.boolean()}),{method:'POST'});}
  logout(){return this.request('/auth/logout',z.object({ok:z.boolean()}),{method:'POST'});}
  watchlist(){return this.request('/watchlist',WatchlistResponseSchema);}
  chart(symbol:string,timeframe:Timeframe='5m',feed:Feed='iex',limit=1000){return this.request(`/chart/${encodeURIComponent(symbol)}?timeframe=${timeframe}&feed=${feed}&limit=${limit}`,ChartResponseSchema);}
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
  reports(limit=10,offset=0){return this.request(`/research?limit=${limit}&offset=${offset}`,z.array(ResearchReportSchema));}
  chat(input:Omit<ChatRequest,'activity_id'> & {activity_id?:string|null}){return this.request('/chat',ChatResponseSchema,{method:'POST',body:JSON.stringify(input)});}
  conversations(limit=50,offset=0,q=''){return this.request(`/conversations?limit=${limit}&offset=${offset}&q=${encodeURIComponent(q)}`,z.array(ConversationSchema));}
  createConversation(symbol:string,options:{signal_id?:string;timeframe?:Timeframe;chart_start?:number;chart_end?:number}={}){return this.request('/conversations',ConversationSchema,{method:'POST',body:JSON.stringify({symbol,...options})});}
  renameConversation(id:string,title:string){return this.request('/conversations/'+encodeURIComponent(id)+'/rename',ConversationSchema,{method:'POST',body:JSON.stringify({title})});}
  summarizeConversation(id:string){return this.request('/conversations/'+encodeURIComponent(id)+'/summary',ConversationSchema,{method:'POST'});}
  conversation(id:string){return this.request('/conversations/'+encodeURIComponent(id),ConversationDetailSchema);}
  conversationChart(id:string){return this.request('/conversations/'+encodeURIComponent(id)+'/chart',ChartResponseSchema);}
  sendConversationMessage(id:string,message:string,requestId:string,timeframe:Timeframe='5m'){return this.request('/conversations/'+encodeURIComponent(id)+'/messages',ConversationDetailSchema,{method:'POST',body:JSON.stringify({message,request_id:requestId,timeframe})});}
  deleteConversation(id:string){return this.request('/conversations/'+encodeURIComponent(id)+'/delete',z.object({ok:z.boolean()}),{method:'POST'});}
  publicSources(){return this.request('/public-traders/sources',z.array(PublicSourceSchema));}
  publicTraders(query:Record<string,string|number>={}){return this.request('/public-traders?'+new URLSearchParams(Object.entries(query).map(([k,v])=>[k,String(v)])),PublicTraderPageSchema);}
  publicActivity(query:Record<string,string|number>={}){return this.request('/public-traders/activity?'+new URLSearchParams(Object.entries(query).map(([k,v])=>[k,String(v)])),PublicActivityPageSchema);}
  publicActivityDetail(id:string,includeChart=true){return this.request('/public-traders/activity/'+encodeURIComponent(id)+(includeChart?'':'?include_chart=false'),PublicActivityDetailSchema);}
  refreshPublicTraders(trader_id:string|null=null){return this.request('/public-traders/refresh',PublicRefreshResultSchema,{method:'POST',body:JSON.stringify({trader_id})});}
  jobs(){return this.request('/jobs',z.array(JobSchema));}
  domain(){return this.request('/domain/SPY',z.record(z.unknown()));}
  modelStatus(){return this.request('/models',z.record(z.unknown()));}
  async streamTicket(){return this.request('/auth/stream-ticket',z.object({ticket:z.string()}),{method:'POST'});}
}
