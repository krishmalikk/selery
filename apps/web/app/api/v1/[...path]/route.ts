import {NextRequest,NextResponse} from 'next/server';
const allowed=new Set(['auth','watchlist','chart','news','settings','strategies','outcomes','journal','alerts','research','chat','jobs','domain','models']);
async function proxy(request:NextRequest,{params}:{params:Promise<{path:string[]}>}){
 const {path}=await params;
 if(!allowed.has(path[0])||path.some(p=>p==='..'||p.includes('/')))return NextResponse.json({detail:'Unknown resource'},{status:404});
 const origin=process.env.SELERY_API_URL||'http://127.0.0.1:8000';
 try{
 const url=new URL(`/api/v1/${path.map(encodeURIComponent).join('/')}${request.nextUrl.search}`,origin);
 const headers=new Headers({'content-type':'application/json'}); headers.set('x-forwarded-proto',request.nextUrl.protocol.replace(':','')); const cookie=request.headers.get('cookie');if(cookie)headers.set('cookie',cookie);
 // Browser calls must be same-origin; credentials are never sent to a caller-controlled host.
 if(request.method!=='GET'){const incoming=request.headers.get('origin');if(incoming&&incoming!==request.nextUrl.origin)return NextResponse.json({detail:'Origin rejected'},{status:403});}
 const response=await fetch(url,{method:request.method,headers,body:request.method==='GET'?undefined:await request.text(),cache:'no-store',signal:AbortSignal.timeout(30000)});
 const outputHeaders=new Headers({'content-type':response.headers.get('content-type')||'application/json','cache-control':'no-store'});
 for(const cookie of response.headers.getSetCookie())outputHeaders.append('set-cookie',cookie);
 const body=await response.text();
 if(path.join('/')==='auth/login'&&response.ok){const data=JSON.parse(body);return new NextResponse(JSON.stringify({...data,token:''}),{status:response.status,headers:outputHeaders});}
 return new NextResponse(body,{status:response.status,headers:outputHeaders});
 }catch{return NextResponse.json({detail:'Research service unavailable. Check the backend connection.'},{status:503});}
}
export const GET=proxy;export const POST=proxy;export const dynamic='force-dynamic';
