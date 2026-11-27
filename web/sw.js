const CACHE="cq-land-study-v9";
const assets=["/","/style.css","/analysis.js","/app.js","/manifest.webmanifest","/icon192.png","/icon512.png","/dashboard.json","/districts.geojson","/client-utils.js","/mobile.html","/mobile.css","/mobile.js","/mobile.webmanifest","/desktop.html","/desktop.css","/desktop.js","/river-ink.webp","/rivers.geojson","/charts.js","/vendor/echarts-6.0.0.min.js"];
self.addEventListener("install",event=>event.waitUntil((async()=>{
  const cache=await caches.open(CACHE);
  await cache.addAll(assets);
  // Alternate study snapshots may omit the published model report.
  await cache.add("/api/v1/analysis/").catch(()=>{});
  await self.skipWaiting();
})()));
self.addEventListener("activate",event=>event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith("cq-land-study-")&&k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));
self.addEventListener("fetch",event=>{
  const url=new URL(event.request.url);
  if(event.request.method!=="GET"||url.origin!==self.location.origin||(!assets.includes(url.pathname)&&url.pathname!=="/api/v1/analysis/"))return;
  event.respondWith((async()=>{
    const cache=await caches.open(CACHE);
    try{
      const response=await fetch(event.request);
      if(response.ok)await cache.put(event.request,response.clone());
      return response;
    }catch(error){return await cache.match(event.request)||Response.error();}
  })());
});
