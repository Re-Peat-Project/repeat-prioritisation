// ---------------------------------------------------------------- KHG table: every KHG, every field; filter, sort, page, histograms and sparklines
const R=DATA.rows,M=DATA.meta,N=R.id.length;
const EXTRA_IND={
  n_desa_target:["Target villages","Bluebook target villages in the KHG.",v=>fmt(v,0)],
  n_dmpg:["DMPG villages","Desa Mandiri Peduli Gambut villages in the KHG (SiTMAT portal).",v=>fmt(v,0)],
  n_tma_stations:["Water-table loggers","SiTMAT water-table loggers in the KHG.",v=>fmt(v,0)],
  priority_ha:["Damaged peat (SKEG 2024), ha","Peat in KLH's damage map SKEG 2024 (the PPEG priority area), hectares.",v=>fmt(v,0)],
  c_holders:["Licence holders","Distinct licence holders on the KHG's peat (business licences 2025).",v=>fmt(v,0)],
  c_contested:["Contested peat","Share of the peat where claims conflict: a licence on land released for communities (PPTPKH) or social forestry, or forest estate on PPTPKH land. Part of tenure complexity.",v=>pc(v)],
  depth_known_share:["Peat depth known","Share of the peat with a depth class in the BBSDLP map.",v=>pc(v)],
  lc_known_share:["Land cover known","Share of the peat with a class in KLH's land cover 2022.",v=>pc(v)],
  u_burned_now:["Burned this year","Share of the KHG's peat burned this year (KLHK burnt area 2026, to date).",v=>pc(v,2)]};
const indMeta=k=>IND[k]||EXTRA_IND[k]||[k,"",v=>fmt(v,2)];
const DIMKEY={urgency:"u",stake:"s",complexity:"c",feasibility:"f",people:"p"};
const confChar=["○","◐","●"],confName=["low","medium","high"];

// ---------------------------------------------------------------- columns
const COLS=[];
const col=(o)=>{COLS.push(o);return o};
col({k:"ru337",g:"khg",label:"Rank in 337",tip:"Rank by urgency among KLH's 337 KHG (1 = most urgent).",v:j=>R.ru337[j],f:v=>fmt(v,0),num:true,asc:true});
col({k:"ru",g:"khg",label:"Rank",tip:"Rank by urgency among all scored KHG.",v:j=>R.ru[j],f:v=>fmt(v,0),num:true,asc:true});
col({k:"type",g:"khg",label:"Type",tip:"Type of action from the terciles of urgency, complexity and stake. The small number is the rank within the type.",v:j=>R.type[j],txt:true,
  html:j=>R.type[j]?`<span class="tyb" style="--c:var(--ty${R.type[j]})"${tipAttr(`<b>${R.type[j]} ${esc(t(TYPE_LABEL[R.type[j]]))}</b><br>${esc(t(TYPE_NOTE[R.type[j]]))}`)}>${R.type[j]}</span> <small style="display:inline">${R.rt[j]??""}</small>`:`<span class="hint">${esc(t("not scored"))}</span>`});
col({k:"iv",g:"khg",label:"Intervention",tip:"What the peat needs, from the canal-affected and the open or degraded shares of the peat.",v:j=>R.iv[j],txt:true,
  html:j=>R.iv[j]?`<span class="ivb" style="--c:${IV_COL[R.iv[j]]}">${esc(t(IV_SHORT[R.iv[j]]))}</span>`:""});
col({k:"tim",g:"khg",label:"KLH team",tip:"KLH's team (Tim 1 to 6) for the KHG of the 337 list.",v:j=>R.tim[j]||null,txt:true,f:v=>esc(v||"")});
col({k:"isl",g:"khg",label:"Island",v:j=>R.isl[j],txt:true,f:v=>esc((v||"").replace(/^Pulau /,""))});
col({k:"peat",g:"khg",label:"Peat km2",tip:"KLH peat inside the KHG (PPEG 2026), km2.",v:j=>R.ind.peat_km2?R.ind.peat_km2[j]:null,f:v=>fmt(v,0),num:true});
col({k:"area",g:"khg",label:"KHG km2",tip:"Area of the KHG, km2.",v:j=>R.area[j],f:v=>fmt(v,0),num:true});
col({k:"conf",g:"khg",label:"Data confidence",tip:"High: canals are mapped, there is enough fire signal and enough peat. Medium: two of the three. Low: fewer.",v:j=>R.conf[j],num:true,f:v=>v==null?t("n/a"):confChar[v]+" "+t(confName[v])});
for(const d of DIMS){const key=d[2];if(!R.dims[key])continue;
  col({k:"d_"+key,g:"scores",label:d[1],tip:DIM_TIP[d[0]],v:j=>R.dims[key][j],f:v=>fx(v,2),num:true,color:`var(--dim-${d[0]})`,bar01:true})}
