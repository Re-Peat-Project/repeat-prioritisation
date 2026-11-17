// ---------------------------------------------------------------- KHG priority (repeat-national-final), live weights, and data export
// Inserted into dashboard.js before init(); uses its helpers (t, fmt, fx, esc, $, $$, select, state, K, chip, tipAttr, css).
const FIN=DATA.final||null;
/*DEFS*/
const ivTip=v=>{const M=FIN.meta.intervention;if(!M||!v)return "";const a=Math.round(M.rewetting.min*100),b=Math.round(M.revegetation.min*100);
  return `<b>${esc(t(IV_SHORT[v]))}</b><br>${esc(t(IV_NOTE[v],{a,b}))}<br><span>${esc(t("Intervention the peat needs, from two shares of the KHG's peat: canal-affected (KLH canal-influence zones, PPEG) and open or degraded cover (KLH land cover 2022: shrub, open land, open swamp, savanna). Thresholds written before the result. Independent of the type, which says how urgent and how complex."))}</span>`};
const ivBadge=v=>v?`<span class="ivb" style="--c:${IV_COL[v]}"${tipAttr(ivTip(v))}>${esc(t(IV_SHORT[v]))}</span>`:"";
const DIRS=()=>FIN.meta.dirs||{};
const indTip=k=>{const m=IND[k]||[k,"",x=>fx(x,2)];const dir=DIRS()[k]==="-"?t("Lower values raise the score."):"";return `<b>${esc(t(m[0]))}</b><br>${esc(t(m[1]))}${dir?"<br><span>"+esc(dir)+"</span>":""}`};
const typeVar=ty=>`var(--ty${ty})`;
const finIdx=id=>FIN?FIN.idx[id]:undefined;
const fin={q:"",type:"",iv:"",only337:true,isl:new Set(),flag:"",k:"ru",dir:1,colour:"type",w:null,missing:"skip",conf:"mh"};
const FK=FIN?FIN.f.id.map(id=>K.id.indexOf(id)):[];          // final-table row -> KHG index of the page
const indVals=k=>{                                             // indicator values; this year's hotspots follow the confidence switch
  if(k==="u_hotspot_now"&&fin.conf==="h"&&K.n1h)return FK.map(i=>i>=0?K.n1h[i]:null);
  return FIN.f.ind[k]};

// ---------------------------------------------------------------- live scoring: the same rule as repeat-national-final
const finDims=()=>DIMS.filter(d=>FIN.meta.dims[d[2]]);
function refW(){const w={};for(const [,,dn] of finDims())for(const k in FIN.meta.dims[dn])w[k]=FIN.meta.dims[dn][k];return w}
function qs(sorted,p){return sorted.length?d3.quantileSorted(sorted,p):NaN}
function finCompute(w){
  const F=FIN.f,n=F.id.length,out={};
  for(const [key,,dn] of finDims()){
    const num=new Float64Array(n),den=new Float64Array(n);
    for(const k in FIN.meta.dims[dn]){const wk=w[k];if(!(wk>0)||!F.ind[k])continue;
      const sg=DIRS()[k]==="-"?-1:1,x=indVals(k);
      const ref=[];for(let j=0;j<n;j++)if(F.pool[j]&&x[j]!=null)ref.push(sg*x[j]);ref.sort(d3.ascending);if(!ref.length)continue;
      for(let j=0;j<n;j++){if(x[j]==null){if(fin.missing==="median"){num[j]+=wk*.5;den[j]+=wk}continue}const v=sg*x[j];const lo=d3.bisectLeft(ref,v),hi=d3.bisectRight(ref,v);num[j]+=wk*(lo+hi)/2/ref.length;den[j]+=wk}}
    out[key]=Array.from({length:n},(_,j)=>F.scored[j]&&den[j]>0?num[j]/den[j]:null)}
  const poolS=key=>{const a=[];for(let j=0;j<n;j++)if(F.pool[j]&&out[key][j]!=null)a.push(out[key][j]);return a.sort(d3.ascending)};
  const cuts={};for(const k of ["u","c","s"]){const a=poolS(k);cuts[k]=[qs(a,1/3),qs(a,2/3)]}
  const fcut=out.f?qs(poolS("f"),1/3):null,pcut=out.p?qs(poolS("p"),2/3):null;
  const type=new Array(n).fill(null);
  for(let j=0;j<n;j++){const u=out.u[j],c=out.c[j],s=out.s[j];if(!F.scored[j]||u==null)continue;
    if(u>=cuts.u[1])type[j]=c==null||c<cuts.c[1]?"A":"B";else if(u>=cuts.u[0])type[j]="C";else type[j]=s!=null&&s>=cuts.s[1]?"D":"E"}
  const rankBy=keep=>{const idx=[];for(let j=0;j<n;j++)if(out.u[j]!=null&&keep(j))idx.push(j);const r=new Array(n).fill(null);
    const srt=idx.map(j=>out.u[j]).sort((a,b)=>b-a);for(const j of idx){let lo=0,hi=srt.length;while(lo<hi){const m=(lo+hi)>>1;if(srt[m]>out.u[j])lo=m+1;else hi=m}r[j]=lo+1}return r};
  const ru=rankBy(()=>true),ru337=rankBy(j=>F.k337[j]);
  const rt=new Array(n).fill(null);
  for(const ty of TYPE_ORDER){const idx=[];for(let j=0;j<n;j++)if(type[j]===ty)idx.push(j);const key=j=>out.u[j]+1e-6*(out.s[j]??0);
    idx.sort((a,b)=>key(b)-key(a));let prev=null,pr=0;idx.forEach((j,k)=>{const v=key(j);if(v!==prev){pr=k+1;prev=v}rt[j]=pr})}
  const lowf=out.f?out.f.map((v,j)=>F.scored[j]&&v!=null&&v<fcut?1:0):F.lowf;
  const hix=out.p?out.p.map((v,j)=>F.scored[j]&&v!=null&&v>=pcut?1:0):new Array(n).fill(0);
  return {...out,type,cuts,fcut,pcut,ru,ru337,rt,lowf,hix};
}
let FC=null,FC0=null;
window.REPEAT_FIN={compute:w=>finCompute(w),refW:()=>refW()};   // for checks from the browser console
function finRecompute(){FC=finCompute(fin.w);if(!FC0)FC0=finCompute(refW())}
const atRef=()=>{const r=refW();return fin.conf==="mh"&&fin.missing==="skip"&&Object.keys(r).every(k=>Math.abs((fin.w[k]??0)-r[k])<1e-9)};

