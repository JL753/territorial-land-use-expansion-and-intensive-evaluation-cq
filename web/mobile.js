"use strict";
if(window.CQLandAndroid)document.querySelector("header a").hidden=true;
let observations=[],districts=[],selected,year,tab="explore";
let favorites=new Set(readLocal("cq-pocket-favorites",[]));
const pages=["explore","profile","saved","pocket-assistant"];
function show(next){
  tab=next;
  for(const id of pages)get(id).hidden=id!==tab;
  for(const button of document.querySelectorAll("nav button")){
    button.setAttribute("aria-current",button.dataset.mobile===(tab==="profile"?"explore":tab)?"page":"false");
  }
  if(next==="saved")list(get("favorites"),districts.filter(r=>favorites.has(r.code)));
  window.scrollTo(0,0);
}
function list(element,items){
  element.replaceChildren(...items.map(r=>{
    const button=make("button",null,"district-item"),label=make("div");
    label.append(make("strong",r.district),make("br"),make("small",r.group+" · "+r.code));
    button.append(label,make("span",favorites.has(r.code)?"★":"›"));
    button.onclick=()=>{selected=r.code;profile();show("profile");};
    return button;
  }));
  if(!items.length)element.textContent=element.id==="favorites"?"收藏的区县会显示在这里。":"没有匹配区县。";
}
function explore(){
  const q=get("find").value.trim();
  list(get("district-list"),districts.filter(r=>r.district.includes(q)||r.code.includes(q)));
}
function profile(){
  const rows=observations.filter(r=>r.code===selected).sort((a,b)=>a.year-b.year);
  const row=rows.find(r=>r.year===year)??rows.at(-1);
  year=row.year;
  get("district-title").textContent=row.district;
  get("area").textContent=row.group+" · "+row.code;
  get("favorite").textContent=favorites.has(row.code)?"★ 已收藏":"☆ 收藏";
  get("favorite").setAttribute("aria-pressed",String(favorites.has(row.code)));
  get("years").replaceChildren(...rows.map(r=>{
    const b=make("button",r.year);b.setAttribute("aria-pressed",String(r.year===year));b.onclick=()=>{year=r.year;profile();};return b;
  }));
  get("quality").textContent=row.provisional?"本年部分经济指标待复核。四期排名属于探索性评价。":"经济指标采用当年现价。页面排名来自四期探索性评价。";
  get("tiles").replaceChildren(...["built_km2","impervious_share_pct","expansion_km2","built_person_m2","population","nominal_gdp_person_yuan","secondary_share_pct","coverage_gap_pct"].map(k=>{
    const item=make("div",null,"tile");
    item.append(make("small",fields[k][0]),make("strong",format(row[k])),make("span",fields[k][1]));return item;
  }));
  const peak=Math.max(...rows.map(r=>r.built_km2))||1;
  get("history").replaceChildren(...rows.map(r=>{
    const line=make("div",null,"history-row"),bar=make("i");
    bar.style.width=(r.built_km2/peak*100)+"%";
    line.append(make("span",r.year),bar,make("b",format(r.built_km2)+" km²"));return line;
  }));
  const matrix=row.transition_km2;
  get("flow-mobile").textContent=matrix?matrix.map((values,i)=>[classNames[i],i===7?0:values[7]])
    .filter(([,v])=>v>0).sort((a,b)=>b[1]-a[1]).slice(0,3)
    .map(([label,v])=>label+" "+format(v)+" km²").join(" · ")||"本阶段无跨类转入。":"本年无可用的阶段转移数据。";
  get("sources").textContent=[row.source_pop,row.source_gdp,"土地覆盖依据 CLCD 30 m 及固定区归属栅格。"].filter(Boolean).join("\n");
  get("memo").value=readLocal("cq-pocket-note-"+selected,"");
  get("memo-status").textContent="";
  get("export-profile").onclick=()=>saveTable(row.district+"-区年档案.csv",rows,["code","district","year","built_km2",
    "impervious_share_pct","built_person_m2","population","nominal_gdp_person_yuan","secondary_share_pct","expansion_km2",
    "coverage_gap_pct","rank","provisional","source_pop","source_gdp"]);
}
document.querySelectorAll("nav button").forEach(b=>b.onclick=()=>show(b.dataset.mobile));
get("find").oninput=explore;
get("back").onclick=()=>{explore();show("explore");};
get("favorite").onclick=()=>{
  if(favorites.has(selected))favorites.delete(selected);else favorites.add(selected);
  const stored=writeLocal("cq-pocket-favorites",[...favorites]);
  profile();
  if(!stored)get("mobile-status").textContent="设备存储不可用，收藏暂时保留在当前会话。";
};
get("memo").oninput=()=>{
  get("memo-status").textContent=writeLocal("cq-pocket-note-"+selected,get("memo").value)?"已保存到本设备":"设备存储不可用";
};
get("mobile-ask").onsubmit=e=>{
  e.preventDefault();
  if(!observations.length)return;
  const q=get("mobile-question").value.trim();
  get("mobile-answer").textContent=q?researchAnswer(q,observations,year,"","built_km2"):"";
};
studyData().then(data=>{
  observations=data;districts=[...new Map(data.map(r=>[r.code,r])).values()];year=Math.max(...data.map(r=>r.year));
  explore();get("mobile-status").textContent=districts.length+" 个区县 · "+data.length+" 条观测";
  if(!window.CQLandAndroid&&"serviceWorker"in navigator)navigator.serviceWorker.register("/sw.js").catch(()=>{});
}).catch(e=>{get("mobile-status").textContent=e.message;});