const GROUPS=[["khg","KHG"],["scores","Scores"]];
for(const [dim,spec] of Object.entries(M.dims)){const lab=(DIMS.find(d=>d[2]===dim)||[0,dim])[1];GROUPS.push([dim,lab]);
  for(const k of Object.keys(spec)){if(!R.ind[k])continue;const m=indMeta(k);
    col({k,g:dim,label:m[0],tip:`${m[1]}<br><span>${t("Weight {w}",{w:fmt(spec[k],1)})}${M.dirs[k]==="-"?" · "+t("Lower values raise the score."):""}</span>${fieldSrc(k)[0]?"<br><span>"+t("Source")+": "+t(fieldSrc(k)[0])+"</span>":""}`,v:j=>R.ind[k][j],f:m[2],num:true,color:`var(--dim-${DIMKEY[dim]})`})}}
GROUPS.push(["reported","Reported, not scored"]);
for(const k of [...M.reported,...M.extra]){if(!R.ind[k]||COLS.some(c=>c.k===k))continue;const m=indMeta(k);col({k,g:"reported",label:m[0],tip:m[1]+(fieldSrc(k)[0]?"<br><span>"+t("Source")+": "+t(fieldSrc(k)[0])+"</span>":""),v:j=>R.ind[k][j],f:m[2],num:true})}
GROUPS.push(["trend","Trends"]);
col({k:"sp_burn",g:"trend",label:"Burned peat, 2015 to 2026",tip:"Share of the KHG's peat burned each year (KLHK burnt area). 2026 to date. Sorts by the 2015 to 2025 mean.",
  v:j=>{const s=R.burned[j].slice(0,-1).filter(x=>x!=null);return s.length?d3.mean(s):null},spark:j=>R.burned[j],sc:"--hist",num:true,f:v=>fx(v,2)+"%"});
col({k:"sp_hs",g:"trend",label:"Hotspots, 2012 to 2026",tip:"VIIRS hotspots on peat per year. 2026 to date. Sorts by the total.",v:j=>{const s=R.hs[j].filter(x=>x!=null);return s.length?d3.sum(s):null},spark:j=>R.hs[j],sc:"--hist",num:true,f:v=>fmt(v,0)});
col({k:"sp_now",g:"trend",label:"Hotspots 2026 by month",tip:"MODIS hotspots on peat this year by month, medium and high confidence. Sorts by the total.",v:j=>{const s=R.now_m[j].filter(x=>x!=null);return s.length?d3.sum(s):null},spark:j=>R.now_m[j],sc:"--now",num:true,f:v=>fmt(v,0)});
GROUPS.unshift(["",""]);

// ---------------------------------------------------------------- state
const S={q:"",scope:"337",isl:"",type:new Set(),iv:new Set(),flag:"",rng:{},sk:"ru337",sd:1,page:0,ps:50,groups:new Set(["khg","scores","urgency","trend"])};
const ISL=[...new Set(R.isl)].filter(Boolean).sort();
const ext={};for(const c of COLS)if(c.num){const v=[];for(let j=0;j<N;j++){const x=c.v(j);if(x!=null&&isFinite(x))v.push(x)}v.sort((a,b)=>a-b);
  c.lo=v.length?v[0]:0;c.hi=v.length?(c.bar01?1:d3.quantile(v,.95)||v[v.length-1]):1;c.all=v;c.min=v[0];c.max=v[v.length-1]}