// ---------------------------------------------------------------- bars and tooltips
const dimOf=key=>DIMS.find(d=>d[0]===key);
function tercile(v,key){if(v==null||!FC)return "";if(key==="f")return v<FC.fcut?t("low (flagged)"):"";if(key==="p")return v>=FC.pcut?t("high (flagged)"):"";
  const c=FC.cuts[key];return v>=c[1]?t("high"):v>=c[0]?t("medium"):t("low")}
function dimTip(key,j){
  const d=dimOf(key),dn=d[2],w=fin.w||refW(),ks=Object.keys(FIN.meta.dims[dn]);
  if(j===undefined)return `<b>${esc(t(d[1]))}</b><br>${esc(t(DIM_TIP[key]))}<br>`+ks.map(k=>`· ${esc(t((IND[k]||[k])[0]))}${w[k]!==1?` <span>(${t("weight")} ${fmt(w[k],1)})</span>`:""}`).join("<br>")+`<br><span>${esc(t(SCORE_NOTE,{m:FIN.meta.min_peat}))}</span>`;
  const F=FIN.f,v=FC[key][j];
  let h=`<b>${esc(F.name[j])}: ${esc(t(d[1]))} ${v==null?t("n/a"):fx(v,2)}</b>${v!=null&&tercile(v,key)?" ("+esc(tercile(v,key))+")":""}<br>`;
  h+=ks.map(k=>{const iv=F.ind[k]?F.ind[k][j]:null;const m=IND[k]||[k,"",x=>fx(x,2)];return `${esc(t(m[0]))}: <b>${iv==null?t("n/a"):m[2](iv)}</b>${w[k]!==1?` <span>(${t("weight")} ${fmt(w[k],1)})</span>`:""}`}).join("<br>");
  return h+`<br><span>${esc(t(DIM_TIP[key]))}</span>`;
}
function finBar(v,key,j){
  const tip=tipAttr(dimTip(key,j));
  if(v==null)return `<span class="fbar na"${tip}>${t("n/a")}</span>`;
  const c=key==="f"?[FC.fcut]:key==="p"?[FC.pcut]:FC.cuts[key],m=c.filter(x=>x!=null).map(x=>`<i style="left:${(x*100).toFixed(1)}%"></i>`).join("");
  return `<span class="fbar"${tip}><b style="width:${(v*100).toFixed(1)}%"></b>${m}</span><span class="fnum"${tip}>${fx(v,2)}</span>`;
}
const typeTip=ty=>`<b>${ty} · ${esc(t(TYPE_LABEL[ty]))}</b><br>${esc(t(TYPE_NOTE[ty]))}<br><span>${esc(t("Rule: {r}. Feasibility and people do not change the type.",{r:t(TYPE_RULE[ty])}))}</span>`;

// ---------------------------------------------------------------- weights panel and presets
function finPresets(){const r=refW(),ks=Object.keys(r);return {"Pre-registered rule":r,"Equal weights":Object.fromEntries(ks.map(k=>[k,1])),
  "Fire history only":Object.fromEntries(ks.map(k=>[k,FIN.meta.dims.urgency[k]!==undefined?(k==="u_fire_freq"?1:0):r[k]]))}}
function markFinPresets(){const P=finPresets();$$("#final-presets button").forEach(b=>{const w=P[b.dataset.p];b.classList.toggle("on",Object.keys(w).every(k=>Math.abs(w[k]-fin.w[k])<1e-9))})}
function buildFinalWeights(){
  const host=$("#final-w");if(!host)return;
  const r=refW();
  host.innerHTML=`<h2 class="hasTip"${tipAttr(t("Each dimension is the weighted mean of its indicators. Move a slider and the scores, types, list and map update. The types come from terciles within each dimension, so only the weights inside a dimension matter. The pre-registered weights are the reference; changes are shown against them."))}>${t("Weights")}</h2>`+
    finDims().map(([key,lab,dn])=>`<div class="fw-g"><div class="gs hasTip"${tipAttr(dimTip(key))}><span class="sw" style="background:var(--dim-${key})"></span>${t(lab)}</div>`+
      Object.keys(FIN.meta.dims[dn]).map(k=>`<div class="sl"><label for="fw-${k}" class="hasTip"${tipAttr(indTip(k)+`<br><span>${t("Pre-registered weight {w}.",{w:fmt(r[k],1)})}</span>`)}>${esc(t((IND[k]||[k])[0]))}</label><input type="range" id="fw-${k}" data-k="${k}" min="0" max="4" step="0.5" value="${fin.w[k]}"><output id="fwo-${k}">${fmt(fin.w[k],1)}</output></div>`).join("")+`</div>`).join("")+
    `<button type="button" id="fw-reset" class="ghost wide"${tipAttr(t("Back to the pre-registered weights."))}>${t("Reset weights")}</button>`+
    (FIN.meta.reported.length?`<p class="hint fw-rep"${tipAttr(FIN.meta.reported.map(indTip).join("<br><br>"))}>${t("Reported, not scored: {x}",{x:FIN.meta.reported.map(k=>t((IND[k]||[k])[0])).join(", ")})}</p>`:"");
  $$("#final-w input[type=range]").forEach(el=>el.oninput=()=>{fin.w[el.dataset.k]=+el.value;$("#fwo-"+el.dataset.k).textContent=fmt(+el.value,1);finSchedule()});
  $("#fw-reset").onclick=()=>{fin.w=refW();buildFinalWeights();finSchedule()};
  const pr=$("#final-presets");pr.innerHTML="";
  const ptip={"Pre-registered rule":"The weights written down on {d}, before any result: the reference for every comparison.","Equal weights":"Every indicator weight 1.","Fire history only":"Urgency from the burned share of peat per year alone, as a check: the other dimensions keep their weights."};
  for(const [nm,w] of Object.entries(finPresets())){const b=document.createElement("button");b.type="button";b.textContent=t(nm);b.dataset.p=nm;b.dataset.tip=t(ptip[nm],{d:FIN.meta.written});
    b.onclick=()=>{fin.w={...w};buildFinalWeights();finSchedule()};pr.appendChild(b)}
  markFinPresets();
}
let finPending=false;
function finSchedule(){if(finPending)return;finPending=true;requestAnimationFrame(()=>{finPending=false;finRecompute();buildFinal(true);renderMap();if(state.sel)renderProfile();history.replaceState(null,"",hashState())})}

