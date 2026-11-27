"use strict";
(function(){
const $=id=>document.getElementById(id),KEY="cq-land-graduation-guide-v1";
const stages=[
{title:"任务一｜多源数据标准化与数据库构建",desc:"统一研究范围、时间口径、空间参考和字段定义，建立可追溯的 21 区四期研究数据底座。",tasks:["整理四期 CLCD 数据及分类版本说明","核对 21 区边界、区划代码和历史区划口径","统一 30 m Albers 等积网格与有效像元范围","整理 84 条区年社会经济面板并标注 A/B/C 质量等级","建立数据字典、来源记录和 SHA-256 文件指纹"]},
{title:"任务二｜建设用地扩张时空格局分析",desc:"以 CLCD 类别 8 不透水面作为操作化指标，分析规模、速度、形态和地类来源。",tasks:["计算四期不透水面面积及占比","计算新增、减少、净扩张和年均扩张强度","构建 21 区 × 3 阶段的地类转移矩阵","识别邻接新增、非邻接新增及邻接未知","计算建设用地重心位移、方向和区组差异"]},
{title:"任务三｜建设用地集约利用评价",desc:"构建人口承载与经济产出密度指标体系，以熵权 TOPSIS 评价相对集约利用水平。",tasks:["计算人口密度、单位用地 GDP 和二产增加值密度","2020、2022 年 42 条 A 级观测作为主要比较样本","四期 84 条观测单独开展探索性评价","计算熵权 TOPSIS、等权 TOPSIS 和区内年度排名","开展自定义权重、排名敏感性和单区情景试算"]},
{title:"任务四｜扩张与集约利用综合关系分析",desc:"从区组、时序和区际关联角度解释扩张与集约利用的共同变化，避免过度推断。",tasks:["比较中心城区 9 区与主城新区 12 区","计算扩张强度与期末集约得分的 Spearman 相关","检查指标相关性、名次变化和权重敏感性","开展 2020—2022 时间留出回测并与基线比较","明确名义价格、样本重复和非因果解释限制"]},
{title:"任务五｜WebGIS 系统设计、实现与验证",desc:"将数据、算法和研究结果集成到可交互、可复现的多端研究平台。",tasks:["完成 Django 数据服务、API 和数据导入流程","完成二维地图、CesiumJS 三维专题大屏和 ECharts 图表","完成扩张分析、集约评价、关系分析和情景实验","完成移动端、桌面端、研究助手和成果导出","完成自动化测试、数据审计、论文和答辩交付"]}
];
const weeks=[
["第 01 周","选题与研究边界",["明确 21 区研究范围和四期时点","确定研究问题、技术路线和预期成果"],"选题说明、研究问题清单"],
["第 02 周","文献与开题",["整理土地扩张、集约利用、熵权 TOPSIS 文献","完成开题报告、研究框架和进度表"],"开题报告、文献综述"],
["第 03 周","数据目录与来源核对",["登记 CLCD、边界、年鉴来源和版本","建立数据字典、字段和质量等级"],"数据清单、来源登记表"],
["第 04 周","空间与统计数据标准化",["统一投影、像元网格和共同有效范围","核对 21 区代码及 84 条面板主键"],"标准化数据集、数据库初版"],
["第 05 周","扩张规模测算",["计算四期不透水面面积和占比","计算新增、减少、净增和扩张强度"],"区级扩张指标表、趋势图"],
["第 06 周","扩张形态与转移分析",["计算地类转移矩阵和耕地转入","计算邻接形态、重心位移和方向"],"转移矩阵、形态分析图"],
["第 07 周","集约评价指标体系",["构建人口、GDP、二产用地密度指标","检查缺失值、现价口径和数据等级"],"指标体系、质量核查表"],
["第 08 周","熵权 TOPSIS 评价",["完成 2020/2022 主分析与四期探索分析","计算等权对照、得分和年度排名"],"权重表、评价结果、排名图"],
["第 09 周","敏感性与情景分析",["遍历权重组合并比较名次区间","开展单区指标扰动和重算实验"],"敏感性报告、情景试算表"],
["第 10 周","综合关系与模型验证",["计算区组差异和 Spearman 相关","完成时间留出回测并与中位数基线比较"],"关系分析图、模型验证报告"],
["第 11 周","系统需求与总体设计",["确定用户场景、模块、接口和数据流","完成数据库、系统架构和页面原型"],"需求规格、系统设计说明"],
["第 12 周","后端与研究算法集成",["实现数据导入、API、审计和分析报告","将扩张与 TOPSIS 结果接入服务端"],"可运行后端、API 测试"],
["第 13 周","WebGIS 与三维大屏",["完成二维地图、CesiumJS 三维区县拉伸","完成年份切换、指标图层和区县联动"],"WebGIS 初版、3D 大屏"],
["第 14 周","多端功能与成果输出",["完成移动端、桌面端、研究助手","完成 CSV、JSON、简报和图表导出"],"完整系统初版、用户手册"],
["第 15 周","测试与论文定稿",["完成自动化测试、数据审计和问题修复","完成论文初稿、图表、参考文献和附录"],"测试报告、论文送审稿"],
["第 16 周","答辩与归档",["制作答辩 PPT、演示脚本和问题准备","归档源码、数据、环境、论文和复现说明"],"答辩材料、完整项目归档"]
];
const chapters=[
["第 1 章 绪论","研究背景、意义、国内外研究现状、研究内容、研究方法与技术路线。"],
["第 2 章 理论基础与关键技术","建设用地扩张、集约利用、CLCD、GIS 空间分析、熵权 TOPSIS、WebGIS 与 CesiumJS。"],
["第 3 章 研究区与数据处理","重庆主城都市区 21 区、数据来源、时间尺度、空间标准化、质量控制和数据库设计。"],
["第 4 章 建设用地扩张时空格局","规模变化、扩张速度、新增与减少、地类转移、邻接形态、重心迁移及区组差异。"],
["第 5 章 建设用地集约利用评价","指标体系、标准化、熵权、TOPSIS、等权对照、排名、敏感性及扩张关联。"],
["第 6 章 系统需求分析与总体设计","用户需求、功能需求、非功能需求、系统架构、模块划分、数据库和技术路线。"],
["第 7 章 系统详细设计与实现","数据管理、二维/三维 WebGIS、扩张分析、集约评价、综合分析、多端和成果输出。"],
["第 8 章 系统测试、结论与展望","功能与性能测试、数据审计、结果讨论、研究局限、结论与后续工作。"]
];
const deliverables=[
["开题与研究设计",["开题报告","文献综述与参考文献","研究问题、指标体系和技术路线"]],
["数据与算法成果",["数据目录、数据字典和来源凭证","21 区四期标准化数据集","扩张指标、转移矩阵和重心结果","熵权 TOPSIS、等权和敏感性结果"]],
["系统与工程成果",["Django 源码、数据库迁移和 API","二维 WebGIS 与 CesiumJS 三维大屏","移动端、桌面端和研究助手","测试报告、数据审计和部署说明"]],
["论文与答辩",["论文 Word/PDF 与 Markdown 源稿","论文插图、统计表和附录","答辩 PPT、演示脚本和常见问题","源码、数据、依赖环境和复现说明"]]
];
let state={done:{},note:""};
try{state={...state,...JSON.parse(localStorage.getItem(KEY)||"{}")}}catch(e){}
function save(){try{localStorage.setItem(KEY,JSON.stringify(state));$("save-status").textContent="已保存 · "+new Date().toLocaleString()}catch(e){$("save-status").textContent="浏览器存储不可用，请导出备份"}updateProgress()}
function checkbox(id,text){const label=document.createElement("label"),input=document.createElement("input"),span=document.createElement("span");input.type="checkbox";input.checked=!!state.done[id];input.addEventListener("change",()=>{state.done[id]=input.checked;save()});span.textContent=text;label.append(input,span);return label}
function renderStages(){const root=$("stage-grid");stages.forEach((s,i)=>{const card=document.createElement("article");card.className="stage-card";const h=document.createElement("h3"),p=document.createElement("p"),list=document.createElement("div");h.textContent=s.title;p.textContent=s.desc;list.className="task-list";s.tasks.forEach((t,j)=>list.append(checkbox("stage-"+i+"-"+j,t)));card.append(h,p,list);root.append(card)})}
function renderWeeks(){const root=$("week-grid");weeks.forEach((w,i)=>{const card=document.createElement("article");card.className="week-card";const num=document.createElement("div"),h=document.createElement("h3"),tasks=document.createElement("div"),output=document.createElement("div");num.className="week-num";num.textContent=w[0];h.textContent=w[1];tasks.className="tasks";w[2].forEach((t,j)=>tasks.append(checkbox("week-"+i+"-"+j,t)));output.className="output";output.textContent="阶段交付："+w[3];card.append(num,h,tasks,output);root.append(card)})}
function renderChapters(){const root=$("chapter-grid");chapters.forEach((c,i)=>{const card=document.createElement("article");card.className="chapter-card";const strong=document.createElement("strong"),h=document.createElement("h3"),p=document.createElement("p");strong.textContent="CHAPTER "+String(i+1).padStart(2,"0");h.textContent=c[0];p.textContent=c[1];card.append(strong,h,p);root.append(card)})}
function renderDeliverables(){const root=$("deliverable-grid");deliverables.forEach((d,i)=>{const card=document.createElement("article"),h=document.createElement("h3"),list=document.createElement("div");card.className="deliverable-card";h.textContent=d[0];list.className="items";d[1].forEach((t,j)=>list.append(checkbox("deliver-"+i+"-"+j,t)));card.append(h,list);root.append(card)})}
function updateProgress(){const total=stages.reduce((n,s)=>n+s.tasks.length,0)+weeks.reduce((n,w)=>n+w[2].length,0)+deliverables.reduce((n,d)=>n+d[1].length,0),done=Object.values(state.done).filter(Boolean).length,pct=total?Math.round(done/total*100):0;$("progress-number").textContent=pct+"%";$("progress-bar").style.width=pct+"%";$("progress-caption").textContent=done+" / "+total+" 项任务完成"}
function exportProgress(){const payload={project:"重庆市主城都市区建设用地扩张与集约利用评价",exported_at:new Date().toISOString(),done:state.done,note:state.note,weeks:weeks.map((w,i)=>({week:w[0],topic:w[1],tasks:w[2].map((task,j)=>({task,done:!!state.done["week-"+i+"-"+j]})),deliverable:w[3]}))};const blob=new Blob([JSON.stringify(payload,null,2)],{type:"application/json"}),url=URL.createObjectURL(blob),a=document.createElement("a");a.href=url;a.download="山城地研-毕设进度备份.json";a.click();URL.revokeObjectURL(url)}
renderStages();renderWeeks();renderChapters();renderDeliverables();$("project-note").value=state.note||"";$("project-note").addEventListener("input",e=>{state.note=e.target.value;save()});$("export-progress").addEventListener("click",exportProgress);updateProgress();
})();