function rowsFiltered(except){const q=S.q.trim().toLowerCase();const out=[];
  for(let j=0;j<N;j++){
    if(S.scope==="337"&&!R.k337[j])continue;if(S.scope==="team"&&!R.team[j])continue;if(S.scope==="362"&&!R.k362[j])continue;if(S.scope==="scored"&&!R.type[j])continue;
    if(S.isl&&R.isl[j]!==S.isl)continue;if(S.type.size&&!S.type.has(R.type[j]))continue;if(S.iv.size&&!S.iv.has(R.iv[j]))continue;
    if(S.flag==="lowf"&&!R.lowf[j])continue;if(S.flag==="hix"&&!R.hix[j])continue;if(S.flag==="wk"&&!R.wk[j])continue;
    if(q&&!(R.name[j].toLowerCase().includes(q)||R.id[j].toLowerCase().includes(q)||R.prov[j].toLowerCase().includes(q)||(R.tim[j]||"").toLowerCase().includes(q)))continue;
    let ok=true;for(const [k,[a,b]] of Object.entries(S.rng)){if(k===except)continue;const c=COLS.find(c=>c.k===k);const v=c.v(j);if(v==null||v<a||v>b){ok=false;break}}
    if(ok)out.push(j)}
  return out}
const visCols=()=>COLS.filter(c=>S.groups.has(c.g));

// ---------------------------------------------------------------- controls
function segH(opts,cur,attr){return `<span class="seg">${opts.map(([v,l,tp])=>`<button type="button" data-${attr}="${v}" class="${cur(v)?"on":""}"${tipAttr(tp?t(tp):"")}>${esc(t(l))}</button>`).join("")}</span>`}
function buildBar(){
  const h=[];
  h.push(`<label class="ctl"><span>${esc(t("Search"))}</span><input type="search" id="q" value="${esc(S.q)}" placeholder="${esc(t("KHG name, code, province or Tim"))}"></label>`);
  h.push(`<div class="ctl"><span>${esc(t("Show"))}</span>${segH([["337","KLH 337","KLH's 337 priority KHG."],["team","Team KHG","KHG chosen by the project team (main and reserve)."],["362","PPEG 362","The 362 priority KHG of KLH's PPEG analysis."],["scored","All scored","Every KHG with a type."],["all","All 865","Every KHG."]],v=>S.scope===v,"scope")}</div>`);
  h.push(`<div class="ctl"><span>${esc(t("Island"))}</span>${segH([["","All"],...ISL.map(i=>[i,i.replace(/^Pulau /,"")])],v=>S.isl===v,"isl")}</div>`);
  h.push(`<div class="ctl"><span>${esc(t("Type"))}</span><span class="seg">${TYPE_ORDER.map(ty=>`<button type="button" data-ty="${ty}" class="${S.type.has(ty)?"on":""}"${tipAttr(`<b>${ty} ${esc(t(TYPE_LABEL[ty]))}</b><br>${esc(t(TYPE_RULE[ty]))}`)}>${ty}</button>`).join("")}</span></div>`);
  h.push(`<div class="ctl"><span>${esc(t("Intervention"))}</span><span class="seg">${IV_ORDER.map(v=>`<button type="button" data-iv="${v}" class="${S.iv.has(v)?"on":""}">${esc(t(IV_SHORT[v]))}</button>`).join("")}</span></div>`);
  h.push(`<div class="ctl"><span>${esc(t("Flag"))}</span>${segH([["","All"],["lowf","Low feasibility"],["hix","High exposure"],["wk","Whole KHG","No peat in KLH's peat map: scored with the whole KHG as peat."]],v=>S.flag===v,"flag")}</div>`);
  h.push(`<div class="ctl"><span>${esc(t("Columns"))}</span><div class="groups">${GROUPS.filter(g=>g[0]).map(([g,l])=>`<button type="button" class="gchip${S.groups.has(g)?" on":""}" data-g="${g}">${esc(t(l))}</button>`).join("")}</div></div>`);
  h.push(`<div class="ctl"><span>&nbsp;</span><button type="button" id="reset" class="ghost">${esc(t("Reset"))}</button></div>`);
  $("#tbar").innerHTML=h.join("");
  $("#q").oninput=e=>{S.q=e.target.value;S.page=0;render(false)};
  $$("#tbar [data-scope]").forEach(b=>b.onclick=()=>{S.scope=b.dataset.scope;S.page=0;update()});
  $$("#tbar [data-isl]").forEach(b=>b.onclick=()=>{S.isl=b.dataset.isl;S.page=0;update()});
  $$("#tbar [data-ty]").forEach(b=>b.onclick=()=>{const v=b.dataset.ty;S.type.has(v)?S.type.delete(v):S.type.add(v);S.page=0;update()});
  $$("#tbar [data-iv]").forEach(b=>b.onclick=()=>{const v=b.dataset.iv;S.iv.has(v)?S.iv.delete(v):S.iv.add(v);S.page=0;update()});
  $$("#tbar [data-flag]").forEach(b=>b.onclick=()=>{S.flag=b.dataset.flag;S.page=0;update()});
  $$("#tbar [data-g]").forEach(b=>b.onclick=()=>{const g=b.dataset.g;S.groups.has(g)?S.groups.delete(g):S.groups.add(g);if(!S.groups.size)S.groups.add("khg");update()});
  $("#reset").onclick=()=>{Object.assign(S,{q:"",scope:"337",isl:"",type:new Set(),iv:new Set(),flag:"",rng:{},sk:"ru337",sd:1,page:0});update()};
}
function rangeChips(){
  $("#rchips").innerHTML=Object.entries(S.rng).map(([k,[a,b]])=>{const c=COLS.find(c=>c.k===k);return `<span class="rchip">${esc(t(c.label))}: ${esc(c.f?c.f(a):fmt(a))} – ${esc(c.f?c.f(b):fmt(b))}<button type="button" data-k="${k}" aria-label="${esc(t("Remove"))}">×</button></span>`}).join("");
  $$("#rchips button").forEach(b=>b.onclick=()=>{delete S.rng[b.dataset.k];S.page=0;update()});
  $("#rchips").style.marginTop=Object.keys(S.rng).length?"10px":"0"}