// ---------------------------------------------------------------- the card: matrix, types, validation, list
function buildFinal(soft){
  const host=$("#final");if(!host)return;
  if(!FIN){host.hidden=true;return}
  if(!fin.w)fin.w=refW();
  if(!FC)finRecompute();
  const M_=FIN.meta,V=M_.validation,S=M_.sensitivity,F=FIN.f,n=F.id.length;
  $("#final-sub").textContent=t("One list of the KHG (peat hydrological units). Five dimensions per KHG, each from its indicators; the type of action from urgency, complexity and stake. Rule v{v} written {d}. Hover any label for what it means.",{v:M_.version,d:M_.written});
  if(!soft)buildFinalWeights();else markFinPresets();
  const vis=j=>FC.type[j]&&(!fin.only337||F.k337[j])&&(!fin.isl.size||fin.isl.has(F.isl[j]));
  // matrix: rows = urgency tercile (high on top), columns = complexity tercile
  const cnt={};
  for(let j=0;j<n;j++){if(!vis(j))continue;const u=FC.u[j],c=FC.c[j];
    const ur=u>=FC.cuts.u[1]?2:u>=FC.cuts.u[0]?1:0,cr=c==null?1:c>=FC.cuts.c[1]?2:c>=FC.cuts.c[0]?1:0;
    const key=ur+"-"+cr;(cnt[key]=cnt[key]||{})[FC.type[j]]=(cnt[key][FC.type[j]]||0)+1}
  const lv=[t("low"),t("medium"),t("high")];
  const lvTip=d=>tipAttr(`${dimTip(d)}<br><span>${t("Terciles of the KHG with at least {m} km2 of peat: low below {a}, high from {b}.",{m:M_.min_peat,a:fx(FC.cuts[d][0],2),b:fx(FC.cuts[d][1],2)})}</span>`);
  let g=`<div class="fmx"><div class="fmx-y"${lvTip("u")}>${t("Urgency")} ↑</div><div class="fmx-grid">`;
  for(const ur of [2,1,0]){g+=`<div class="fmx-rl"${lvTip("u")}>${lv[ur]}</div>`;
    for(const cr of [0,1,2]){const c=cnt[ur+"-"+cr]||{};const parts=TYPE_ORDER.filter(ty=>c[ty]).map(ty=>`<button type="button" class="fmx-t${fin.type===ty?" on":""}" data-ty="${ty}" style="--c:${typeVar(ty)}"${tipAttr(typeTip(ty)+"<br>"+t("{n} KHG in this cell. Click to filter the list.",{n:c[ty]}))}>${ty}<b>${c[ty]}</b></button>`).join("");
      g+=`<div class="fmx-c">${parts||"<span class='fmx-0'>0</span>"}</div>`}}
  g+=`<div></div>${[0,1,2].map(cr=>`<div class="fmx-cl"${lvTip("c")}>${lv[cr]}</div>`).join("")}</div><div class="fmx-x"${lvTip("c")}>${t("Complexity")} →</div></div>`;
  if($("#final-matrix"))$("#final-matrix").innerHTML=g;
  // type summary, live
  const agg={};for(const ty of TYPE_ORDER)agg[ty]={n:0,peat:0,lowf:0,hix:0,moved:0};
  for(let j=0;j<n;j++){if(!vis(j))continue;const a=agg[FC.type[j]];a.n++;a.peat+=F.peat[j]||0;a.lowf+=FC.lowf[j];a.hix+=FC.hix[j];if(FC0.type[j]!==FC.type[j])a.moved++}
  const mx={n:d3.max(TYPE_ORDER,ty=>agg[ty].n)||1,peat:d3.max(TYPE_ORDER,ty=>agg[ty].peat)||1};
  const chg=!atRef();
  $("#final-types").innerHTML=`<table class="ftypes"><thead><tr><th${tipAttr(t("The five types of action. Click a type to filter the list."))}>${t("Type")}</th><th${tipAttr(t("KHG of the type, after the 337 and island filters."))}>${t("KHG")}</th><th${tipAttr(t("KLH peat (PPEG 2026) of the KHG of the type."))}>${t("Peat")} km2</th><th${tipAttr(dimTip("f"))}>${t("Low feasibility")}</th>${FC.p?`<th${tipAttr(dimTip("p"))}>${t("High exposure")}</th>`:""}${chg?`<th${tipAttr(t("KHG whose type differs from the type at the pre-registered weights."))}>${t("Moved in")}</th>`:""}</tr></thead><tbody>`+
    TYPE_ORDER.map(ty=>{const a=agg[ty];return `<tr class="${fin.type===ty?"on":""}" data-ty="${ty}"${tipAttr(typeTip(ty))}><td><span class="tyb" style="--c:${typeVar(ty)}">${ty}</span> ${esc(t(TYPE_LABEL[ty]))}</td>
      <td><span class="hb" style="width:${(54*a.n/mx.n).toFixed(0)}px;background:${typeVar(ty)}"></span>${fmt(a.n,0)}</td>
      <td><span class="hb" style="width:${(54*a.peat/mx.peat).toFixed(0)}px;background:${typeVar(ty)}"></span>${fmt(a.peat,0)}</td>
      <td class="num">${fmt(a.lowf,0)}</td>${FC.p?`<td class="num">${fmt(a.hix,0)}</td>`:""}${chg?`<td class="num">${fmt(a.moved,0)}</td>`:""}</tr>`}).join("")+`</tbody></table>`;
  if(false&&F.iv){const ct={};for(let j=0;j<n;j++){if(!vis(j)||!F.iv[j])continue;const k=FC.type[j]+"|"+F.iv[j];ct[k]=(ct[k]||0)+1}
    $("#final-types").insertAdjacentHTML("beforeend",`<table class="ftypes fiv"><thead><tr><th${tipAttr(t("KHG by type (rows) and by the intervention their peat needs (columns). Click a number to filter the list."))}>${t("Type × intervention")}</th>${IV_ORDER.map(v=>`<th>${ivBadge(v)}</th>`).join("")}</tr></thead><tbody>`+
      TYPE_ORDER.map(ty=>`<tr><td><span class="tyb" style="--c:${typeVar(ty)}">${ty}</span></td>${IV_ORDER.map(v=>{const c=ct[ty+"|"+v]||0;return `<td class="num"><button type="button" class="ivn${fin.type===ty&&fin.iv===v?" on":""}" data-ty="${ty}" data-iv="${v}"${c?"":" disabled"}>${c||"·"}</button></td>`}).join("")}</tr>`).join("")+`</tbody></table>`);
    $$("#final-types .ivn").forEach(b=>b.onclick=e=>{e.stopPropagation();const on=fin.type===b.dataset.ty&&fin.iv===b.dataset.iv;fin.type=on?"":b.dataset.ty;fin.iv=on?"":b.dataset.iv;buildFinal(true)})}
  $$("#final-types tr[data-ty]").forEach(tr=>tr.onclick=()=>{fin.type=fin.type===tr.dataset.ty?"":tr.dataset.ty;buildFinal(true)});
  $$("#final-matrix .fmx-t").forEach(b=>b.onclick=()=>{fin.type=fin.type===b.dataset.ty?"":b.dataset.ty;buildFinal(true)});
  // validation and stability: removed from the page (kept in the report's data tables)
  const vu=V.urgency,vf=V.fire_history_only;
  if($("#final-kpis"))$("#final-kpis").innerHTML=[
    [`${fx(vu.capture_top20pct*100,0)}<small>%</small>`,t("of 2026 burned peat in the top 20% by urgency (fire history alone: {b}%)",{b:fx(vf.capture_top20pct*100,0)})],
    [fx(vu.auc,2),t("AUC against burned or not in 2026 (fire history alone: {b})",{b:fx(vf.auc,2)})],
    [`${fx(S.share_khg_type_stable_80pct*100,0)}<small>%</small>`,t("of KHG keep their type in 80% of {n} runs with every weight ±50%",{n:S.runs})],
  ].map(([v,l],k)=>`<div class="kpi"${tipAttr(t(["Urgency built without this year's hotspots, from data up to 2025, tested on the peat that burned in 2026: the 20% most urgent KHG hold this share of it.","Area under the ROC curve: the chance that a KHG that burned in 2026 ranks above one that did not (0.5 = chance, 1 = perfect).","Every weight multiplied by a random factor between 0.5 and 1.5, {n} times; KHG keeping their type in at least 80% of the draws. Computed at the pre-registered weights."][k],{n:S.runs}))}><div class="v">${v}</div><div class="l">${esc(l)}</div></div>`).join("");
  // controls
  const sw=$("#final-ctl");sw.innerHTML="";
  const seg=(items,cur,on,tip)=>{const s=document.createElement("span");s.className="seg";if(tip)s.dataset.tip=tip;items.forEach(([v,tx,tp])=>{const b=document.createElement("button");b.type="button";b.textContent=tx;if(tp)b.dataset.tip=tp;b.classList.toggle("on",cur(v));b.onclick=()=>on(v);s.appendChild(b)});sw.appendChild(s)};
  seg([[true,t("KLH 337"),t("KLH's work list of 337 KHG (Tim GIS, September 2026).")],[false,t("All scored KHG"),t("Every KHG with at least {m} km2 of KLH peat, plus the 337 with less.",{m:M_.min_peat})]],v=>fin.only337===v,v=>{fin.only337=v;buildFinal(true);renderMap()});
  seg([...new Set(F.isl)].filter(Boolean).sort().map(x=>[x,x]),v=>fin.isl.has(v),v=>{fin.isl.has(v)?fin.isl.delete(v):fin.isl.add(v);buildFinal(true);renderMap()},t("Island filter: click one or more."));
  seg([["mh",t("Medium + high"),t("This year's hotspots: medium and high confidence.")],["h",t("High only"),t("This year's hotspots: high confidence only.")]],v=>fin.conf===v,v=>{fin.conf=v;finSchedule()},t("Hotspot confidence (this year's hotspots)."));
  seg([["skip",t("Ignore"),t("A KHG without a value (e.g. no canals mapped) is scored on the indicators it has.")],["median",t("Average"),t("A KHG without a value is given the middle (median) rank for it.")]],v=>fin.missing===v,v=>{fin.missing=v;finSchedule()},t("Missing values, e.g. no canals mapped: ignore them or use the average."));
  seg([["",t("All")],["lowf",t("Low feasibility"),dimTip("f")],...(FC.p?[["hix",t("High exposure"),dimTip("p")]]:[]),...(chg?[["moved",t("Type changed"),t("KHG whose type differs from the type at the pre-registered weights.")]]:[])],v=>fin.flag===v,v=>{fin.flag=v;buildFinal(true)});
  const q=document.createElement("input");q.type="search";q.placeholder=t("Search KHG or province");q.value=fin.q;q.className="fq";q.oninput=()=>{fin.q=q.value;renderFinalTable()};sw.appendChild(q);
  if(fin.type||fin.iv){const b=document.createElement("button");b.type="button";b.className="ghost";b.textContent=[fin.type?t("Type {ty}",{ty:fin.type}):"",fin.iv?t(IV_SHORT[fin.iv]):""].filter(Boolean).join(" · ")+" · "+t("clear");b.onclick=()=>{fin.type="";fin.iv="";buildFinal(true)};sw.appendChild(b)}
  renderFinalTable();
}
function finRows(){
  const F=FIN.f,q=fin.q.trim().toLowerCase(),idx=[];
  for(let j=0;j<F.id.length;j++){if(!FC.type[j])continue;if(fin.only337&&!F.k337[j])continue;if(fin.isl.size&&!fin.isl.has(F.isl[j]))continue;if(fin.type&&FC.type[j]!==fin.type)continue;if(fin.iv&&(F.iv||[])[j]!==fin.iv)continue;
    if(fin.flag==="lowf"&&!FC.lowf[j])continue;if(fin.flag==="hix"&&!FC.hix[j])continue;if(fin.flag==="moved"&&FC0.type[j]===FC.type[j])continue;
    if(q&&!(F.name[j].toLowerCase().includes(q)||F.id[j].toLowerCase().includes(q)||(F.prov[j]||"").toLowerCase().includes(q)))continue;idx.push(j)}
  return idx}
