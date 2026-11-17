// ---------------------------------------------------------------- final prioritisation (repeat-national-final) and data export
// Inserted into dashboard.js before init(); uses its helpers (t, fmt, fx, esc, $, $$, select, state, K, chip, tipAttr).
const FIN=DATA.final||null;
const TYPE_ORDER=["A","B","C","D","E"];
const TYPE_LABEL={A:"Quick action",B:"Multi-party coordination",C:"Staged restoration",D:"Protect and monitor",E:"Monitor"};
const TYPE_NOTE={A:"High urgency, low or medium complexity: act now through KLH and the villages.",
  B:"High urgency, high complexity: needs coordination of companies, the Ministry of Forestry, KLH and villages.",
  C:"Medium urgency: restore in stages.",D:"Low urgency, high stake (deep peat, dome, protected function): protect and monitor.",
  E:"Low urgency, low or medium stake: monitor."};
const DIMS=[["u","Urgency"],["s","Stake"],["c","Complexity"],["f","Feasibility"]];
const fin={q:"",type:"",only337:true,k:"ru",dir:1};
const DIM_KEY={u:"urgency",s:"stake",c:"complexity",f:"feasibility"};
const DIM_TIP={
  u:"How likely the peat is to burn and degrade further: burned share of peat per year (counts double), repeat burning, hotspots 2012-2025 and this year, SKEG 2024 damage, canal-affected peat.",
  s:"What would be lost: peat 3 m or deeper, dome landform, protected peat ecosystem function, peat area.",
  c:"How hard it is to act: tenure complexity (counts double: licences on community land, contested land, claim types, licence holders), actor types holding damaged peat, villages involved.",
  f:"How easy rewetting is: dry-season water balance (P - E) and existing BRGM structures per km2 of peat. Partly echoes urgency, because blocks were built where fires were; a flag only."};
const SCORE_NOTE="Score 0 to 1: weighted mean of the indicators' percentile ranks among the KHG with at least 25 km2 of peat. Ticks mark the tercile cuts.";
const IND={u_fire_freq:["Burned share of peat per year, 2015-2025",v=>fx(v*100,2)+"%"],u_burn_repeat:["Peat burned twice or more",v=>fx(v*100,1)+"%"],
  u_hotspot:["Hotspots per km2 of peat per year, 2012-2025",v=>fx(v,2)],u_hotspot_now:["Hotspots this year per km2 of peat",v=>fx(v,2)],
  damage_share:["SKEG 2024 damaged share of peat",v=>fx(v*100,0)+"%"],canal_share:["Canal-affected share of peat",v=>fx(v*100,0)+"%"],
  thick3m_share:["Peat 3 m or deeper",v=>fx(v*100,0)+"%"],dome_share:["Peat on dome landform",v=>fx(v*100,0)+"%"],
  protected_share:["Peat with protected function",v=>fx(v*100,0)+"%"],peat_km2:["Peat area",v=>fmt(v,0)+" km2"],
  tenure_complexity:["Tenure complexity index",v=>fx(v,2)],actor_types:["Actor types holding damaged peat (of 4)",v=>fmt(v,0)],
  villages:["Target and DMPG villages",v=>fmt(v,0)],dry_balance_mm:["Dry-season P - E",v=>fmt(v,0)+" mm"],
  brgm_blocks_per_km2:["BRGM structures per km2 of peat",v=>fx(v,2)]};