// ---------------------------------------------------------------- summary
function spark(vals,colorVar,w=96,h=22,area=true){
  const v=vals.map(x=>x==null?null:+x);const n=v.length;if(!n||v.every(x=>x==null))return `<svg class="spark" viewBox="0 0 ${w} ${h}"></svg>`;
  const mx=Math.max(1e-9,...v.filter(x=>x!=null));const X=i=>1+i*(w-2)/Math.max(1,n-1),Y=x=>h-2-(x/mx)*(h-4);
  let d="",a="";v.forEach((x,i)=>{if(x==null)return;d+=(d?"L":"M")+X(i).toFixed(1)+","+Y(x).toFixed(1)});
  const pts=v.map((x,i)=>x==null?null:[X(i),Y(x)]).filter(Boolean);if(area&&pts.length>1)a=`<path d="M${pts[0][0]},${h-1}L${pts.map(p=>p.join(",")).join("L")}L${pts[pts.length-1][0]},${h-1}Z" fill="${css(colorVar)}" opacity=".15"/>`;
  const last=pts[pts.length-1];return `<svg class="spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">${a}<path d="${d}" fill="none" stroke="${css(colorVar)}" stroke-width="1.3"/><circle cx="${last[0]}" cy="${last[1]}" r="1.8" fill="${css(colorVar)}"/></svg>`}
function summary(idx){
  const sum=(arr)=>d3.sum(idx,j=>arr[j]||0);
  const byY=(key,ny)=>d3.range(ny).map(i=>d3.sum(idx,j=>(R[key][j][i]||0)*((key==="burned")?(R.ind.peat_km2[j]||0):1)));
  const burnKm=byY("burned",DATA.years.burned.length).map(x=>x/100);
  const hs=byY("hs",DATA.years.hs.length),nowm=d3.range(12).map(i=>d3.sum(idx,j=>R.now_m[j][i]||0));
  const k=[[fmt(idx.length,0),t("KHG shown"),""],
    [fmt(sum(R.ind.peat_km2),0),t("km2 of peat"),""],
    [fmt(d3.sum(idx,j=>R.ind.pop_on_peat?R.ind.pop_on_peat[j]||0:0),0),t("people on the peat"),""],
    [fmt(d3.sum(burnKm.slice(0,-1)),0),t("km2 of peat burned, 2015 to 2025"),spark(burnKm,"--hist",200,26)],
    [fmt(d3.sum(hs),0),t("VIIRS hotspots on peat, 2012 to 2026"),spark(hs,"--hist",200,26)],
    [fmt(d3.sum(nowm),0),t("hotspots this year (MODIS)"),spark(nowm.slice(0,Math.max(1,nowm.findLastIndex(x=>x>0)+1)),"--now",200,26)]];
  $("#sum").innerHTML=k.map(([v,l,s])=>`<div class="kpi"><div class="v">${v}</div><div class="l">${esc(l)}</div>${s}</div>`).join("")}

