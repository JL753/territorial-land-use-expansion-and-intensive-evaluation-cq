"use strict";
(() => {
  const create=(tag,text)=>{
    const el=document.createElement(tag);if(text!=null)el.textContent=text;return el;
  };
  const launch=create("button","AI");
  launch.id="live-launch";launch.type="button";launch.setAttribute("aria-haspopup","dialog");launch.setAttribute("aria-label","打开问山城 AI 研究助手");launch.title="问山城 AI 研究助手";
  const dialog=create("dialog");dialog.id="live-assistant";dialog.setAttribute("aria-labelledby","live-title");
  const form=create("form"),label=create("label","问题"),question=create("input");
  const title=create("h2","山城研究助手");title.id="live-title";
  label.htmlFor="live-question";question.id="live-question";question.required=true;question.maxLength=400;
  question.placeholder="例如 2022 年渝北区的不透水面是多少";
  const close=create("button","关闭");close.type="button";close.className="live-close";
  const ask=create("button","查询");ask.type="submit";
  const answer=create("p");answer.id="live-answer";answer.setAttribute("aria-live","polite");
  const modelAnswer=create("p");modelAnswer.setAttribute("aria-live","polite");
  const interpret=create("button","用本机模型梳理");interpret.hidden=true;interpret.type="button";
  const details=create("details"),summary=create("summary","数据版本与更新记录"),status=create("div");
  const refresh=create("button","刷新页面数据");refresh.type="button";refresh.hidden=true;
  details.append(summary,status,refresh);
  const hints=create("div");hints.className="live-hints";
  for(const tip of ["总结当前研究数据","1985—2025 年建设用地变化趋势","当前区县的三维数据覆盖情况","哪些数据待复核？"]){
    const button=create("button",tip);button.type="button";button.onclick=()=>{question.value=tip;form.requestSubmit();};hints.append(button);
  }
  form.append(label,question,ask);
  dialog.append(close,title,hints,form,answer,interpret,modelAnswer,details);
  document.body.append(launch,dialog);
  if(location.pathname==="/mobile.html")document.body.classList.add("live-mobile");
  const savedPanel={version:null,rows:[]};
  let sequence=0,resultQuestion="",evidence="",statusSnapshot=null;
  const translate={published:"已发布",unchanged:"未变化",failed:"失败，保留上次快照",restored:"已恢复",checked:"已检查",
    research:"区年研究",osm:"虎溪地图",clcd:"CLCD 年度土地覆盖"};
  async function getJSON(path){
    const response=await fetch(path);
    if(!response.ok)throw Error("数据暂不可用");
    return response.json();
  }
  function time(value){
    return value?new Intl.DateTimeFormat("zh-CN",{timeZone:"Asia/Shanghai",dateStyle:"medium",timeStyle:"short"})
      .format(new Date(value)):"仓库基线";
  }
  async function showStatus(){
    status.textContent="正在检查发布状态…";
    try{
      const data=await getJSON("/api/v1/research/status/");
      statusSnapshot=data;
      status.replaceChildren(
        create("p",`区年版本 ${data.research.id??"基线"} · ${data.research.years.join("、")} · ${data.research.observations} 条 · ${time(data.research.published_at)}`),
        create("p",`虎溪地图 ${data.map.observed_at.slice(0,10)} · ${data.panel_feed?"已配置区年数据源":"区年观测由批准的数据包发布"}`)
      );
      for(const run of data.runs.slice(0,5)){
        status.append(create("p",`${time(run.happened_at)} · ${translate[run.feed]} · ${translate[run.status]}`));
      }
      if(data.map_versions.length)status.append(create("p","已保留的地图版本："+data.map_versions.map(v=>"#"+v.id).join("、")));
      if(data.versions.length)status.append(create("p","已保留的研究版本："+data.versions.map(v=>"#"+v.id).join("、")));
    }catch{status.textContent="实时发布记录不可用，仍可查询设备当前可读取的数据。";}
  }
  async function retrieve(){
    try{
      const data=await getJSON("/api/v1/research/panel/");
      if(savedPanel.version&&savedPanel.version!==data.version)refresh.hidden=false;
      savedPanel.version=data.version;savedPanel.rows=enrichObservations(data.observations);
      return {rows:savedPanel.rows,source:data.version==="base"?"仓库基线":"研究版本 #"+data.version};
    }catch{
      if(savedPanel.rows.length)return {rows:savedPanel.rows,source:"最近读取的"+(savedPanel.version==="base"?"仓库基线":"研究版本 #"+savedPanel.version)};
      const rows=enrichObservations(await getJSON("/dashboard.json"));
      return {rows,source:"设备可读取的快照"};
    }
  }
  function context(rows){
    const options=[...document.querySelectorAll("#year,#d-year,#year-select,#city-years [aria-pressed=true],#years [aria-pressed=true]")];
    const y=Number(options.map(x=>x.value||x.textContent).find(v=>rows.some(row=>row.year===Number(v))));
    const selected=document.querySelector("#district-select, #city-district")?.selectedOptions?.[0]?.textContent||document.querySelector("[data-selected-district]")?.getAttribute("data-selected-district");
    const detail=document.querySelector("#district-detail .district-name")?.textContent;
    const district=(selected||detail||"").trim();
    return {year:y||Math.max(...rows.map(row=>row.year)),group:document.querySelector("#group, #d-group")?.value||"",district};
  }
  async function mapAnswer(){
    let snap;
    try{snap=(await getJSON("/api/v1/research/map/")).osm;}
    catch{snap=(await getJSON("/city/manifest.json")).osm;}
    return `虎溪及周边 · ${snap.date.slice(0,10)} OSM 快照\n${snap.buildings} 个建筑轮廓、${snap.poi} 条设施记录、${snap.roads} 条道路线。\n数据仅覆盖该片区，建筑高度依据见两江立体图。`;
  }
  form.onsubmit=async event=>{
    event.preventDefault();
    const query=question.value.trim();if(!query)return;
    const current=++sequence;
    answer.textContent="正在查找数据…";interpret.hidden=true;modelAnswer.textContent="";
    try{
      let text;
      if(/虎溪/.test(query)&&/建筑|设施|道路|地图/.test(query))text=await mapAnswer();
      else{
        const data=await retrieve(),c=context(data.rows);
        const key=document.querySelector("#metric, #metric-select, #d-metric")?.value||"built_km2";
        const contextualQuery=c.district&&!query.includes(c.district)?c.district+" "+query:query;
        text=data.source+"\n"+researchAnswer(contextualQuery,data.rows,c.year,c.group,key);
      }
      if(current!==sequence)return;
      resultQuestion=query;evidence=text;answer.textContent=text;
      if(statusSnapshot?.model)interpret.hidden=false;
      else getJSON("/api/config").then(data=>{if(current===sequence)interpret.hidden=!data.model;}).catch(()=>{});
    }catch{if(current===sequence)answer.textContent="当前没有可读取的研究快照。";}
  };
  interpret.onclick=async()=>{
    const current=sequence;interpret.disabled=true;modelAnswer.textContent="正在梳理已核验的证据…";
    const token=document.cookie.match(/(?:^|; )csrftoken=([^;]+)/)?.[1]||"";
    try{
      const response=await fetch("/api/interpret",{method:"POST",headers:{"Content-Type":"application/json","X-CSRFToken":token},
        body:JSON.stringify({question:resultQuestion,evidence})});
      if(!response.ok)throw Error("模型暂不可用");
      const data=await response.json();
      if(current===sequence)modelAnswer.textContent=data.answer;
    }catch{
      if(current===sequence)modelAnswer.textContent="本机模型暂不可用。";
    }finally{interpret.disabled=false;}
  };
  refresh.onclick=()=>location.reload();
  launch.onclick=()=>{dialog.showModal();showStatus();question.focus();};
  close.onclick=()=>dialog.close();
  details.ontoggle=()=>{if(details.open)showStatus();};
  const openedVersion=retrieve().catch(()=>{});
  window.addEventListener("focus",()=>openedVersion.then(()=>retrieve()).catch(()=>{}));
})();
