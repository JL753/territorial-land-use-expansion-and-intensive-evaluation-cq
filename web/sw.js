const CACHE="cq-land-study-v14";
const cityAssets=["/city.html","/city.js","/city.css","/vendor/maplibre-5.16.0.js","/vendor/maplibre-5.16.0.css",
  "/city/manifest.json","/city/buildings.geojson","/city/poi.geojson","/city/roads.geojson",
  ...[2010,2015,2020,2022].map(y=>"/city/cover-"+y+".png"),
  ...[2015,2020,2022].map(y=>"/city/change-"+y+".png")];
const assets=["/","/live.js","/live.css","/style.css","/analysis.js","/app.js","/manifest.webmanifest","/icon192.png","/icon512.png","/dashboard.json","/districts.geojson","/client-utils.js","/mobile.html","/mobile.css","/mobile.js","/mobile.webmanifest","/desktop.html","/desktop.css","/desktop.js","/river-ink.webp","/rivers.geojson","/charts.js","/vendor/echarts-6.0.0.min.js","/dashboard3d.html","/dashboard3d.css","/dashboard3d.js","/guide.html","/guide.css","/guide.js"];
self.addEventListener("install",event=>event.waitUntil((async()=>{
  const cache=await caches.open(CACHE);
  await cache.addAll(assets);
  // Alternate study snapshots may omit the published model report.
  await Promise.all(["/api/v1/analysis/","/api/v1/recent-observations/"].map(path=>cache.add(path).catch(()=>{})));
  await self.skipWaiting();
})()));
self.addEventListener("activate",event=>event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith("cq-land-study-")&&k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));
self.addEventListener("message",event=>{
  if(event.data==="cache-city")event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(cityAssets)).catch(()=>{}));
});
self.addEventListener("fetch",event=>{
  const url=new URL(event.request.url);
  if(url.pathname.startsWith("/api/v1/research/"))return;
  const preview=/^\/city\/(cover|change)-20[0-9]{2}\.png$/.test(url.pathname);
  if(event.request.method!=="GET"||url.origin!==self.location.origin||(!assets.includes(url.pathname)&&!cityAssets.includes(url.pathname)&&!preview&&!["/api/v1/analysis/","/api/v1/recent-observations/"].includes(url.pathname)))return;
  event.respondWith((async()=>{
    const cache=await caches.open(CACHE);
    try{
      const response=await fetch(event.request);
      if(response.ok)await cache.put(event.request,response.clone());
      return response;
    }catch(error){return await cache.match(event.request)||Response.error();}
  })());
});