function profBar(j){      // one bar per KHG: each dimension's score as a segment of a fifth of the bar (a profile, not a combined score)
  const dd=finDims(),n=dd.length;
  return `<span class="pbar">${dd.map(([key])=>{const v=FC[key][j];return `<b style="width:${v==null?0:(100*v/n).toFixed(2)}%;background:var(--dim-${key})"${tipAttr(dimTip(key,j))}></b>`}).join("")}</span>`}
function renderFinalTable(){
  const F=FIN.f,idx=finRows(),chg=!atRef();
  const rk=j=>fin.only337?FC.ru337[j]:FC.ru[j],rk0=j=>fin.only337?FC0.ru337[j]:FC0.ru[j];
  const key={ru:j=>rk(j)??1e9,ty:j=>TYPE_ORDER.indexOf(FC.type[j])*1000+FC.rt[j],u:j=>-FC.u[j],s:j=>-(FC.s[j]??-1),c:j=>-(FC.c[j]??-1),f:j=>-(FC.f[j]??-1),p:j=>-((FC.p||[])[j]??-1),
    iv:j=>IV_ORDER.indexOf((F.iv||[])[j])*1000+(rk(j)??0),mv:j=>-((rk0(j)??0)-(rk(j)??0)),peat:j=>-F.peat[j],nm:j=>F.name[j]}[fin.k]||(j=>rk(j)??1e9);
  idx.sort((a,b)=>{const x=key(a),y=key(b);return (x<y?-1:x>y?1:0)*fin.dir||a-b});
  const pct=(m)=>Math.round(((FIN.meta.intervention||{})[m]||{min:.2}).min*100);
  const HT={ru:t("Rank by urgency (1 = most urgent), among KLH's 337 or among all scored KHG. Click any header to sort."),
    mv:t("Change in rank against the pre-registered weights: places gained (▲) or lost (▼). A small letter shows the earlier type when it changed. All dots: the weights are as pre-registered."),
    nm:t("KHG: peat hydrological unit, the unit of analysis. Click a row to open its profile below; the small text is the province and any flags.")+"<br>"+t("● high ◐ medium ○ low data confidence · ◆ team KHG"),
    ty:t("Type of action from the terciles of urgency, complexity and stake; the small number is the rank within the type.")+"<br>"+TYPE_ORDER.map(ty=>`${ty} ${esc(t(TYPE_LABEL[ty]))}: ${esc(t(TYPE_RULE[ty]))}`).join("<br>"),
    iv:ivTip("rewetting and revegetation")+"<br>"+IV_ORDER.map(v=>`${esc(t(IV_SHORT[v]))}: ${esc(t(IV_NOTE[v],{a:pct("rewetting"),b:pct("revegetation")}))}`).join("<br>"),
    peat:t("KLH peat inside the KHG (PPEG 2026), km2.")};
  const sel=state.sel;
  const flags=j=>[(F.wk||[])[j]?t("no KLH peat: whole KHG used"):"",F.small[j]?t("small peat area"):"",FC.lowf[j]?t("low feasibility"):"",FC.hix[j]?t("high exposure"):""].filter(Boolean);
  const flagTip=j=>tipAttr([(F.wk||[])[j]?t("KLH's peat map shows no peat in this KHG, although it is a peat hydrological unit and the Global Peatland Map shows peat. It is scored with the whole KHG as the peat extent, against the larger KHG, and is less reliable."):"",F.small[j]?t("Small peat area: less than {m} km2 of KLH peat, scored against the larger KHG and less reliable.",{m:FIN.meta.min_peat}):"",FC.lowf[j]?t("Low feasibility: lowest third of the KHG on feasibility. The type is kept; plan for harder rewetting."):"",FC.hix[j]?t("High exposure: highest third on people. The type is kept; more people are affected by fire and haze."):""].filter(Boolean).join("<br>")||t("Click to open the profile."));
  const th=(k,l,cls="")=>`<th data-k="${k}" class="${cls}${fin.k===k?" on":""}"${tipAttr(HT[k]||"")}>${esc(t(l))}${fin.k===k?(fin.dir>0?" ▾":" ▴"):""}</th>`;
  const profHead=`<th class="phead">${finDims().map(([key,lab])=>`<span class="pchip${fin.k===key?" on":""}" data-k="${key}"${tipAttr(dimTip(key)+"<br><span>"+t("Click to sort by this dimension.")+"</span>")}><i style="background:var(--dim-${key})"></i>${esc(t(lab))}${fin.k===key?(fin.dir>0?" ▾":" ▴"):""}</span>`).join("")}</th>`;
  const conf=j=>{const i=FK[j];if(i<0||K.conf==null)return "";return `<span class="cdot"${tipAttr(t("Data confidence: {c}",{c:t(confName[K.conf[i]])})+"<br>"+t("High: canals are mapped, there is enough fire signal and enough peat. Medium: two of the three. Low: fewer."))}>${confChar[K.conf[i]]}</span> `};
  const team=j=>{const i=FK[j];return i>=0&&K.team[i]?` <span class="tdia"${tipAttr(t("Team KHG")+(K.team[i]?": "+esc(t(K.team[i])):""))}>◆</span>`:""};
  $("#final-table").innerHTML=`<table class="ftab"><thead><tr>${th("ru",fin.only337?"Rank in 337":"Rank","num")}${th("mv","Change","num")}${th("nm","KHG")}${th("ty","Type")}${F.iv?th("iv","Intervention"):""}${profHead}${th("peat","Peat km2","num")}</tr></thead><tbody>`+
    idx.map(j=>{const d=(rk0(j)??0)-(rk(j)??0),ty0=FC0.type[j];return `<tr data-id="${F.id[j]}" class="${F.id[j]===sel?"sel":""}${F.small[j]||(F.wk||[])[j]?" small":""}">
      <td class="num">${rk(j)??""}</td>
      <td class="num dl">${!chg?"·":d>0?"▲"+d:d<0?"▼"+(-d):"·"}${chg&&ty0!==FC.type[j]?` <span class="tyb sm" style="--c:${typeVar(ty0)}"${tipAttr(t("Type at the pre-registered weights: {ty}",{ty:ty0+" "+t(TYPE_LABEL[ty0])}))}>${ty0}</span>`:""}</td>
      <td${flagTip(j)}>${conf(j)}${esc(F.name[j])}${team(j)}<small>${esc(F.prov[j]||"")}${flags(j).map(x=>" · "+x).join("")}</small></td>
      <td><span class="tyb" style="--c:${typeVar(FC.type[j])}"${tipAttr(typeTip(FC.type[j]))}>${FC.type[j]}</span><small>${FC.rt[j]}</small></td>
      ${F.iv?`<td>${ivBadge(F.iv[j])}</td>`:""}
      <td>${profBar(j)}</td>
      <td class="num">${fmt(F.peat[j],0)}</td></tr>`}).join("")+`</tbody></table>`;
  $("#final-count").textContent=t("{n} KHG",{n:idx.length});
  const sortBy=k=>{fin.dir=fin.k===k?-fin.dir:1;fin.k=k;renderFinalTable()};
  $$("#final-table th[data-k]").forEach(h=>h.onclick=()=>sortBy(h.dataset.k));
  $$("#final-table .pchip").forEach(h=>h.onclick=e=>{e.stopPropagation();sortBy(h.dataset.k)});
  $$("#final-table tr[data-id]").forEach(tr=>tr.onclick=()=>{select(tr.dataset.id);$("#profile").scrollIntoView({behavior:"smooth"})});
  renderShift(idx);
}
function renderShift(idx){    // the earlier rank-shift chart: pre-registered weights (left) against the current weights (right)
  const svg=d3.select("#fshift");if(svg.empty())return;
  const rk=j=>fin.only337?FC.ru337[j]:FC.ru[j],rk0=j=>fin.only337?FC0.ru337[j]:FC0.ru[j];
  const pool=idx.filter(j=>rk(j)!=null&&rk0(j)!=null),n=Math.max(12,Math.min(25,Math.floor(((document.querySelector('.final-sum')?.clientHeight||600)-(document.querySelector('#final-types')?.offsetHeight||250)-90)/20)));
  const a=pool.slice().sort((x,y)=>rk0(x)-rk0(y)).slice(0,n),b=pool.slice().sort((x,y)=>rk(x)-rk(y)).slice(0,n);
  const ids=[...new Set([...a,...b])];
  const W=svg.node().getBoundingClientRect().width||520,rowH=20,H=Math.max(n,ids.length)*rowH+36;svg.attr("viewBox",`0 0 ${W} ${H}`).attr("height",H);svg.selectAll("*").remove();
  const L=W*.45,R=W*.55;
  const left=ids.slice().sort((x,y)=>rk0(x)-rk0(y)),right=ids.slice().sort((x,y)=>rk(x)-rk(y));
  const yL=new Map(left.map((j,k)=>[j,32+k*rowH])),yR=new Map(right.map((j,k)=>[j,32+k*rowH]));
  const moved=ids.some(j=>rk(j)!==rk0(j));
  svg.append("text").attr("x",L).attr("y",12).attr("text-anchor","end").attr("class","bh").text(t("Pre-registered weights"));
  svg.append("text").attr("x",R).attr("y",12).attr("class","bh").text(moved?t("Your weights"):t("Your weights (same)"));
  const nm=j=>{const s=FIN.f.name[j];const m=Math.max(18,Math.floor(W*.45/7.2)-4);return s.length>m?s.slice(0,m-1)+"…":s};
  const g=svg.append("g").selectAll("g").data(ids).join("g").attr("class","bl").style("cursor","pointer")
    .on("click",(e,j)=>select(FIN.f.id[j])).on("mousemove",(e,j)=>showTip(`<b>${esc(FIN.f.name[j])}</b><br>${t("pre-registered {a} → now {b}",{a:rk0(j),b:rk(j)})}`,e)).on("mouseleave",hideTip);
  g.append("line").attr("x1",L+4).attr("x2",R-4).attr("y1",j=>yL.get(j)-4).attr("y2",j=>yR.get(j)-4)
    .attr("stroke",j=>FIN.f.id[j]===state.sel?css("--now"):Math.abs(rk(j)-rk0(j))>=3?css("--ink2"):css("--axis")).attr("stroke-width",j=>FIN.f.id[j]===state.sel?2.2:1.2);
  g.append("text").attr("x",L).attr("y",j=>yL.get(j)).attr("text-anchor","end").text(j=>`${nm(j)}  ${rk0(j)}`);
  g.append("text").attr("x",R).attr("y",j=>yR.get(j)).text(j=>`${rk(j)}  ${nm(j)}`);
}