// ---------------------------------------------------------------- table
function histSvg(c,idxAll,idxOther){
  const W=110,H=26,B=18,lo=c.min,hi=c.bar01?1:(c.max>c.hi*3?c.hi:c.max);if(lo==null||hi==null||hi<=lo)return "";
  const bin=x=>Math.max(0,Math.min(B-1,Math.floor((Math.min(x,hi)-lo)/(hi-lo)*B)));
  const a=new Array(B).fill(0),b=new Array(B).fill(0);
  for(const x of c.all)a[bin(x)]++;for(const j of idxOther){const x=c.v(j);if(x!=null&&isFinite(x))b[bin(x)]++}
  const mx=Math.max(1,...a),bw=W/B;
  const r=S.rng[c.k];
  return `<svg class="hist" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" data-k="${c.k}" data-lo="${lo}" data-hi="${hi}">`+
    a.map((n,i)=>`<rect x="${i*bw+.5}" width="${bw-1}" y="${H-1-(H-2)*Math.sqrt(n/mx)}" height="${(H-2)*Math.sqrt(n/mx)}" fill="${css("--grid")}"/>`).join("")+
    b.map((n,i)=>n?`<rect x="${i*bw+.5}" width="${bw-1}" y="${H-1-(H-2)*Math.sqrt(n/mx)}" height="${(H-2)*Math.sqrt(n/mx)}" fill="${c.color&&c.color.startsWith("var")?css(c.color.slice(4,-1)):css("--hist")}" opacity=".8"/>`:"").join("")+
    (r?`<rect x="${(Math.max(r[0],lo)-lo)/(hi-lo)*W}" width="${Math.max(1,(Math.min(r[1],hi)-Math.max(r[0],lo))/(hi-lo)*W)}" y="0" height="${H}" fill="${css("--ink")}" opacity=".08"/>`:"")+`</svg>`}
function cell(c,j){
  if(c.spark){const v=c.v(j);return `<td${tipAttr(`${esc(R.name[j])}<br>${esc(t(c.label))}: ${esc(c.f(v))}`)}>${spark(c.spark(j),c.sc)}</td>`}
  if(c.html)return `<td class="l">${c.html(j)}</td>`;
  const v=c.v(j);
  if(c.txt)return `<td class="l">${c.f?c.f(v):esc(v??"")}</td>`;
  if(v==null||!isFinite(v))return `<td class="na">${esc(t("n/a"))}</td>`;
  const w=c.hi>c.lo?Math.max(0,Math.min(1,(v-Math.min(0,c.lo))/(c.hi-Math.min(0,c.lo)))):0;
  return `<td>${esc(c.f?c.f(v):fmt(v))}${c.k==="conf"||c.k==="ru"||c.k==="ru337"?"":`<span class="cb"><i style="width:${(w*100).toFixed(1)}%;--c:${c.color||"var(--hist)"}"></i></span>`}</td>`}
