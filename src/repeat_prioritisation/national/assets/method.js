// ---------------------------------------------------------------- Method: a short explanation of the prioritisation, numbers from the run
const D=DATA,RU=D.rule,NN=D.n;
const DIM_Q={u:"When to act?",s:"What is at stake?",c:"Who must act together?",f:"How easy is rewetting on the ground?",p:"How many people are affected?"};
const DIM_USE={u:"Sets the type",s:"Sets the type (low urgency)",c:"Sets the type (high urgency)",f:"Flag only",p:"Flag only"};
const SOURCES=[
  ["Peat extent","KLH peat land map (PPEG 2026), 1:50,000; KHG boundaries 2017"],
  ["Fire history","KLHK burnt area 2015 to 2026; VIIRS hotspots (NASA FIRMS) 2012 to 2026"],
  ["Fire this year","MODIS hotspots: KLH file, then NASA FIRMS near-real-time, medium and high confidence"],
  ["Peat damage and drainage","SKEG 2024 damage map and canal-influence zones (KLH, PPEG); canal map of the project (OSM based)"],
  ["Peat depth and landform","KLHK peat ecosystem function map (FEG) thickness classes; BBSDLP peat dome landform"],
  ["Land status","Kawasan hutan 2023 (1:250,000); business licences 2025; social forestry; PPTPKH"],
  ["Villages","Village boundaries 2023 (KLH); Bluebook target villages; DMPG villages (SiTMAT)"],
  ["Access and water","RBI rivers (two-bank), lakes and roads"],
  ["Climate","TerraClimate rainfall and evaporation, about 4 km"],
  ["People","IHME Populace 2025, third quarter, 40 m"],
  ["Land cover","KLH land cover 2022 (PL_2022)"]];
function weightsTable(dim){const spec=RU.dims[dim]||{};
  return `<table class="mt"><thead><tr><th>${esc(t("Indicator"))}</th><th class="n">${esc(t("Weight"))}</th></tr></thead><tbody>${Object.entries(spec).map(([k,w])=>{const m=IND[k]||[k,""];
    return `<tr${tipAttr(`<b>${esc(t(m[0]))}</b><br>${esc(t(m[1]))}`)}><td>${esc(t(m[0]))}${RU.dirs[k]==="-"?` <span class="small">(${esc(t("lower is better"))})</span>`:""}</td><td class="n">${w?fmt(w,1):`<span class="small">0 · ${esc(t("optional"))}</span>`}</td></tr>`}).join("")}</tbody></table>`}