// ---------------------------------------------------------------- map colours and tooltip
function finColour(i){
  const j=finIdx(K.id[i]);if(j===undefined||!FC||!FC.type[j])return null;
  if(fin.only337&&!FIN.f.k337[j])return null;if(fin.isl.size&&!fin.isl.has(FIN.f.isl[j]))return null;
  if(fin.colour==="type")return css("--ty"+FC.type[j]);
  if(fin.colour==="iv")return FIN.f.iv&&FIN.f.iv[j]?IV_COL[FIN.f.iv[j]]:null;
  const v=FC[fin.colour][j];return v==null?null:d3.interpolateRgb(css("--ramp0"),css("--ramp1"))(v)}
function finLegend(){
  const g=`<span style="margin-left:auto;color:var(--muted)">${t("grey: not scored or filtered out · outlined: team")}</span>`;
  if(fin.colour==="type")return TYPE_ORDER.map(ty=>`<span class="hasTip"${tipAttr(typeTip(ty))}><i class="poly" style="background:var(--ty${ty})"></i>${ty} ${esc(t(TYPE_LABEL[ty]))}</span>`).join("")+g;
  if(fin.colour==="iv")return IV_ORDER.map(v=>`<span class="hasTip"${tipAttr(ivTip(v))}><i class="poly" style="background:${IV_COL[v]}"></i>${esc(t(IV_SHORT[v]))}</span>`).join("")+g;
  const d=dimOf(fin.colour);return `<span class="hasTip"${tipAttr(dimTip(fin.colour))}>${esc(t(d[1]))}</span><span>0</span><span class="ramp" style="background:linear-gradient(90deg,${css("--ramp0")},${css("--ramp1")})"></span><span>1</span>`+g}