let IDX=[];
function render(full=true){
  const idx=rowsFiltered();IDX=idx;
  const c0=COLS.find(c=>c.k===S.sk)||COLS[0];
  const key=j=>{const v=c0.v(j);return v==null||(typeof v==="number"&&!isFinite(v))?null:v};
  idx.sort((a,b)=>{const x=key(a),y=key(b);if(x==null&&y==null)return a-b;if(x==null)return 1;if(y==null)return -1;return (x<y?-1:x>y?1:0)*S.sd||a-b});
  const ps=S.ps==="all"?idx.length||1:S.ps,np=Math.max(1,Math.ceil(idx.length/ps));S.page=Math.min(S.page,np-1);
  const pageIdx=idx.slice(S.page*ps,S.page*ps+ps);
  const cols=visCols();
  const grp=[];for(const c of cols){if(grp.length&&grp[grp.length-1][0]===c.g)grp[grp.length-1][1]++;else grp.push([c.g,1])}
  const gl=g=>esc(t((GROUPS.find(x=>x[0]===g)||[0,g])[1]));
  const firstOf=new Set();{let prev=null;for(const c of cols){if(c.g!==prev)firstOf.add(c.k);prev=c.g}}
  const head=`<thead><tr class="g"><th class="sticky"></th>${grp.map(([g,n])=>`<th colspan="${n}">${gl(g)}</th>`).join("")}</tr><tr class="h"><th class="sticky"><span class="lb${S.sk==="name"?" on":""}" data-k="name">${esc(t("KHG"))}${S.sk==="name"?(S.sd>0?" ▴":" ▾"):""}</span><small class="hint">${esc(t("● high ◐ medium ○ low data confidence · ◆ team KHG"))}</small></th>`+
    cols.map(c=>{const others=c.num?rowsFiltered(c.k):[];return `<th class="${firstOf.has(c.k)?"gstart":""}"><span class="lb${S.sk===c.k?" on":""}" data-k="${c.k}"${tipAttr(`<b>${esc(t(c.label))}</b>${c.tip?"<br>"+t(c.tip):""}<br><span>${esc(t(c.num?"Click to sort. Drag on the histogram to filter a range.":"Click to sort."))}</span>`)}>${esc(t(c.label))}${S.sk===c.k?(S.sd>0?" ▴":" ▾"):""}</span>${c.num&&!c.spark&&c.k!=="ru"&&c.k!=="ru337"&&c.k!=="conf"?histSvg(c,idx,others):""}</th>`}).join("")+`</tr></thead>`;
  const body=`<tbody>${pageIdx.map(j=>`<tr data-id="${R.id[j]}"><td class="sticky l"${tipAttr(t("Open the profile of this KHG in the KHG priority page."))}>${R.conf[j]!=null?`<span style="color:var(--muted)">${confChar[R.conf[j]]}</span> `:""}${esc(R.name[j])}${R.team[j]?` <span${tipAttr(t("Team KHG")+": "+esc(R.team[j]))}>◆</span>`:""}<small>${esc(R.id[j])} · ${esc(R.prov[j])}${R.k337[j]?"":" · "+esc(t("not in the 337"))}${R.wk[j]?" · "+esc(t("whole KHG used")):""}</small></td>${cols.map(c=>cell(c,j)).join("")}</tr>`).join("")}</tbody>`;
  $("#twrap").innerHTML=`<table class="kt">${head}${body}</table>`;
  $$("#twrap .lb").forEach(h=>h.onclick=()=>{const k=h.dataset.k;const c=COLS.find(c=>c.k===k);S.sd=S.sk===k?-S.sd:(c&&c.num&&!c.asc?-1:1);S.sk=k;render()});
  $$("#twrap tbody tr").forEach(tr=>tr.onclick=e=>{if(e.target.closest("[data-tip]")&&e.target.closest(".tyb,.ivb"))return;location.href=`dashboard.html#l=${LANG}${document.documentElement.dataset.theme?"&t="+document.documentElement.dataset.theme:""}&k=${tr.dataset.id}`});
  $$("#twrap svg.hist").forEach(svgEl=>{const k=svgEl.dataset.k,lo=+svgEl.dataset.lo,hi=+svgEl.dataset.hi;
    const s=d3.select(svgEl),W=110,H=26,x=d3.scaleLinear([0,W],[lo,hi]);
    const br=d3.brushX().extent([[0,0],[W,H]]).on("end",ev=>{if(!ev.sourceEvent)return;if(!ev.selection){delete S.rng[k]}else{const [a,b]=ev.selection.map(x);S.rng[k]=[a,b>=hi-1e-12?Infinity:b];if(a<=lo+1e-12)S.rng[k][0]=-Infinity}S.page=0;update()});
    s.append("g").attr("class","hbrush").call(br)});
  pager(idx.length,np,ps);
  if(full){summary(idx);rangeChips()}else summary(idx);
  hash()}