function tercile(v,dim){if(v==null)return "";if(dim==="f")return FIN.meta.fcut!=null&&v<FIN.meta.fcut?t("low (flagged)"):"";const c=finCut(dim);if(!c)return "";return v>=c[1]?t("high"):v>=c[0]?t("medium"):t("low")}
function dimTip(dim,j){
  const lab=DIMS.find(d=>d[0]===dim)[1];let h=`<b>${esc(t(lab))}</b><br>${esc(t(DIM_TIP[dim]))}<br><span>${esc(t(SCORE_NOTE))}</span>`;
  if(j===undefined)return h;
  const F=FIN.f,v=F[dim][j];
  h=`<b>${esc(F.name[j])}: ${esc(t(lab))} ${v==null?t("n/a"):fx(v,2)}</b>${v!=null&&tercile(v,dim)?" ("+esc(tercile(v,dim))+")":""}<br>`;
  const w=(FIN.meta.dims||{})[DIM_KEY[dim]]||{};
  h+=Object.keys(w).map(k=>{const iv=F.ind&&F.ind[k]?F.ind[k][j]:null;const m=IND[k]||[k,x=>fx(x,2)];return `${esc(t(m[0]))}: <b>${iv==null?t("n/a"):m[1](iv)}</b>${w[k]!==1?` <span>(${t("weight")} ${fmt(w[k],1)})</span>`:""}`}).join("<br>");
  return h+`<br><span>${esc(t(DIM_TIP[dim]))}</span>`;
}
const typeVar=ty=>`var(--ty${ty})`;
const finIdx=id=>FIN?FIN.idx[id]:undefined;

