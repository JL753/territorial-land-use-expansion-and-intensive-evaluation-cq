const CACHE="cq-land-study-v5";
const assets=["/","/style.css","/analysis.js","/app.js","/manifest.webmanifest","/icon192.png","/icon512.png","/dashboard.json","/districts.geojson","/client-utils.js","/mobile.html","/mobile.css","/mobile.js","/mobile.webmanifest","/desktop.html","/desktop.css","/desktop.js"];
self.addEventListener("install",event=>event.waitUntil(caches.open(CACHE).then(c=>c.addAll(assets)).then(()=>self.skipWaiting())));
self.addEventListener("activate",event=>event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith("cq-land-study-")&&k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));
self.addEventListener("fetch",event=>{
  const url=new URL(event.request.url);
  if(event.request.method!=="GET"||url.origin!==self.location.origin||!assets.includes(url.pathname))return;
  event.respondWith((async()=>{
    const cache=await caches.open(CACHE);
    try{
      const response=await fetch(event.request);
      if(response.ok)await cache.put(event.request,response.clone());
      return response;
    }catch(error){return await cache.match(event.request)||Response.error();}
  })());
});
