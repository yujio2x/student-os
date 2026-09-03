const CACHE_NAME="student-os-shell-v7";
const PUBLIC_SHELL=["/","/static/styles.css","/static/app.js","/static/account.js","/static/photo.js","/static/restore.js","/static/pwa.js","/static/manifest.webmanifest","/static/icon.svg","/static/icon-192.png","/static/icon-512.png"];

self.addEventListener("install",event=>{
  event.waitUntil(caches.open(CACHE_NAME).then(cache=>cache.addAll(PUBLIC_SHELL)));
  self.skipWaiting();
});

self.addEventListener("activate",event=>{
  event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(key=>key.startsWith("student-os-shell-")&&key!==CACHE_NAME).map(key=>caches.delete(key)))));
  self.clients.claim();
});

self.addEventListener("fetch",event=>{
  const url=new URL(event.request.url);
  if(event.request.method!=="GET"||url.origin!==self.location.origin||url.pathname.startsWith("/api/")||url.pathname.startsWith("/admin"))return;
  if(!PUBLIC_SHELL.includes(url.pathname)||(url.pathname==="/"&&url.search))return;
  event.respondWith(fetch(event.request).then(response=>{
    if(response.ok)caches.open(CACHE_NAME).then(cache=>cache.put(event.request,response.clone()));
    return response;
  }).catch(()=>caches.match(url.pathname)));
});