function finMapTools(host){
  const lb=document.createElement("span");lb.className="lab";lb.textContent=t("Colour by");lb.dataset.tip=t("Colour the KHG by their type or by one dimension score.");host.appendChild(lb);
  const s=document.createElement("span");s.className="seg";s.id="fin-colour";
  [["type","Type"],...(FIN.f.iv?[["iv","Intervention"]]:[]),...finDims().map(d=>[d[0],d[1]])].forEach(([v,tx])=>{const b=document.createElement("button");b.type="button";b.textContent=t(tx);b.dataset.tip=v==="type"?t("Type of action."):v==="iv"?ivTip("rewetting and revegetation"):dimTip(v);b.classList.toggle("on",fin.colour===v);
    b.onclick=()=>{fin.colour=v;$$("#fin-colour button").forEach(x=>x.classList.toggle("on",x===b));renderMap()};s.appendChild(b)});
  host.appendChild(s)}
function finTip(i){
  const j=finIdx(K.id[i]),F=FIN.f;
  let h=`<b>${esc(K.name[i])}</b><br><span>${esc(K.prov[i])} · ${t("peat {x} km2",{x:fmt(K.peat[i],0)})}</span>`;
  if(j===undefined||!FC.type[j])return h+`<br>${t("Not scored: no KLH peat, or below the minimum peat area and outside the 337.")}`;
  const ty=FC.type[j];
  h+=`<br><b>${ty} · ${esc(t(TYPE_LABEL[ty]))}</b> · ${F.k337[j]?t("rank {a} of the 337",{a:FC.ru337[j]}):t("rank {a}",{a:FC.ru[j]})}`;
  if(F.iv&&F.iv[j])h+=`<br>${t("Intervention")}: <b>${esc(t(IV_SHORT[F.iv[j]]))}</b>`;
  h+="<br>"+finDims().map(([key,lab])=>`${t(lab)} ${FC[key][j]==null?t("n/a"):fx(FC[key][j],2)}`).join(" · ");
  return h+`<br><span>${t("Click to open the profile.")}</span>`}