function render(){
  const ty=Object.fromEntries(D.types.map(r=>[r.type,r]));
  const ivn=Object.fromEntries(D.iv.map(r=>[r.intervention,r]));
  const a=Math.round(RU.intervention.rewetting.min*100),b=Math.round(RU.intervention.revegetation.min*100);
  const cut=(k,i)=>fx(D.cuts[k][i],2);
  const S=[];
  S.push(`<section class="card"><h2>${esc(t("In short"))}</h2>
    <p>${esc(t("The prioritisation ranks Indonesia's peat hydrological units (KHG) by how urgently their peat needs restoration, and says what kind of action each one needs. It is built for KLH's list of {k} priority KHG and covers all {n} KHG for comparison.",{k:fmt(NN.k337,0),n:fmt(NN.khg,0)}))}</p>
    <div class="flow">
      <div class="st"><i>1</i><b>${esc(t("Indicators"))}</b><span>${esc(t("Measured on the KLH peat inside each KHG: fire, damage, drainage, depth, land status, villages, access, people."))}</span></div>
      <div class="st"><i>2</i><b>${esc(t("Five dimensions"))}</b><span>${esc(t("Indicators are ranked against the other KHG and averaged with weights into urgency, stake, complexity, feasibility and people."))}</span></div>
      <div class="st"><i>3</i><b>${esc(t("Type of action"))}</b><span>${esc(t("Urgency, then complexity or stake, place each KHG in one of five types, A to E."))}</span></div>
      <div class="st"><i>4</i><b>${esc(t("Intervention"))}</b><span>${esc(t("Canal drainage and open cover say whether the peat needs rewetting, revegetation, both, or protection."))}</span></div>
    </div>
    <p class="small">${esc(t("Rule version {v}, written {w} before any result was seen. Weights are provisional and can be changed live on the KHG priority page.",{v:RU.version,w:RU.written}))}</p></section>`);
  S.push(`<section class="card" id="m-unit"><h2>${esc(t("Unit of analysis"))}</h2>
    <ul><li>${esc(t("The KHG (kesatuan hidrologis gambut) is the unit: water moves within it, so rewetting is planned per KHG. Indonesia has {n} KHG with {p} km2 of KLH peat.",{n:fmt(NN.khg,0),p:fmt(NN.peat_km2,0)}))}</li>
    <li>${esc(t("{s} KHG are scored, including all {k} of KLH's list. Scores are ranked against the {pool} KHG with at least {m} km2 of peat, so a few very small KHG do not set the scale.",{s:fmt(NN.scored,0),k:fmt(NN.scored337,0),pool:fmt(NN.pool,0),m:RU.min_peat}))}</li>
    <li>${esc(t("{w} KHG of the list have no peat in KLH's peat map, although they are peat hydrological units. They are scored with the whole KHG as the peat extent, and are flagged as less reliable.",{w:fmt(NN.whole,0)}))}</li>
    <li>${esc(t("Indicators are measured on the peat inside the KHG, not on the whole KHG, so a KHG that is mostly mineral soil is not diluted."))}</li></ul></section>`);
  S.push(`<section class="card" id="m-dims"><h2>${esc(t("Five dimensions"))}</h2>
    <p>${esc(t("Each indicator is turned into a percentile rank among the KHG (0.8 means higher than 80% of them). A dimension is the weighted mean of its indicators' ranks, from 0 to 1. Missing values are left out of the mean. Hover an indicator for what it measures and where it comes from."))}</p>
    <div class="dims">${DIMS.map(([k,l,key])=>`<div class="dim" style="--c:var(--dim-${k})"><div class="use">${esc(t(DIM_USE[k]))}</div><h3>${esc(t(l))}</h3><div class="q"><b>${esc(t(DIM_Q[k]))}</b> ${esc(t(DIM_TIP[k]))}</div>${weightsTable(key)}</div>`).join("")}
    <div class="dim" style="--c:var(--border)"><div class="use">${esc(t("Shown, not scored"))}</div><h3>${esc(t("Reported indicators"))}</h3>
      <ul>${RU.reported.map(k=>{const m=IND[k]||[k,""];return `<li${tipAttr(`<b>${esc(t(m[0]))}</b><br>${esc(t(m[1]))}`)}>${esc(t(m[0]))}</li>`}).join("")}</ul>
      <p class="small">${esc(t("BRGM canal blocks were built where fires were, so they echo urgency. Open and forest cover set the intervention, not the score."))}</p></div></div></section>`);
  S.push(`<section class="card" id="m-types"><h2>${esc(t("Types of action"))}</h2><div class="tgrid"><div>
    <p>${esc(t("Each dimension is split into thirds (terciles) across the KHG: low, medium, high. Three questions in order give the type:"))}</p>
    <div class="tree">
      <span class="q">1</span><span>${esc(t("Urgency high (above {b})? Then complexity decides: high complexity (above {c}) is B, otherwise A.",{b:cut("urgency",1),c:cut("complexity",1)}))}</span>
      <span class="q">2</span><span>${esc(t("Urgency medium ({a} to {b})? C.",{a:cut("urgency",0),b:cut("urgency",1)}))}</span>
      <span class="q">3</span><span>${esc(t("Urgency low (below {a})? Then stake decides: high stake (above {s}) is D, otherwise E.",{a:cut("urgency",0),s:cut("stake",1)}))}</span>
    </div>
    <p>${esc(t("Feasibility and people do not change the type. They add flags: low feasibility (bottom third, below {f}) means harder rewetting; high exposure (top third, above {p}) means more people affected by fire and haze.",{f:fx(D.fcut,2),p:fx(D.pcut,2)}))}</p>
    <p>${esc(t("Why urgency against complexity: urgency says when to act; among the urgent KHG, complexity says whether one agency can act (A) or several must coordinate (B). Among the low-urgency KHG, stake says whether to protect (D) or monitor (E)."))}</p></div>
    <table class="mt"><thead><tr><th>${esc(t("Type"))}</th><th class="n">${esc(t("KHG"))}</th><th class="n">${esc(t("in the 337"))}</th><th class="n">${esc(t("Peat km2"))}</th></tr></thead><tbody>${TYPE_ORDER.map(x=>{const r=ty[x]||{};
      return `<tr${tipAttr(`<b>${x} ${esc(t(TYPE_LABEL[x]))}</b><br>${esc(t(TYPE_NOTE[x]))}`)}><td><span class="tyb" style="--c:var(--ty${x})">${x}</span> ${esc(t(TYPE_LABEL[x]))}<div class="small">${esc(t(TYPE_RULE[x]))}</div></td><td class="n">${fmt(r.khg,0)}</td><td class="n">${fmt(r.in_337,0)}</td><td class="n">${fmt(r.peat_km2,0)}</td></tr>`}).join("")}</tbody></table></div></section>`);
  S.push(`<section class="card" id="m-iv"><h2>${esc(t("Intervention"))}</h2><div class="tgrid"><div>
    <p>${esc(t("Separate from the type, two shares of the KHG's peat say what the peat needs:"))}</p>
    <ul><li>${esc(t("Canal-affected: share of the peat inside KLH's canal-influence zones. At least {a}% means the peat is drained: rewetting (canal blocking).",{a}))}</li>
    <li>${esc(t("Open or degraded cover: share of the peat with shrub, open land, open swamp or savanna in KLH's land cover 2022. At least {b}% means revegetation. Plantations, crops and settlements are not counted as open.",{b}))}</li>
    <li>${esc(t("Both thresholds met: rewetting and revegetation. Neither: protect, the peat is largely intact."))}</li></ul>
    <p class="small">${esc(t("The {a}% thresholds were set before the result and are to be confirmed with KLH.",{a}))}</p></div>
    <table class="mt"><thead><tr><th>${esc(t("Intervention"))}</th><th class="n">${esc(t("KHG"))}</th><th class="n">${esc(t("in the 337"))}</th></tr></thead><tbody>${IV_ORDER.map(v=>{const r=ivn[v]||{};
      return `<tr${tipAttr(esc(t(IV_NOTE[v],{a,b})))}><td><span class="ivb" style="--c:${IV_COL[v]}">${esc(t(IV_SHORT[v]))}</span></td><td class="n">${fmt(r.khg,0)}</td><td class="n">${fmt(r.in_337,0)}</td></tr>`}).join("")}</tbody></table></div></section>`);
  S.push(`<section class="card" id="m-data"><h2>${esc(t("Data"))}</h2><table class="mt"><tbody>${SOURCES.map(([a,b])=>`<tr><td style="width:24%">${esc(t(a))}</td><td>${esc(t(b))}</td></tr>`).join("")}</tbody></table>
    <p class="small">${esc(t("Fire data to {d}. Prioritisation run {r}.",{d:D.period_now||"",r:D.run||""}))}</p></section>`);
  S.push(`<section class="card" id="m-limits"><h2>${esc(t("Limits"))}</h2><ul>
    <li>${esc(t("Weights are provisional, to be agreed with KLH. The KHG priority page shows how ranks and types move when they change."))}</li>
    <li>${esc(t("Scores are relative: a low urgency means lower than most other KHG, not no fire."))}</li>
    <li>${esc(t("Hotspots and burned area inside a licence or forest area are a spatial overlap; they do not show the cause of a fire or who is responsible."))}</li>
    <li>${esc(t("Land status categories overlap: licences lie inside forest estate, and DMPG villages cover both."))}</li>
    <li>${esc(t("Canal zones, damage and land cover come from KLH's PPEG analysis and have not been checked in the field by the project."))}</li></ul></section>`);
  S.push(`<section class="card"><h2>${esc(t("The pages"))}</h2><ul>
    <li><b>${esc(t("KHG priority"))}</b>: ${esc(t("the ranked list with live weights, a map and a profile of each KHG."))}</li>
    <li><b>${esc(t("KHG table"))}</b>: ${esc(t("every KHG with every field, to filter, sort and download."))}</li>
    <li><b>${esc(t("Fire by land status"))}</b>: ${esc(t("burned area and hotspots by concession, forest area and DMPG village, nationally and by province."))}</li></ul></section>`);
  const toc=[["m-unit","Unit of analysis"],["m-dims","Five dimensions"],["m-types","Types of action"],["m-iv","Intervention"],["m-data","Data"],["m-limits","Limits"]];
  $("#mp").innerHTML=`<div class="toc">${toc.map(([id,l])=>`<a href="#${id}" data-go="${id}">${esc(t(l))}</a>`).join("")}</div>`+S.join("");
  $$(".toc a").forEach(a=>a.onclick=e=>{e.preventDefault();document.getElementById(a.dataset.go).scrollIntoView({behavior:"smooth"})});
}
function update(){topBar("method.html",update);document.title=t("Method");
  $("#sub").textContent=t("How the KHG are scored, typed and given an intervention, in one page");
  render();const th=document.documentElement.dataset.theme;history.replaceState(null,"",`#l=${LANG}${th?"&t="+th:""}`);navHrefs()}
readLangTheme(new URLSearchParams(location.hash.slice(1)));update();
document.body.dataset.ready="1";
