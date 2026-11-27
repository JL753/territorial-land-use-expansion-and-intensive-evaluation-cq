"use strict";
(function(){
const $=id=>document.getElementById(id);
const esc=value=>String(value??"—");
const fmtDate=value=>value?new Date(value).toLocaleString("zh-CN",{hour12:false}):"—";
function card(item){
 const article=document.createElement("article");article.className="dc-card";
 const head=document.createElement("div");head.className="dc-card-head";
 const title=document.createElement("div"),h=document.createElement("h3"),provider=document.createElement("div");h.textContent=item.name;provider.className="provider";provider.textContent=item.provider;title.append(h,provider);
 const tag=document.createElement("span");tag.className="tag";tag.textContent=item.category;head.append(title,tag);article.append(head);
 const dl=document.createElement("dl");
 for(const [k,v] of [["时间覆盖",item.coverage],["空间分辨率",item.resolution],["更新机制",item.update_mode],["数据时效",item.freshness],["优先级",item.priority]]){
  const dt=document.createElement("dt"),dd=document.createElement("dd");dt.textContent=k;dd.textContent=esc(v);dl.append(dt,dd);
 }
 article.append(dl);const desc=document.createElement("p");desc.className="desc";desc.textContent=item.description;article.append(desc);
 const a=document.createElement("a");a.href=item.url;a.target="_blank";a.rel="noopener noreferrer";a.textContent="打开数据源 ↗";article.append(a);
 const state=document.createElement("div");state.className="check-state";state.textContent=item.checkable?"● 支持在线版本检查":"○ 需要按来源页面核验";article.append(state);return article;
}
function renderHistory(runs){
 const body=$("update-history");body.replaceChildren();
 if(!runs.length){const tr=document.createElement("tr"),td=document.createElement("td");td.colSpan=5;td.textContent="暂无检查记录";tr.append(td);body.append(tr);return;}
 for(const run of runs){
  const tr=document.createElement("tr");
  [fmtDate(run.created_at),run.source_key,run.action,run.status,run.version||run.message||"—"].forEach((value,index)=>{const td=document.createElement("td");td.textContent=value;if(index===3)td.className="status-"+run.status;tr.append(td);});
  body.append(tr);
 }
}
async function load(){
 const response=await fetch("/api/v1/data-sources/");if(!response.ok)throw new Error("数据源目录读取失败");
 const data=await response.json();$("source-count").textContent=data.sources.length;$("checkable-count").textContent=data.sources.filter(x=>x.checkable).length;
 $("last-check").textContent=data.runs.length?fmtDate(data.runs[0].created_at):"尚未检查";
 const grid=$("source-grid");grid.replaceChildren();data.sources.forEach(item=>grid.append(card(item)));renderHistory(data.runs);
}
$("check-updates").addEventListener("click",async()=>{
 const button=$("check-updates");button.disabled=true;button.textContent="正在检查…";$("dc-status").textContent="正在连接公开数据源检查最新版本，请稍候。";
 try{
  const token=document.cookie.match(/(?:^|; )csrftoken=([^;]+)/)?.[1]||"";
  const response=await fetch("/api/v1/data-updates/check/",{method:"POST",headers:{"Content-Type":"application/json","X-CSRFToken":token},body:JSON.stringify({source_keys:["clcd"]})});
  const data=await response.json();if(!response.ok)throw new Error(data.error||"检查失败");
  const result=data.results[0];$("dc-status").textContent=result.status==="success"?"CLCD 版本检查完成："+(result.details?.latest_year||result.version||"已获取元数据")+"；未自动覆盖现有研究数据。":"检查完成，但数据源返回："+(result.message||result.status);
  await load();
 }catch(error){$("dc-status").textContent="暂时无法完成在线检查："+error.message;}
 finally{button.disabled=false;button.textContent="立即检查可用新版本";}
});
load().then(()=>$("dc-status").textContent="数据源目录已加载。点击右上角按钮可实时检查 CLCD 最新公开版本。").catch(error=>$("dc-status").textContent=error.message);
})();