// ---------------------------------------------------------------- profile: type block, and where the KHG sits on each indicator
function profileFinal(i){
  const host=$("#p-final");if(!host)return;
  const j=FIN?finIdx(K.id[i]):undefined;
  if(j===undefined||!FC||!FC.type[j]){host.innerHTML=FIN?`<p class="hint">${t("Not scored in the final prioritisation: no KLH peat, or below the minimum peat area and outside the 337.")}</p>`:"";return}
  const F=FIN.f,ty=FC.type[j];
  const ranks=F.k337[j]?t("rank {a} of the 337 by urgency, {b} in type {ty}",{a:FC.ru337[j],b:FC.rt[j],ty}):t("rank {a} by urgency, {b} in type {ty}",{a:FC.ru[j],b:FC.rt[j],ty});
  host.innerHTML=`<div class="pf-h"><span class="tyb big" style="--c:${typeVar(ty)}"${tipAttr(typeTip(ty))}>${ty}</span><div><b>${esc(t(TYPE_LABEL[ty]))}</b> ${ivBadge((F.iv||[])[j])}<br><span class="hint">${esc(t(TYPE_NOTE[ty]))}</span>${F.iv&&F.iv[j]?`<br><span class="hint">${esc(t(IV_NOTE[F.iv[j]],{a:Math.round(FIN.meta.intervention.rewetting.min*100),b:Math.round(FIN.meta.intervention.revegetation.min*100)}))} ${t("Canal-affected {a}, open or degraded {b}.",{a:F.ind.canal_share&&F.ind.canal_share[j]!=null?pc(F.ind.canal_share[j]):t("n/a"),b:F.ind.open_share&&F.ind.open_share[j]!=null?pc(F.ind.open_share[j]):t("n/a")})}</span>`:""}</div></div>
    <div class="pf-d">${finDims().map(([k,l])=>`<div class="pf-r"><span class="hasTip"${tipAttr(dimTip(k))}>${esc(t(l))}</span>${finBar(FC[k][j],k,j)}</div>`).join("")}</div>
    <p class="hint">${esc(ranks)} · ${t("type kept in {p}% of weight draws",{p:F.st[j]==null?"–":fx(F.st[j]*100,0)})}${(F.wk||[])[j]?" · "+t("no KLH peat: whole KHG used, less reliable"):""}${F.small[j]?" · "+t("small peat area: less reliable"):""}${FC.lowf[j]?" · "+t("low feasibility"):""}${FC.hix[j]?" · "+t("high exposure"):""}${!atRef()&&FC0.type[j]!==ty?" · "+t("type {a} at the pre-registered weights",{a:FC0.type[j]}):""}</p>`;
}
function finRankTile(i){   // the first two profile tiles: rank and type
  const j=finIdx(K.id[i]);if(j===undefined||!FC||!FC.type[j])return [[t("n/a"),t("Rank by urgency")],[t("n/a"),t("Type")]];
  const F=FIN.f,d=(FC0.ru[j]??0)-(FC.ru[j]??0);
  return [[`${F.k337[j]?FC.ru337[j]:FC.ru[j]}<small>${!atRef()&&d?(d>0?"▲"+d:"▼"+(-d)):""}</small>`,F.k337[j]?t("Rank of the 337 by urgency"):t("Rank by urgency")],
          [`<span style="color:var(--ty${FC.type[j]})">${FC.type[j]}</span>`,t(TYPE_LABEL[FC.type[j]])]]}