function finCut(dim){const c=FIN.meta.cuts[{u:"urgency",c:"complexity",s:"stake"}[dim]];return c||null}
function finBar(v,dim,j){
  const tip=tipAttr(dimTip(dim,j));
  if(v==null)return `<span class="fbar na"${tip}>${t("n/a")}</span>`;
  const c=dim==="f"?(FIN.meta.fcut!=null?[FIN.meta.fcut]:null):finCut(dim),m=c?c.map(x=>`<i style="left:${(x*100).toFixed(1)}%"></i>`).join(""):"";
  return `<span class="fbar"${tip}><b style="width:${(v*100).toFixed(1)}%"></b>${m}</span><span class="fnum"${tip}>${fx(v,2)}</span>`;
}
function buildFinal(){
  const host=$("#final");if(!host)return;
  if(!FIN){host.hidden=true;return}
  const M_=FIN.meta,V=M_.validation,S=M_.sensitivity;
  $("#final-sub").textContent=t("Four dimensions per KHG, each the weighted mean of its indicators' percentile ranks; types from the terciles of urgency, complexity and stake. Rule written {d}; KLH's 337 work list scored.",{d:M_.written});
  // typology matrix: rows = urgency tercile (high on top), columns = complexity tercile
  const F=FIN.f,cnt={};
  for(let j=0;j<F.id.length;j++){if(!F.type[j])continue;if(fin.only337&&!F.k337[j])continue;
    const ur=F.u[j]>=M_.cuts.urgency[1]?2:F.u[j]>=M_.cuts.urgency[0]?1:0,cr=F.c[j]==null?1:F.c[j]>=M_.cuts.complexity[1]?2:F.c[j]>=M_.cuts.complexity[0]?1:0;
    const key=ur+"-"+cr;(cnt[key]=cnt[key]||{})[F.type[j]]=(cnt[key][F.type[j]]||0)+1}
  const lv=[t("low"),t("medium"),t("high")];
  const lvTip=d=>tipAttr(`${esc(t(DIM_TIP[d]))}<br><span>${t("Terciles of the KHG with at least 25 km2 of peat: low below {a}, high from {b}.",{a:fx(finCut(d)[0],2),b:fx(finCut(d)[1],2)})}</span>`);
  let g=`<div class="fmx"><div class="fmx-y"${lvTip("u")}>${t("Urgency")} ↑</div><div class="fmx-grid">`;
  for(const ur of [2,1,0]){g+=`<div class="fmx-rl"${lvTip("u")}>${lv[ur]}</div>`;
    for(const cr of [0,1,2]){const c=cnt[ur+"-"+cr]||{};const parts=TYPE_ORDER.filter(ty=>c[ty]).map(ty=>`<button type="button" class="fmx-t" data-ty="${ty}" style="--c:${typeVar(ty)}"${tipAttr(`<b>${ty} · ${t(TYPE_LABEL[ty])}</b><br>${t(TYPE_NOTE[ty])}`)}>${ty}<b>${c[ty]}</b></button>`).join("");
      g+=`<div class="fmx-c">${parts||"<span class='fmx-0'>0</span>"}</div>`}}
  g+=`<div></div>${[0,1,2].map(cr=>`<div class="fmx-cl"${lvTip("c")}>${lv[cr]}</div>`).join("")}</div><div class="fmx-x"${lvTip("c")}>${t("Complexity")} →</div></div>`;
  $("#final-matrix").innerHTML=g;
  // type summary
  const rows=M_.types.filter(r=>r.type);
  const mx={khg:d3.max(rows,r=>fin.only337?r.in_337:r.khg),peat:d3.max(rows,r=>r.peat_km2),dmg:d3.max(rows,r=>r.priority_ha)};
  $("#final-types").innerHTML=`<table class="ftypes"><thead><tr><th${tipAttr(t("Click a type to filter the list."))}>${t("Type")}</th><th>${t(fin.only337?"KHG in the 337":"KHG")}</th><th${tipAttr(t("KLH peat (PPEG 2026) of the KHG of the type."))}>${t("Peat")} km2</th><th${tipAttr(t("Peat damaged in SKEG 2024 (KLH's priority area), from the PPEG analysis."))}>${t("SKEG-damaged peat")} ha</th><th${tipAttr(t("KHG in the lowest tercile of feasibility: flagged, the type is not changed."))}>${t("Low feasibility")}</th></tr></thead><tbody>`+
    rows.map(r=>{const n=fin.only337?r.in_337:r.khg;return `<tr class="${fin.type===r.type?"on":""}" data-ty="${r.type}"><td><span class="tyb" style="--c:${typeVar(r.type)}">${r.type}</span> ${esc(t(TYPE_LABEL[r.type]))}</td>
      <td><span class="hb" style="width:${(60*n/mx.khg).toFixed(0)}px;background:${typeVar(r.type)}"></span>${fmt(n,0)}</td>
      <td><span class="hb" style="width:${(60*r.peat_km2/mx.peat).toFixed(0)}px;background:${typeVar(r.type)}"></span>${fmt(r.peat_km2,0)}</td>
      <td><span class="hb" style="width:${(60*r.priority_ha/mx.dmg).toFixed(0)}px;background:${typeVar(r.type)}"></span>${fmt(r.priority_ha,0)}</td>
      <td>${fmt(r.low_feasibility,0)}</td></tr>`}).join("")+`</tbody></table><p class="hint">${t("Counts include every scored KHG; the 337 switch filters the matrix and the list.")}</p>`;
  $$("#final-types tr[data-ty]").forEach(tr=>tr.onclick=()=>{fin.type=fin.type===tr.dataset.ty?"":tr.dataset.ty;buildFinal()});
  $$("#final-matrix .fmx-t").forEach(b=>b.onclick=()=>{fin.type=fin.type===b.dataset.ty?"":b.dataset.ty;buildFinal()});
  // validation and stability
  const vu=V.urgency,vf=V.fire_history_only;
  $("#final-kpis").innerHTML=[
    [`${fx(vu.capture_top20pct*100,0)}<small>%</small>`,t("of 2026 burned peat in the top 20% by urgency (fire history alone: {b}%)",{b:fx(vf.capture_top20pct*100,0)})],
    [fx(vu.auc,2),t("AUC against burned or not in 2026 (fire history alone: {b})",{b:fx(vf.auc,2)})],
    [`${fx(S.share_khg_type_stable_80pct*100,0)}<small>%</small>`,t("of KHG keep their type in 80% of {n} runs with every weight ±50%",{n:S.runs})],
  ].map(([v,l],k)=>`<div class="kpi"${tipAttr(t(["Urgency built without this year's hotspots, from data up to 2025, tested on the peat that burned in 2026: the 20% most urgent KHG hold this share of it.","Area under the ROC curve: the chance that a KHG that burned in 2026 ranks above one that did not (0.5 = chance).","Every weight multiplied by a random factor between 0.5 and 1.5, {n} times; KHG keeping their type in at least 80% of the draws."][k],{n:S.runs}))}><div class="v">${v}</div><div class="l">${esc(l)}</div></div>`).join("");
  // controls
  const sw=$("#final-ctl");sw.innerHTML="";
  const seg=document.createElement("span");seg.className="seg";
  [[true,"KLH 337"],[false,"All scored KHG"]].forEach(([v,tx])=>{const b=document.createElement("button");b.type="button";b.textContent=t(tx);b.classList.toggle("on",fin.only337===v);b.onclick=()=>{fin.only337=v;buildFinal()};seg.appendChild(b)});
  sw.appendChild(seg);
  const q=document.createElement("input");q.type="search";q.placeholder=t("Search KHG");q.value=fin.q;q.className="fq";q.oninput=()=>{fin.q=q.value;renderFinalTable()};sw.appendChild(q);
  if(fin.type){const b=document.createElement("button");b.type="button";b.className="ghost";b.textContent=t("Type {ty} · clear",{ty:fin.type});b.onclick=()=>{fin.type="";buildFinal()};sw.appendChild(b)}
  renderFinalTable();
}
function renderFinalTable(){
  const F=FIN.f,q=fin.q.trim().toLowerCase();
  let idx=[];for(let j=0;j<F.id.length;j++){if(!F.type[j])continue;if(fin.only337&&!F.k337[j])continue;if(fin.type&&F.type[j]!==fin.type)continue;
    if(q&&!(F.name[j].toLowerCase().includes(q)||F.id[j].toLowerCase().includes(q)||(F.prov[j]||"").toLowerCase().includes(q)))continue;idx.push(j)}
  const key={ru:j=>fin.only337?F.ru337[j]:F.ru[j],ty:j=>TYPE_ORDER.indexOf(F.type[j])*1000+F.rt[j],u:j=>-F.u[j],s:j=>-(F.s[j]??-1),c:j=>-(F.c[j]??-1),f:j=>-(F.f[j]??-1),st:j=>-(F.st[j]??0),peat:j=>-F.peat[j],nm:j=>F.name[j]}[fin.k];
  idx.sort((a,b)=>{const x=key(a),y=key(b);return (x<y?-1:x>y?1:0)*fin.dir});
  const head=[["ru",fin.only337?"Rank in 337":"Rank"],["nm","KHG"],["ty","Type"],["u","Urgency"],["s","Stake"],["c","Complexity"],["f","Feasibility"],["st","Type stability"],["peat","Peat km2"]];
  const HT={ru:t("Rank by urgency (1 = most urgent), among KLH's 337 or among all scored KHG. Click a header to sort."),nm:t("Click a row to open the KHG profile below."),
    ty:t("Type of action from the terciles of urgency, complexity and stake; the small number is the rank within the type."),
    u:dimTip("u"),s:dimTip("s"),c:dimTip("c"),f:dimTip("f"),
    st:t("Share of {n} weight draws (every weight ±50%) in which the KHG keeps its type.",{n:FIN.meta.sensitivity.runs}),peat:t("KLH peat inside the KHG (PPEG 2026).")};
  const sel=state.sel;
  $("#final-table").innerHTML=`<table class="ftab"><thead><tr>${head.map(([k,l])=>`<th data-k="${k}" class="${fin.k===k?"on":""}"${tipAttr(HT[k]||"")}>${esc(t(l))}${fin.k===k?(fin.dir>0?" ▾":" ▴"):""}</th>`).join("")}</tr></thead><tbody>`+
    idx.map(j=>`<tr data-id="${F.id[j]}" class="${F.id[j]===sel?"sel":""}${F.small[j]?" small":""}">
      <td class="num">${fin.only337?(F.ru337[j]??""):F.ru[j]}</td>
      <td>${esc(F.name[j])}<small>${esc(F.prov[j]||"")}${F.small[j]?" · "+t("small peat area"):""}${F.lowf[j]?" · "+t("low feasibility"):""}</small></td>
      <td><span class="tyb" style="--c:${typeVar(F.type[j])}"${tipAttr(`<b>${t(TYPE_LABEL[F.type[j]])}</b><br>${t(TYPE_NOTE[F.type[j]])}`)}>${F.type[j]}</span><small>${F.rt[j]}</small></td>
      <td>${finBar(F.u[j],"u",j)}</td><td>${finBar(F.s[j],"s",j)}</td><td>${finBar(F.c[j],"c",j)}</td><td>${finBar(F.f[j],"f",j)}</td>
      <td class="num"${tipAttr(t(F.st[j]==null?"Small KHG: not in the sensitivity test.":"Share of {n} weight draws (every weight ±50%) in which this KHG keeps its type. Below 80%: the type is a close call.",{n:FIN.meta.sensitivity.runs}))}>${F.st[j]==null?t("n/a"):fx(F.st[j]*100,0)+"%"}</td><td class="num">${fmt(F.peat[j],0)}</td></tr>`).join("")+`</tbody></table>`;
  $("#final-count").textContent=t("{n} KHG",{n:idx.length});
  $$("#final-table th").forEach(th=>th.onclick=()=>{fin.dir=fin.k===th.dataset.k?-fin.dir:1;fin.k=th.dataset.k;renderFinalTable()});
  $$("#final-table tr[data-id]").forEach(tr=>tr.onclick=()=>{select(tr.dataset.id);$("#profile").scrollIntoView({behavior:"smooth"})});
}
function profileFinal(i){
  const host=$("#p-final");if(!host)return;
  const j=FIN?finIdx(K.id[i]):undefined;
  if(j===undefined||!FIN.f.type[j]){host.innerHTML=FIN?`<p class="hint">${t("Not scored in the final prioritisation: no KLH peat, or below the minimum peat area and outside the 337.")}</p>`:"";return}
  const F=FIN.f,ty=F.type[j];
  const ranks=F.k337[j]?t("rank {a} of the 337 by urgency, {b} in type {ty}",{a:F.ru337[j],b:F.rt[j],ty}):t("rank {a} by urgency, {b} in type {ty}",{a:F.ru[j],b:F.rt[j],ty});
  host.innerHTML=`<div class="pf-h"><span class="tyb big" style="--c:${typeVar(ty)}"${tipAttr(`<b>${ty} · ${esc(t(TYPE_LABEL[ty]))}</b><br>${esc(t(TYPE_NOTE[ty]))}<br><span>${esc(t("Type from the terciles of urgency, complexity and stake. Feasibility does not change the type."))}</span>`)}>${ty}</span><div><b>${esc(t(TYPE_LABEL[ty]))}</b><br><span class="hint">${esc(t(TYPE_NOTE[ty]))}</span></div></div>
    <div class="pf-d">${DIMS.map(([k,l])=>{const v={u:F.u,s:F.s,c:F.c,f:F.f}[k][j];return `<div class="pf-r"><span class="hasTip"${tipAttr(dimTip(k))}>${esc(t(l))}</span>${finBar(v,k,j)}</div>`}).join("")}</div>
    <p class="hint">${esc(ranks)} · ${t("type kept in {p}% of weight draws",{p:F.st[j]==null?"–":fx(F.st[j]*100,0)})}${F.small[j]?" · "+t("small peat area: less reliable"):""}${F.lowf[j]?" · "+t("low feasibility"):""}</p>`;
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
function buildExport(){
  const host=$("#export-list");if(!host||!DATA.exports)return;
  host.innerHTML=DATA.exports.map((d,n)=>`<li><div><b>${esc(d.file)}</b> <small>${fmt(d.rows,0)} ${t("rows")} · ${fmt(d.cols,0)} ${t("columns")} · ${d.kb>=1024?fx(d.kb/1024,1)+" MB":fmt(Math.max(1,Math.round(d.kb)),0)+" kB"}</small><br><span>${esc(t(d.desc))}</span><br><small class="src">${esc(d.src)}</small></div>
    <button type="button" data-n="${n}">${t("Download")}</button></li>`).join("");
  $$("#export-list button").forEach(b=>b.onclick=()=>downloadData(+b.dataset.n));
  $("#export-all").onclick=async()=>{for(let n=0;n<DATA.exports.length;n++){await downloadData(n);await new Promise(r=>setTimeout(r,400))}};
  $("#export-btn").onclick=()=>$("#export").showModal();$("#export-close").onclick=()=>$("#export").close();
  $("#export-note").textContent=t("Files as written by the pipeline; the date of each is under its name. Areas in km2 or ha as named in each column; shares are 0 to 1. The KLH layers behind them are for team use only.");
}
