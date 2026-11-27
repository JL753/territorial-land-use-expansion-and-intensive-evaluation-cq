"use strict";
(function(){
  if(document.getElementById("cq-ai-launcher"))return;
  const el=(tag,cls,text)=>{const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n;};
  const csrf=()=>document.cookie.match(/(?:^|; )csrftoken=([^;]+)/)?.[1]||"";
  const get=id=>document.getElementById(id);
  function context(){
    const val=ids=>{for(const id of ids){const n=get(id);if(n&&n.value)return n.value;}return "";};
    const title=get("district-name")?.textContent||get("city-name")?.textContent||get("district-title")?.textContent||document.querySelector("#district-detail .district-name")?.textContent||get("profile-name")?.textContent||"";
    const code=val(["district","city-district","scenario-code","d-district","district-select"]);
    const year=val(["year","d-year","compare-year","mobile-base"]);
    const group=val(["group","d-group"]);
    const metric=val(["metric","district-metric","topic"]);
    return {path:location.pathname,year:year||null,group:group||"",metric:metric||"",district_code:/^\d{6}$/.test(code)?code:null,district_name:title.trim().slice(0,40)};
  }
  const launcher=el("button","cq-ai-launcher");launcher.id="cq-ai-launcher";launcher.type="button";launcher.setAttribute("aria-label","打开山城地研 AI 研究助手");launcher.setAttribute("aria-expanded","false");launcher.innerHTML="<span>AI</span>";
  const panel=el("section","cq-ai-panel");panel.id="cq-ai-panel";panel.setAttribute("role","dialog");panel.setAttribute("aria-label","山城地研 AI 研究助手");
  const head=el("div","cq-ai-head"),avatar=el("div","cq-ai-avatar","✦"),title=el("div","");title.append(el("div","cq-ai-title","山城 AI 研究助手"),el("span","cq-ai-subtitle","结合当前页面与研究数据回答"));
  const actions=el("div","cq-ai-head-actions"),min=el("button","","—"),close=el("button","","×");min.type=close.type="button";min.setAttribute("aria-label","收起助手");close.setAttribute("aria-label","关闭助手");actions.append(min,close);head.append(avatar,title,actions);
  const ctx=el("div","cq-ai-context","当前页面："+location.pathname);
  const messages=el("div","cq-ai-messages");messages.setAttribute("aria-live","polite");
  const suggestions=el("div","cq-ai-suggestions");
  ["分析当前区县的建设用地变化","解释当前指标和统计口径","哪些数据还需要核验？"].forEach(q=>{const b=el("button","",q);b.type="button";b.addEventListener("click",()=>{input.value=q;send();});suggestions.append(b);});
  const form=el("form","cq-ai-form"),input=el("textarea");input.rows=2;input.maxLength=500;input.placeholder="输入研究问题，例如：江北区近年建设用地扩张情况？";input.setAttribute("aria-label","研究问题");
  const sendButton=el("button","cq-ai-send","发送");sendButton.type="submit";form.append(input,sendButton);
  const foot=el("div","cq-ai-foot","回答仅基于当前已入库数据；缺少数据时会明确提示。");
  panel.append(head,ctx,messages,suggestions,form,foot);document.body.append(launcher,panel);
  function addMessage(text,role,meta){
    const box=el("div","cq-ai-message "+role);box.textContent=text;
    if(meta){const small=el("small","",meta);box.append(small);}
    messages.append(box);messages.scrollTop=messages.scrollHeight;return box;
  }
  addMessage("你好！我可以查询区县指标、解释扩张与集约评价结果，也可以协助检查数据口径。当前页面上下文会随问题一起提供。","assistant");
  function toggle(open){panel.classList.toggle("is-open",open);launcher.setAttribute("aria-expanded",String(open));if(open){ctx.textContent="当前上下文："+context().path+" · "+(context().year||"未指定年份")+" · "+(context().district_name||"未选区县");input.focus();}}
  launcher.addEventListener("click",()=>toggle(!panel.classList.contains("is-open")));min.addEventListener("click",()=>toggle(false));close.addEventListener("click",()=>toggle(false));
  async function send(){
    const question=input.value.trim();if(!question||sendButton.disabled)return;
    input.value="";addMessage(question,"user");sendButton.disabled=true;sendButton.textContent="…";
    const loading=addMessage("正在检索当前研究数据并组织回答…","assistant cq-ai-loading");
    try{
      const response=await fetch("/api/v1/assistant/",{method:"POST",headers:{"Content-Type":"application/json","X-CSRFToken":csrf()},body:JSON.stringify({question,context:context()})});
      const data=await response.json();if(!response.ok)throw new Error(data.error||"助手服务暂不可用");
      loading.remove();addMessage(data.answer||"没有生成可用回答。","assistant",data.mode==="ollama"?"AI 综合解读 · 本机模型":"数据检索模式 · 尚未配置大语言模型");
    }catch(error){loading.remove();addMessage("暂时无法完成请求："+error.message,"assistant cq-ai-error");}
    finally{sendButton.disabled=false;sendButton.textContent="发送";input.focus();}
  }
  form.addEventListener("submit",event=>{event.preventDefault();send();});
  input.addEventListener("keydown",event=>{if(event.key==="Enter"&&!event.shiftKey){event.preventDefault();send();}});
})();
