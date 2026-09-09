const CACHE='selery-shell-v1';
self.addEventListener('install',event=>{event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(['/offline.html','/icon-192.png','/icon-512.png'])));self.skipWaiting();});
self.addEventListener('activate',event=>{event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(key=>key!==CACHE).map(key=>caches.delete(key)))));self.clients.claim();});
self.addEventListener('fetch',event=>{
 const url=new URL(event.request.url);
 if(event.request.method!=='GET'||url.origin!==self.location.origin||url.pathname.startsWith('/api/'))return;
 if(event.request.mode==='navigate'){event.respondWith(fetch(event.request).catch(()=>caches.match('/offline.html')));return;}
 if(url.pathname.startsWith('/_next/static/')||url.pathname.startsWith('/icon-'))event.respondWith(caches.open(CACHE).then(async cache=>{const hit=await cache.match(event.request);if(hit)return hit;const response=await fetch(event.request);if(response.ok)await cache.put(event.request,response.clone());return response;}));
});
