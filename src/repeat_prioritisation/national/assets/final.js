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
const typeVar=ty=>`var(--ty${ty})`;
const finIdx=id=>FIN?FIN.idx[id]:undefined;

function finCut(dim){const c=FIN.meta.cuts[{u:"urgency",c:"complexity",s:"stake"}[dim]];return c||null}
function finBar(v,dim){
  if(v==null)return `<span class="fbar na">${t("n/a")}</span>`;
  const c=finCut(dim),m=c?c.map(x=>`<i style="left:${(x*100).toFixed(1)}%"></i>`).join(""):"";
  return `<span class="fbar"><b style="width:${(v*100).toFixed(1)}%"></b>${m}</span><span class="fnum">${fx(v,2)}</span>`;
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
  let g=`<div class="fmx"><div class="fmx-y">${t("Urgency")} ↑</div><div class="fmx-grid">`;
  for(const ur of [2,1,0]){g+=`<div class="fmx-rl">${lv[ur]}</div>`;
    for(const cr of [0,1,2]){const c=cnt[ur+"-"+cr]||{};const parts=TYPE_ORDER.filter(ty=>c[ty]).map(ty=>`<button type="button" class="fmx-t" data-ty="${ty}" style="--c:${typeVar(ty)}"${tipAttr(`<b>${ty} · ${t(TYPE_LABEL[ty])}</b><br>${t(TYPE_NOTE[ty])}`)}>${ty}<b>${c[ty]}</b></button>`).join("");
      g+=`<div class="fmx-c">${parts||"<span class='fmx-0'>0</span>"}</div>`}}
  g+=`<div></div>${[0,1,2].map(cr=>`<div class="fmx-cl">${lv[cr]}</div>`).join("")}</div><div class="fmx-x">${t("Complexity")} →</div></div>`;
  $("#final-matrix").innerHTML=g;
  // type summary
  const rows=M_.types.filter(r=>r.type);
  const mx={khg:d3.max(rows,r=>fin.only337?r.in_337:r.khg),peat:d3.max(rows,r=>r.peat_km2),dmg:d3.max(rows,r=>r.priority_ha)};
  $("#final-types").innerHTML=`<table class="ftypes"><thead><tr><th>${t("Type")}</th><th>${t(fin.only337?"KHG in the 337":"KHG")}</th><th>${t("Peat")} km2</th><th>${t("SKEG-damaged peat")} ha</th><th>${t("Low feasibility")}</th></tr></thead><tbody>`+
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
  ].map(([v,l])=>`<div class="kpi"><div class="v">${v}</div><div class="l">${esc(l)}</div></div>`).join("");
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
  const sel=state.sel;
  $("#final-table").innerHTML=`<table class="ftab"><thead><tr>${head.map(([k,l])=>`<th data-k="${k}" class="${fin.k===k?"on":""}">${esc(t(l))}${fin.k===k?(fin.dir>0?" ▾":" ▴"):""}</th>`).join("")}</tr></thead><tbody>`+
    idx.map(j=>`<tr data-id="${F.id[j]}" class="${F.id[j]===sel?"sel":""}${F.small[j]?" small":""}">
      <td class="num">${fin.only337?(F.ru337[j]??""):F.ru[j]}</td>
      <td>${esc(F.name[j])}<small>${esc(F.prov[j]||"")}${F.small[j]?" · "+t("small peat area"):""}${F.lowf[j]?" · "+t("low feasibility"):""}</small></td>
      <td><span class="tyb" style="--c:${typeVar(F.type[j])}"${tipAttr(`<b>${t(TYPE_LABEL[F.type[j]])}</b><br>${t(TYPE_NOTE[F.type[j]])}`)}>${F.type[j]}</span><small>${F.rt[j]}</small></td>
      <td>${finBar(F.u[j],"u")}</td><td>${finBar(F.s[j],"s")}</td><td>${finBar(F.c[j],"c")}</td><td>${finBar(F.f[j],"f")}</td>
      <td class="num">${F.st[j]==null?t("n/a"):fx(F.st[j]*100,0)+"%"}</td><td class="num">${fmt(F.peat[j],0)}</td></tr>`).join("")+`</tbody></table>`;
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
  host.innerHTML=`<div class="pf-h"><span class="tyb big" style="--c:${typeVar(ty)}">${ty}</span><div><b>${esc(t(TYPE_LABEL[ty]))}</b><br><span class="hint">${esc(t(TYPE_NOTE[ty]))}</span></div></div>
    <div class="pf-d">${DIMS.map(([k,l])=>{const v={u:F.u,s:F.s,c:F.c,f:F.f}[k][j];return `<div class="pf-r"><span>${esc(t(l))}</span>${finBar(v,k)}</div>`}).join("")}</div>
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