function renderStrips(i,ic=-1){
  const host=$("#p-strips");host.innerHTML="";host.classList.toggle("cmp",ic>=0);
  if(!FIN){renderStripsOld(i,ic);return}
  const F=FIN.f,j=finIdx(K.id[i]),jc=ic>=0?finIdx(K.id[ic]):undefined;
  host.insertAdjacentHTML("beforeend",`<h3 class="hasTip"${tipAttr(t("Where this KHG sits on each indicator among the KHG with at least {m} km2 of peat. Grey bars: how those KHG are spread. Marker: this KHG; ring: the KHG compared.",{m:FIN.meta.min_peat}))}>${t("Indicators")}</h3>`);
  for(const [key,lab,dn] of finDims()){
    host.insertAdjacentHTML("beforeend",`<div class="gs hasTip"${tipAttr(dimTip(key))}><span class="sw" style="background:var(--dim-${key})"></span>${t(lab)}</div>`);
    for(const k of Object.keys(FIN.meta.dims[dn])){
      const x=F.ind[k];if(!x)continue;
      const vals=[];for(let a=0;a<x.length;a++)if(F.pool[a]&&x[a]!=null)vals.push(x[a]);vals.sort(d3.ascending);
      const v=j!==undefined?x[j]:null,vc=jc!==undefined?x[jc]:null,m=IND[k]||[k,"",z=>fx(z,2)];
      const row=document.createElement("div");row.className="strip";
      row.innerHTML=`<span class="t hasTip"${tipAttr(indTip(k))}>${esc(t(m[0]))}<b>w ${fmt(fin.w[k],1)}</b></span><svg></svg><span class="n">${v==null?t("n/a"):m[2](v)}</span>`;host.appendChild(row);
      const svgEl=row.querySelector("svg"),svg=d3.select(svgEl);const W=svgEl.clientWidth||240;svg.attr("viewBox",`0 0 ${W} 22`);
      if(vals.length<2)continue;
      const lo=d3.quantileSorted(vals,.02),hi=d3.quantileSorted(vals,.98),sx=d3.scaleLinear([lo,Math.max(hi,lo+1e-9)],[4,W-4]).clamp(true);
      const bins=d3.bin().domain(sx.domain()).thresholds(28)(vals.map(a=>Math.min(Math.max(a,lo),hi)));const mx=d3.max(bins,b=>b.length);
      svg.append("g").selectAll("rect").data(bins).join("rect").attr("x",b=>sx(b.x0)).attr("width",b=>Math.max(1,sx(b.x1)-sx(b.x0)-1)).attr("y",b=>20-18*Math.sqrt(b.length/mx)).attr("height",b=>18*Math.sqrt(b.length/mx)).attr("fill",css("--axis")).attr("opacity",.7);
      if(vc!=null)svg.append("circle").attr("cx",sx(vc)).attr("cy",11).attr("r",5).attr("fill","none").attr("stroke",css("--ink2")).attr("stroke-width",1.6);
      if(v!=null){svg.append("rect").attr("x",sx(v)-1.5).attr("y",1).attr("width",3).attr("height",20).attr("fill",css("--now"));
        const p=(d3.bisectLeft(vals,v)+d3.bisectRight(vals,v))/2/vals.length;
        svgEl.dataset.tip=`<b>${esc(t(m[0]))}: ${m[2](v)}</b><br>${t("Higher than {p}% of the KHG with at least {m} km2 of peat.",{p:fx(100*p,0),m:FIN.meta.min_peat})}${vc!=null?`<br>${esc(K.name[ic])}: ${m[2](vc)}`:""}`}
    }
  }
}

// ---------------------------------------------------------------- export of the underlying data
async function csvText(n){
  const el=document.getElementById("csv-"+n);if(!el)return null;
  const bin=Uint8Array.from(atob(el.textContent.trim()),c=>c.charCodeAt(0));
  if(!window.DecompressionStream)throw new Error("no DecompressionStream");
  const s=new Blob([bin]).stream().pipeThrough(new DecompressionStream("gzip"));
  return await new Response(s).text();
}
async function downloadData(n){
  const d=DATA.exports[n];const tx=await csvText(n);if(tx==null)return;
  const a=document.createElement("a");a.href=URL.createObjectURL(new Blob(["\ufeff"+tx],{type:d.file.endsWith(".json")?"application/json":"text/csv;charset=utf-8"}));
  a.download=d.file;document.body.appendChild(a);a.click();setTimeout(()=>{URL.revokeObjectURL(a.href);a.remove()},500);
}
function downloadCurrent(){
  const F=FIN.f,idx=finRows(),ks=Object.keys(refW()),dd=finDims();
  const head=["khg_code","khg_name","provinces","island","klh_337","type","rank_urgency","rank_urgency_337","rank_in_type",...dd.map(d=>d[2]),"intervention","flag_low_feasibility","flag_high_exposure","type_at_rule",...ks,...ks.map(k=>"w_"+k)];
  const rows=idx.map(j=>[F.id[j],F.name[j],F.prov[j],F.isl[j],F.k337[j],FC.type[j],FC.ru[j],FC.ru337[j],FC.rt[j],...dd.map(d=>FC[d[0]][j]==null?"":+FC[d[0]][j].toFixed(4)),(F.iv||[])[j]||"",FC.lowf[j],FC.hix[j],FC0.type[j],...ks.map(k=>F.ind[k]?F.ind[k][j]??"":""),...ks.map(k=>fin.w[k])]);
  const csv=[head,...rows].map(r=>r.map(v=>`"${String(v??"").replace(/"/g,'""')}"`).join(",")).join("\n");
  const a=document.createElement("a");a.href=URL.createObjectURL(new Blob(["\ufeff"+csv],{type:"text/csv;charset=utf-8"}));a.download="khg_priority_current_view.csv";document.body.appendChild(a);a.click();setTimeout(()=>{URL.revokeObjectURL(a.href);a.remove()},500);
}
function buildExport(){
  const host=$("#export-list");if(!host||!DATA.exports)return;
  host.innerHTML=(FIN?`<li><div><b>khg_priority_current_view.csv</b> <small>${t("the list as shown")}</small><br><span>${esc(t("The KHG in the list now, with your filters and weights: scores, type, ranks, flags, the type at the pre-registered weights, every indicator and the weights used."))}</span></div><button type="button" id="export-cur">${t("Download")}</button></li>`:"")+
    DATA.exports.map((d,n)=>`<li><div><b>${esc(d.file)}</b> <small>${fmt(d.rows,0)} ${t("rows")} · ${fmt(d.cols,0)} ${t("columns")} · ${d.kb>=1024?fx(d.kb/1024,1)+" MB":fmt(Math.max(1,Math.round(d.kb)),0)+" kB"}</small><br><span>${esc(t(d.desc))}</span><br><small class="src">${esc(d.src)}</small></div>
    <button type="button" data-n="${n}">${t("Download")}</button></li>`).join("");
  $$("#export-list button[data-n]").forEach(b=>b.onclick=()=>downloadData(+b.dataset.n));
  if($("#export-cur"))$("#export-cur").onclick=downloadCurrent;
  $("#export-all").onclick=async()=>{for(let n=0;n<DATA.exports.length;n++){await downloadData(n);await new Promise(r=>setTimeout(r,400))}};
  $("#export-btn").onclick=()=>$("#export").showModal();$("#export-close").onclick=()=>$("#export").close();
  $("#export-note").textContent=t("Files as written by the pipeline; the date of each is under its name. Areas in km2 or ha as named in each column; shares are 0 to 1. The KLH layers behind them are for team use only.");
}