function pager(n,np,ps){
  const from=n?S.page*ps+1:0,to=Math.min(n,S.page*ps+ps);
  const pages=[];for(let p=0;p<np;p++)if(p<2||p>np-3||Math.abs(p-S.page)<=2)pages.push(p);else if(pages[pages.length-1]!=="…")pages.push("…");
  const h=`<span class="hint">${esc(t("{a}–{b} of {n} KHG",{a:fmt(from,0),b:fmt(to,0),n:fmt(n,0)}))}</span>
    <span class="seg">${[25,50,100,"all"].map(v=>`<button type="button" data-ps="${v}" class="${S.ps===v?"on":""}">${v==="all"?esc(t("All")):v}</button>`).join("")}</span>
    <span class="seg">${`<button type="button" data-pg="${S.page-1}" ${S.page?"":"disabled"}>‹</button>`+pages.map(p=>p==="…"?`<button type="button" disabled>…</button>`:`<button type="button" data-pg="${p}" class="${p===S.page?"on":""}">${p+1}</button>`).join("")+`<button type="button" data-pg="${S.page+1}" ${S.page<np-1?"":"disabled"}>›</button>`}</span>`;
  for(const id of ["#pager","#pager-top"])$(id).innerHTML=h;
  $$(".pager [data-ps]").forEach(b=>b.onclick=()=>{S.ps=b.dataset.ps==="all"?"all":+b.dataset.ps;S.page=0;render()});
  $$(".pager [data-pg]").forEach(b=>b.onclick=()=>{S.page=+b.dataset.pg;render();$("#twrap").scrollTop=0})}

// ---------------------------------------------------------------- CSV, hash, init
function csv(){
  const cols=COLS.filter(c=>!c.spark);const q=v=>{const s=v==null?"":String(v);return /[",\n]/.test(s)?`"${s.replace(/"/g,'""')}"`:s};
  const head=["khg_code","khg_name","provinces","klh_337","team_khg",...cols.map(c=>c.k.replace(/^d_/,""))];
  const lines=[head.join(",")].concat(IDX.map(j=>[R.id[j],R.name[j],R.prov[j],R.k337[j],R.team[j],...cols.map(c=>c.v(j))].map(q).join(",")));
  const a=document.createElement("a");a.href=URL.createObjectURL(new Blob(["\ufeff"+lines.join("\n")],{type:"text/csv"}));a.download="khg_table.csv";a.click();setTimeout(()=>URL.revokeObjectURL(a.href),2000)}
function hash(){const th=document.documentElement.dataset.theme;
  const h=`#l=${LANG}${th?"&t="+th:""}&s=${S.scope}${S.isl?"&i="+encodeURIComponent(S.isl):""}${S.type.size?"&ty="+[...S.type].join(""):""}${S.flag?"&f="+S.flag:""}&k=${S.sk}&d=${S.sd}&g=${[...S.groups].join(",")}`;
  history.replaceState(null,"",h);navHrefs()}
function readHash(){const h=new URLSearchParams(location.hash.slice(1));readLangTheme(h);
  if(["337","team","362","scored","all"].includes(h.get("s")))S.scope=h.get("s");if(h.get("i"))S.isl=h.get("i");if(h.get("ty"))S.type=new Set(h.get("ty").split("").filter(x=>TYPE_ORDER.includes(x)));
  if(["lowf","hix","wk"].includes(h.get("f")))S.flag=h.get("f");if(h.get("k")&&(h.get("k")==="name"||COLS.some(c=>c.k===h.get("k"))))S.sk=h.get("k");if(h.get("d")==="-1")S.sd=-1;
  if(h.get("g")){const g=h.get("g").split(",").filter(x=>GROUPS.some(y=>y[0]===x));if(g.length)S.groups=new Set(g)}}
COLS.push({k:"name",g:"_",v:j=>R.name[j],txt:true});
function update(){topBar("khg_table.html",update);document.title=t("KHG table");
  $("#sub").textContent=t("Every KHG with every field of the prioritisation: filter, sort, and drag on a column's histogram to keep a range. Click a row to open its profile.");
  $("#foot").textContent=t("Scores and types from the prioritisation run of {r}; fire data to {d}. Histograms: grey is every KHG, colour is the KHG that pass the other filters. Sparklines share no scale: each shows the shape of one KHG's series.",{r:M.run||"",d:(M.period_now||"").toString()});
  $("#csv-btn").onclick=csv;buildBar();render()}
readHash();update();
document.body.dataset.ready="1";
