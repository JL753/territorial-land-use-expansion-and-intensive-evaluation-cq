"use strict";
(function(){
const $=id=>document.getElementById(id);
const fmtDate=value=>value?new Date(value).toLocaleString("zh-CN",{hour12:false}):"—";
function addCard(item){
 const article=document.createElement("article");article.className="dc-card";
 const head=document.createElement("div");head.className="dc-card-head";
 const title=document.createElement("div"),h=document.createElement("h3"),provider=document.createElement("div");h.textContent=item.name;provider.className="provider";provider.textContent=item.key.toUpperCase();title.append(h,provider);
 const tag=document.createElement("span");tag.className="tag";tag.textContent=item.category;head.append(title,tag);article.append(head);
 const dl=document.createElement("dl");
 for(const [k,v] of [["覆盖范围",item.coverage],["空间分辨率",item.resolution],["数据时效",item.freshness],["更新机制",item.mode],["当前状态",item.status]]){
  const dt=document.createElement("dt"),dd=document.createElement("dd");dt.textContent=k;dd.textContent=String(v??"—");dl.append(dt,dd);
 }
 article.append(dl);const link=document.createElement("a");link.href=item.url;link.target="_blank";link.rel="noopener noreferrer";link.textContent="打开数据源 ↗";article.append(link);
 const state=document.createElement("div");state.className="check-state";state.textContent=item.latest_check?"最近检查："+fmtDate(item.latest_check):"尚无自动检查记录";article.append(state);
 $("source-grid").append(article);
}
function renderRuns(runs){
 const body=$("update-history");body.replaceChildren();
 if(!runs.length){const tr=document.createElement("tr"),td=document.createElement("td");td.colSpan=4;td.textContent="暂无检查记录";tr.append(td);body.append(tr);return;}
 for(const run of runs){const tr=document.createElement("tr");
  [fmtDate(run.happened_at),run.feed,run.status,run.detail].forEach((value,index)=>{const td=document.createElement("td");td.textContent=String(value??"—");if(index===2)td.className="status-"+run.status;tr.append(td);});
  body.append(tr);
 }
}
async function load(){
 const response=await fetch("/api/v1/data-sources/");if(!response.ok)throw new Error("数据源目录读取失败");
 const data=await response.json();const [lcResponse,osmResponse]=await Promise.all([fetch("/api/v1/landcover-series/").catch(()=>null),fetch("/api/v1/osm-status/").catch(()=>null)]);const lc=lcResponse&&lcResponse.ok?await lcResponse.json():{status:"not_built",years:[]};const osm=osmResponse&&osmResponse.ok?await osmResponse.json():{status:"not_built",counts:{}};$("source-count").textContent=data.sources.length+2;
 const allYears=[...new Set([...data.research.years,...(lc.years||[])])].sort((a,b)=>a-b);$("year-count").textContent=allYears.length;$("year-list").textContent=allYears.join("、");
 $("research-version").textContent=data.research.version?"#"+data.research.version:"基线";$("research-source").textContent=data.research.source;
 $("year-list").textContent=data.research.years.join("、")+(lc.years?.length?"；CLCD 遥感："+lc.years[0]+"—"+lc.years.at(-1)+"（"+lc.years.length+"期）":"；CLCD 年度栅格尚未生成");
 $("source-grid").replaceChildren();data.sources.forEach(addCard);addCard({key:"clcd-derived",name:"CLCD 21 区县年度统计",category:"年度遥感处理",coverage:lc.years?.length?lc.years[0]+"—"+lc.years.at(-1)+"；"+lc.years.length+" 个可用年份":"等待执行年度栅格处理",resolution:"30 m 原始像元",freshness:"年度产品发布后更新",mode:"远程 COG 窗口读取；不下载整幅中国栅格",status:lc.status==="ready"?"已生成 "+(lc.rows||[]).length+" 条区年遥感记录":"尚未生成；运行 tools/build_clcd_district_series.py",url:"https://zenodo.org/records/18180184"});addCard({key:"geofabrik",name:"Geofabrik 重庆 OSM 区域快照",category:"建筑道路设施",coverage:"重庆区域 PBF；按 21 区县边界裁剪",resolution:"要素级",freshness:"每日快照",mode:"区域快照下载后解析；需检查 OSM 覆盖",status:osm.status==="ready"?"已生成："+Object.values(osm.counts.buildings||{}).reduce((a,b)=>a+b,0)+" 个建筑要素":"待下载重庆 PBF 并解析",url:"https://download.geofabrik.de/asia/china.html"});renderRuns(data.runs);
}
$("check-updates").addEventListener("click",async()=>{
 const button=$("check-updates");button.disabled=true;button.textContent="正在检查…";$("dc-status").textContent="正在连接 Zenodo 检查 CLCD 最新公开版本。";
 try{
  const token=document.cookie.match(/(?:^|; )csrftoken=([^;]+)/)?.[1]||"";
  const response=await fetch("/api/v1/data-updates/check/",{method:"POST",headers:{"Content-Type":"application/json","X-CSRFToken":token},body:"{}"});
  const data=await response.json();if(!response.ok)throw new Error(data.detail||data.error||"检查失败");
  $("dc-status").textContent=data.detail+"。本次只检查元数据，没有下载或覆盖栅格。";
  await load();
 }catch(error){$("dc-status").textContent="在线版本检查暂不可用："+error.message;}
 finally{button.disabled=false;button.textContent="立即检查 CLCD 版本";}
});
load().then(()=>$("dc-status").textContent="已读取当前发布版本和数据源目录。").catch(error=>$("dc-status").textContent=error.message);
})();
