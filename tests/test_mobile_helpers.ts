import assert from 'node:assert/strict';
import { z } from 'zod';
import { encodeCache, parseCache } from '../packages/shared/src/cache';
import { connectResearchStream, type StreamSocket } from '../packages/shared/src/stream';

const schema = z.object({ price: z.number() });
assert.deepEqual(parseCache(encodeCache({price: 100}, 1000), schema, {now: 2000}), {data: {price:100}, retrievedAt:1000, stale:false});
assert.equal(parseCache(encodeCache({price:100}, 1000), schema, {now:31_000})?.stale, true);
assert.equal(parseCache(encodeCache({price:100}, 3000), schema, {now:2000})?.stale, true);
assert.equal(parseCache('{broken', schema), null);
assert.equal(parseCache(JSON.stringify({data:{price:'bad'},at:1000}), schema), null);
assert.equal(parseCache(JSON.stringify({version:2,data:{price:100},retrievedAt:1000}), schema), null);
assert.equal(parseCache(JSON.stringify({data:{price:100},at:1000}), schema,{now:2000})?.stale,false);

async function verifyStream() {
 const sockets: StreamSocket[] = [], delays:number[] = [], callbacks:Array<()=>void> = [], statuses:string[] = [], events:unknown[]=[];
 let tickets=0, invalid=0, closed=0;
 const stream=connectResearchStream({baseUrl:'https://api.example.test/',ticket:async()=>({ticket:`ticket ${++tickets}`}),
  socket:url=>{assert.match(url,/^wss:\/\/api.example.test\/api\/v1\/stream\?ticket=ticket%20\d$/);const s:StreamSocket={onopen:null,onmessage:null,onerror:null,onclose:null,close(){closed++;}};sockets.push(s);return s;},
  onStatus:status=>statuses.push(status),onEvent:event=>events.push(event),onInvalidEvent:()=>invalid++,
  schedule:(callback,delay)=>{callbacks.push(callback);delays.push(delay);return callbacks.length;},cancel:()=>{},
 });
 await Promise.resolve();
 sockets[0].onopen?.();
 sockets[0].onmessage?.({data:JSON.stringify({type:'heartbeat',timestamp:'2026-09-09T12:00:00Z',data:{}})});
 sockets[0].onmessage?.({data:'not-json'});
 assert.equal(events.length,1);assert.equal(invalid,1);
 sockets[0].onclose?.();sockets[0].onerror?.();assert.deepEqual(delays,[1000]);
 callbacks.shift()!();await Promise.resolve();
 assert.equal(tickets,2);assert.equal(sockets.length,2);
 sockets[1].onclose?.();assert.deepEqual(delays,[1000,2000]);
 stream.stop();assert.equal(statuses.at(-1),'closed');assert.ok(closed>0);
 callbacks.shift()!();await Promise.resolve();assert.equal(sockets.length,2);
}
verifyStream().then(() => console.log('Shared cache and reconnect tests passed')).catch(error => { console.error(error); process.exitCode = 1; });
