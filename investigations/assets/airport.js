// Banjarbaru airport fire check: charts, map and tables from DATA (built by investigations/airport.py).
const ID={
"Syamsudin Noor airport and KHG Sungai Maluka - Sungai Martapura":"Bandara Syamsudin Noor dan KHG Sungai Maluka - Sungai Martapura",
"Theme":"Tema","Map":"Peta","Search":"Cari","Sources":"Sumber",
"Is this KHG Sungai Maluka - Sungai Martapura?":"Apakah ini KHG Sungai Maluka - Sungai Martapura?",
"Peat under the KHG, three sources":"Gambut di KHG, tiga sumber",
"Hotspots per year within 5 km of the runway":"Hotspot per tahun dalam 5 km dari landasan",
"Hotspots per year 5 to 10 km from the runway":"Hotspot per tahun 5 sampai 10 km dari landasan",
"Hotspot density by ground, within 10 km":"Kepadatan hotspot menurut lahan, dalam 10 km",
"Burned area per year inside the KHG":"Luas terbakar per tahun di dalam KHG",
"Smoke at the airport and fire nearby, per year":"Asap di bandara dan api di sekitarnya, per tahun",
"Fire season, daily":"Musim kebakaran, harian",
"Wind during smoke reports":"Angin saat laporan asap",
"Where the hotspots are, within 10 km":"Letak hotspot, dalam 10 km",
"Smoke reports by hour":"Laporan asap per jam",
"Smoke days and fire, per year":"Hari berasap dan api, per tahun",
"KHG peat soil":"Tanah gambut KHG","KHG mineral soil":"Tanah mineral KHG","Outside KHG":"Di luar KHG",
"Peat soil":"Tanah gambut","Mineral soil":"Tanah mineral",
"hotspots":"hotspot","hotspots per km² per year":"hotspot per km² per tahun","ha":"ha",
"Smoke days":"Hari berasap","Hotspots ≤ {r} km":"Hotspot ≤ {r} km","Hotspots {a} to {b} km":"Hotspot {a} sampai {b} km",
"Lowest visibility (km)":"Jarak pandang terendah (km)","Smoke reported":"Asap dilaporkan",
"KHG area":"Luas KHG","Runway inside the KHG":"Landasan di dalam KHG","Peat soil in the KHG":"Tanah gambut di KHG",
"Runway to nearest peat soil":"Landasan ke tanah gambut terdekat","Smoke days at the airport":"Hari berasap di bandara",
"Hotspots within 5 km":"Hotspot dalam 5 km",
"SK area {v} ha":"Luas SK {v} ha","of {v} km":"dari {v} km","{v} of the KHG; mineral {m} ha":"{v} dari KHG; mineral {m} ha",
"FEG 1:50,000 polygon edge":"Tepi poligon FEG 1:50.000","2026 to {d}; {y}: {n}":"2026 sampai {d}; {y}: {n}",
"VIIRS, n/h confidence":"VIIRS, kepercayaan n/h","nearest 2026 hotspot {d} km ({t})":"hotspot 2026 terdekat {d} km ({t})",
"Code in the KLHK FEG 1:50,000 layer":"Kode ada di lapisan FEG 1:50.000 KLHK",
"Area matches the SK":"Luas cocok dengan SK","BRGM structures named Maluka-Martapura fall inside":"Bangunan BRGM bernama Maluka-Martapura ada di dalamnya",
"Kabupaten in the code match the coverage":"Kabupaten dalam kode cocok dengan cakupan",
"Absent from the SK.129/2017 boundaries":"Tidak ada di batas SK.129/2017",
"Nearest SK.129 KHG: {n}, {d} km":"KHG SK.129 terdekat: {n}, {d} km",
"KLH 2026 hotspots inside, by kabupaten: {v}":"Hotspot KLH 2026 di dalamnya, per kabupaten: {v}",
"{n} polygons; legal basis lists SK.270/2022":"{n} poligon; dasar hukum mencantumkan SK.270/2022",
"computed {a} ha vs {b} ha in the SK ({d})":"hitungan {a} ha vs {b} ha di SK ({d})",
"{a} of {b}, desa {d}":"{a} dari {b}, desa {d}",
"KHG":"KHG","Within 5 km":"Dalam 5 km","Within 10 km":"Dalam 10 km","Within 20 km":"Dalam 20 km",
"FEG 50K peat soil":"Tanah gambut FEG 50K","GFW composite":"Komposit GFW","Global Peatland Map 1 km":"Global Peatland Map 1 km",
"share of area that is peat":"bagian luas yang gambut",
"KHG boundary":"Batas KHG","FEG peat soil":"Tanah gambut FEG","GFW peat":"Gambut GFW","Burned area":"Area terbakar",
"VIIRS hotspots":"Hotspot VIIRS","KLH 2026 hotspots":"Hotspot KLH 2026","Rings 5, 10, 20 km":"Cincin 5, 10, 20 km",
"BRGM structures":"Bangunan BRGM","Runway":"Landasan","Peat thickness (m)":"Ketebalan gambut (m)",
"Year":"Tahun","Reports":"Laporan","Days with reports":"Hari dengan laporan","Smoke with low visibility":"Asap dan jarak pandang rendah",
"Haze days":"Hari berkabut (HZ)","Fire ≤ {r} km same or previous day":"Api ≤ {r} km hari yang sama atau sebelumnya",
"Only fire {a} to {b} km":"Hanya api {a} sampai {b} km","No fire within {b} km":"Tanpa api dalam {b} km","No hotspot data yet":"Belum ada data hotspot",
"Dataset":"Data","Has this KHG":"Memuat KHG ini","Used for":"Dipakai untuk","Note":"Catatan","yes":"ya","no":"tidak","name only":"nama saja",
"Hotspots on the map":"Hotspot di peta","Burned in":"Terbakar tahun","all years":"semua tahun",
"wind from":"angin dari","calm: {n} reports":"tenang: {n} laporan","VIIRS 2012-2025":"VIIRS 2012-2025","KLH 2026":"KLH 2026",
"share of reports with smoke (%)":"bagian laporan dengan asap (%)","local time (WITA)":"waktu lokal (WITA)",
"days":"hari","Hotspots 2026 are KLH MODIS, not VIIRS: not on the same scale":"Hotspot 2026 dari KLH (MODIS), bukan VIIRS: skalanya tidak sama",
"VIIRS {a}; 2026 from KLH (MODIS)":"VIIRS {a}; 2026 dari KLH (MODIS)",
"Inside the KHG on peat soil":"Di dalam KHG, tanah gambut","Inside the KHG on mineral soil":"Di dalam KHG, tanah mineral","Outside the KHG within {r} km":"Di luar KHG dalam {r} km",
"Weather reports {a} to {b}, {n} reports; hotspots to {d}":"Laporan cuaca {a} sampai {b}, {n} laporan; hotspot sampai {d}",
"Inside KHG, peat":"Di dalam KHG, gambut","Inside KHG, not peat":"Di dalam KHG, bukan gambut","Peat map":"Peta gambut",
"FEG: not peat = Non Gambut (Mineral), thickness class 0-0.5 m":"FEG: bukan gambut = Non Gambut (Mineral), kelas ketebalan 0-0,5 m",
"GFW: peat = composite of Miettinen 2016 and Gumbricht 2017, about 76 m":"GFW: gambut = gabungan Miettinen 2016 dan Gumbricht 2017, sekitar 76 m",
"Peat in the KHG":"Gambut di KHG","Runway to nearest peat":"Landasan ke gambut terdekat","GFW {v} ha":"GFW {v} ha","GFW {v} km":"GFW {v} km",
"Smoke days at the airport, fixed hours":"Hari berasap di bandara, jam tetap",
"Reports per day":"Laporan per hari","Smoke days, fixed hours":"Hari berasap, jam tetap",
"Fire ≤ {r} km and {r} to {b} km":"Api ≤ {r} km dan {r} sampai {b} km","Only fire ≤ {r} km":"Hanya api ≤ {r} km",
"Smoke with fire ≤ {r} km upwind":"Asap dengan api ≤ {r} km arah angin datang","Smoke only in calm":"Asap hanya saat tenang",
"Kabupaten with hotspots inside lie in the SK.270 coverage":"Kabupaten dengan hotspot di dalamnya termasuk cakupan SK.270",
"FEG 1:50,000":"FEG 1:50.000","GFW composite, 76 m":"Komposit GFW, 76 m",
"same or previous day; fire ≤ {r} km within 45° of the wind direction":"hari yang sama atau sebelumnya; api ≤ {r} km dalam 45° dari arah angin",
"UTC hours {h}, first report of each hour":"jam UTC {h}, laporan pertama tiap jam",
};
let LANG="en";
const T=(s,v)=>{let o=LANG==="id"&&ID[s]?ID[s]:s;if(v)for(const k in v)o=o.replaceAll("{"+k+"}",v[k]);return o};
const css=n=>getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const nf=(x,d=0)=>x==null||isNaN(x)?"–":new Intl.NumberFormat(LANG==="id"?"id-ID":"en-US",{maximumFractionDigits:d,minimumFractionDigits:d}).format(x);
const pct=(x,d=0)=>x==null||isNaN(x)?"–":nf(100*x,d)+"%";
const F=DATA.facts,H=DATA.hot,M=DATA.metar,C=DATA.cfg,RK=C.rings_km,FAR=RK[RK.length-1];
const ZONES=["peat","mineral","outside"],ZV={peat:"--c-peat",mineral:"--c-min",outside:"--c-out"};
let PEAT="feg";
const ZN=z=>T({peat:"Inside KHG, peat",mineral:"Inside KHG, not peat",outside:"Outside KHG"}[z]);
const peatNote=()=>PEAT==="feg"?T("FEG: not peat = Non Gambut (Mineral), thickness class 0-0.5 m"):T("GFW: peat = composite of Miettinen 2016 and Gumbricht 2017, about 76 m");
const SECT=["N","NE","E","SE","S","SW","W","NW"];
const tip=document.getElementById("tip");
function showTip(e,h){tip.innerHTML=h;tip.style.display="block";const w=tip.offsetWidth,hh=tip.offsetHeight;
  tip.style.left=Math.min(e.clientX+14,innerWidth-w-8)+"px";tip.style.top=(e.clientY+hh+20>innerHeight?e.clientY-hh-10:e.clientY+14)+"px"}
function hideTip(){tip.style.display="none"}
document.addEventListener("mouseover",e=>{const t=e.target.closest("[data-tip]");if(t)showTip(e,t.dataset.tip)});
document.addEventListener("mousemove",e=>{const t=e.target.closest("[data-tip]");if(t)showTip(e,t.dataset.tip)});
document.addEventListener("mouseout",e=>{if(e.target.closest("[data-tip]"))hideTip()});
const esc=s=>String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));

// ---------- text ----------
function texts(){
  document.querySelectorAll("[data-t]").forEach(e=>e.textContent=T(e.dataset.t));
  document.querySelectorAll("[data-tp]").forEach(e=>e.placeholder=T(e.dataset.tp));
  document.documentElement.lang=LANG;
  document.getElementById("sub").textContent=`${C.khg.code} · ${C.khg.sk} · ${C.airport.icao}`;
  document.getElementById("foot").textContent=T("Weather reports {a} to {b}, {n} reports; hotspots to {d}",{a:M.first,b:M.last,n:nf(M.n),d:H.now_last})+
    ". "+T("Hotspots 2026 are KLH MODIS, not VIIRS: not on the same scale")+".";
}

// ---------- KPIs ----------
function kpis(){
  const y=C.event_years,yr=Object.fromEntries(M.years.map(r=>[r.year,r]));
  const v5=Object.fromEntries(H.viirs_year.map(r=>[r.year,ZONES.reduce((s,z)=>s+r[`0-${RK[0]}|${z}`],0)]));
  const peak=y.filter(a=>v5[a]!=null).sort((a,b)=>v5[b]-v5[a])[0];
  const k=[
    [T("KHG area"),nf(F.khg_ha)+"<small>ha</small>",T("SK area {v} ha",{v:nf(F.khg_ha_sk,2)}),"KLHK FEG 1:50,000 (BIG Satu Peta mirror), area in UTM 50S. "+C.khg.sk],
    [T("Runway inside the KHG"),nf(F.runway_in_khg_m/1000,2)+"<small>km</small>",T("of {v} km",{v:nf(F.runway_m/1000,2)}),"Runway 10/28 from threshold coordinates: "+C.airport.runway_source],
    [T("Peat in the KHG"),nf(F.feg_peat_ha)+"<small>ha FEG</small>",T("GFW {v} ha",{v:nf(F.gfw_peat_ha_khg)})+" · GPM "+pct(F.gpm_share_khg),"FEG 1:50,000: tnh_gambut = Tanah Gambut (the rest is Non Gambut (Mineral), thickness class 0-0.5 m). GFW composite peat extent (Miettinen 2016 and Gumbricht 2017), about 76 m. Global Peatland Map 2.0, 1 km: share of cells"],
    [T("Runway to nearest peat"),nf(F.runway_to_peat_km,1)+"<small>km FEG</small>",T("GFW {v} km",{v:nf(F.runway_to_gfw_km,1)}),"Shortest distance from the runway line to a FEG peat-soil polygon, and to the centre of a GFW peat cell"],
    [T("Smoke days at the airport, fixed hours"),nf(yr[2026]?.smoke_days_fixed)+"<small>2026</small>",y.filter(a=>a!==2026).map(a=>a+": "+nf(yr[a]?.smoke_days_fixed)).join(" · "),"METAR "+C.airport.icao+" (Iowa Environmental Mesonet): local days with smoke (FU), counted on the UTC hours "+M.fixed_hours_utc.join(", ")+" only, first report of each hour, so that years with more reports per day are not favoured. 2026 to "+M.last],
    [T("Hotspots within 5 km"),nf(v5[peak])+"<small>"+peak+"</small>",T("nearest 2026 hotspot {d} km ({t})",{d:nf(H.nearest_now.d_km,1),t:H.nearest_now.day}),"FIRMS VIIRS S-NPP, confidence n/h, type 0, distance to the runway line; 2026: KLH hotspots, medium and high"]];
  document.getElementById("kpis").innerHTML=k.map(a=>`<div class="card kpi" data-tip="${esc(a[3])}"><div class="v">${a[1]}</div><div class="l">${a[0]}</div><div class="s">${a[2]}</div></div>`).join("");
}

// ---------- identity checks ----------
function checks(){
  const d=(F.khg_ha-F.khg_ha_sk)/F.khg_ha_sk;
  const kab=Object.entries(F.kab_in_khg).map(([a,b])=>a+" "+b).join(", ");
  const rows=[
    [true,T("Code in the KLHK FEG 1:50,000 layer"),T("{n} polygons; legal basis lists SK.270/2022",{n:F.feg_n})],
    [Math.abs(d)<.01,T("Area matches the SK"),T("computed {a} ha vs {b} ha in the SK ({d})",{a:nf(F.khg_ha),b:nf(F.khg_ha_sk,2),d:(d>0?"+":"")+nf(100*d,2)+"%"})],
    [F.brgm_named_inside===F.brgm_named&&F.brgm_named>0,T("BRGM structures named Maluka-Martapura fall inside"),T("{a} of {b}, desa {d}",{a:F.brgm_named_inside,b:F.brgm_named,d:F.brgm_named_desa.join(", ")})+" · "+F.brgm_named_detail.join(", ")],
    [F.kab_ok,T("Kabupaten with hotspots inside lie in the SK.270 coverage"),T("KLH 2026 hotspots inside, by kabupaten: {v}",{v:kab})],
    [false,T("Absent from the SK.129/2017 boundaries"),F.old_nearest?T("Nearest SK.129 KHG: {n}, {d} km",{n:F.old_nearest.name,d:nf(F.old_nearest.d_km,1)}):""]];
  document.getElementById("checks").innerHTML=rows.map(r=>`<li><span class="${r[0]?"ok":"no"}">${r[0]?"✓":"✗"}</span><div>${esc(r[1])}<small>${esc(r[2])}</small></div></li>`).join("");
}

// ---------- peat sources (dot plot) ----------
function peatbars(){
  const el=document.getElementById("peatbars");el.innerHTML="";
  const rows=[[T("KHG"),F.feg_peat_ha/F.khg_ha,F.gfw_share_khg,F.gpm_share_khg],
    ...F.rings.map(r=>[T("Within "+r.km+" km"),r.feg_peat_ha/r.area_ha,r.gfw_share,r.gpm_share])];
  const S=[[T("FEG 50K peat soil"),"--ink"],[T("GFW composite"),"--c-min"],[T("Global Peatland Map 1 km"),"--c-out"]];
  const W=el.clientWidth||360,m={l:84,r:14,t:6,b:26},rh=30,h=m.t+m.b+rows.length*rh;
  const x=d3.scaleLinear([0,1],[m.l,W-m.r]);
  const svg=d3.select(el).append("svg").attr("width",W).attr("height",h);
  svg.append("g").attr("class","axis").attr("transform",`translate(0,${h-m.b})`).call(d3.axisBottom(x).ticks(5).tickFormat(d3.format(".0%")));
  svg.append("g").attr("class","gridl").attr("transform",`translate(0,${h-m.b})`).call(d3.axisBottom(x).ticks(5).tickSize(-(h-m.t-m.b)).tickFormat(""));
  rows.forEach((r,i)=>{const y=m.t+i*rh+rh/2;
    svg.append("text").attr("class","lab").attr("x",0).attr("y",y+4).text(r[0]);
    svg.append("line").attr("x1",x(d3.min(r.slice(1)))).attr("x2",x(d3.max(r.slice(1)))).attr("y1",y).attr("y2",y).attr("stroke",css("--axis"));
    S.forEach((s,j)=>svg.append("circle").attr("cx",x(r[j+1])).attr("cy",y).attr("r",5.5).attr("fill",css(s[1])).attr("stroke",css("--surface"))
      .attr("data-tip",`${esc(r[0])}<br><span>${esc(s[0])}</span> <b>${pct(r[j+1],1)}</b>`))});
  d3.select(el).append("div").attr("class","legend").html(S.map(s=>`<span><i class="sw dot" style="background:${css(s[1])}"></i>${s[0]}</span>`).join("")+
    `<span style="color:${css("--muted")}">${T("share of area that is peat")}</span>`);
}

// ---------- line chart ----------
function lineChart(el,series,o){
  el=typeof el==="string"?document.getElementById(el):el;el.innerHTML="";
  const W=el.clientWidth||520,h=o.h||230,m={l:48,r:o.endLab?118:14,t:10,b:28};
  const xs=series.flatMap(s=>s.v.map(d=>d[0])),ys=series.flatMap(s=>s.v.map(d=>d[1])).filter(v=>v!=null);
  const x=(o.time?d3.scaleTime():d3.scaleLinear()).domain(o.xd||d3.extent(xs)).range([m.l,W-m.r]);
  const y=d3.scaleLinear([0,o.ymax||d3.max(ys)||1],[h-m.b,m.t]).nice();
  const svg=d3.select(el).append("svg").attr("width",W).attr("height",h);
  svg.append("g").attr("class","gridl").attr("transform",`translate(${m.l},0)`).call(d3.axisLeft(y).ticks(4).tickSize(-(W-m.l-m.r)).tickFormat(""));
  svg.append("g").attr("class","axis").attr("transform",`translate(0,${h-m.b})`).call(o.time?d3.axisBottom(x).ticks(6).tickFormat(d3.timeFormat("%b")):d3.axisBottom(x).ticks(Math.min(xs.length,8)).tickFormat(d3.format("d")));
  svg.append("g").attr("class","axis").attr("transform",`translate(${m.l},0)`).call(d3.axisLeft(y).ticks(4).tickFormat(v=>nf(v)));
  if(o.yl)svg.append("text").attr("class","lab").attr("x",m.l).attr("y",m.t-1).attr("dy","-0.1em").text("");
  const line=d3.line().defined(d=>d[1]!=null).x(d=>x(d[0])).y(d=>y(d[1]));
  series.forEach(s=>{svg.append("path").attr("d",line(s.v)).attr("fill","none").attr("stroke",css(s.c)).attr("stroke-width",s.w||2).attr("stroke-dasharray",s.dash||null);
    if(s.dots)svg.append("g").selectAll("circle").data(s.v.filter(s.dots)).join("circle").attr("cx",d=>x(d[0])).attr("cy",d=>y(d[1])).attr("r",3).attr("fill",css(s.dc||s.c));
    if(o.endLab){const l=[...s.v].reverse().find(d=>d[1]!=null);if(l)svg.append("text").attr("class","end").attr("x",x(l[0])+6).attr("y",y(l[1])+4).attr("fill",css(s.c)).text(s.n)}});
  // hover
  const xv=[...new Set(xs.map(v=>+v))].sort((a,b)=>a-b);
  const g=svg.append("line").attr("stroke",css("--axis")).attr("y1",m.t).attr("y2",h-m.b).style("display","none");
  svg.append("rect").attr("x",m.l).attr("y",m.t).attr("width",W-m.l-m.r).attr("height",h-m.t-m.b).attr("fill","transparent")
    .on("mousemove",e=>{const px=d3.pointer(e)[0],xi=x.invert(px),k=xv[d3.minIndex(xv,v=>Math.abs(v-xi))];g.style("display",null).attr("x1",x(k)).attr("x2",x(k));
      const lab=o.time?d3.timeFormat("%d %b %Y")(new Date(k)):k;
      showTip(e,`<b>${lab}</b>`+series.map(s=>{const d=s.v.find(d=>+d[0]===k);return `<br><span style="color:${css(s.c)}">●</span> ${esc(s.n)} <b>${d&&d[1]!=null?nf(d[1],o.dec||0):"–"}</b>`}).join("")+(o.extra?o.extra(k):""))})
    .on("mouseleave",()=>{g.style("display","none");hideTip()});
  if(o.unit)d3.select(el).append("div").attr("class","legend").html(`<span style="color:${css("--muted")}">${esc(o.unit)}</span>`);
}
const zoneLegend=()=>document.querySelectorAll(".zl").forEach(e=>e.innerHTML=ZONES.map(z=>`<span><i class="sw" style="background:${css(ZV[z])}"></i>${ZN(z)}</span>`).join(""));

function hotspotCharts(){
  const rings=[`0-${RK[0]}`,`${RK[0]}-${RK[1]}`],VY=PEAT==="feg"?H.viirs_year:H.viirs_year_gfw;
  ["hs5","hs10"].forEach((id,i)=>lineChart(id,ZONES.map(z=>({n:ZN(z),c:ZV[z],v:VY.map(r=>[r.year,r[rings[i]+"|"+z]])})),{unit:T("VIIRS, n/h confidence")+" · "+peatNote()}));
  // density within 10 km, per km2 of each ground
  const r10=F.rings[1],area=PEAT==="feg"?{peat:r10.feg_peat_ha/100,mineral:r10.khg_mineral_ha/100,outside:r10.outside_ha/100}:{peat:r10.gfw_peat_ha/100,mineral:r10.gfw_nonpeat_ha/100,outside:r10.outside_ha/100};
  lineChart("dens",ZONES.map(z=>({n:ZN(z),c:ZV[z],v:VY.map(r=>[r.year,(r[rings[0]+"|"+z]+r[rings[1]+"|"+z])/area[z]])})),
    {dec:2,unit:T("hotspots per km² per year")+` · ${ZN("peat")} ${nf(area.peat,1)} km², ${ZN("mineral")} ${nf(area.mineral,1)} km², ${ZN("outside")} ${nf(area.outside,1)} km²`});
  document.getElementById("bl").innerHTML=[["--c-peat",ZN("peat")],["--c-min",ZN("mineral")],["--c-out",T("Outside the KHG within {r} km",{r:FAR})]]
    .map(a=>`<span><i class="sw" style="background:${css(a[0])}"></i>${a[1]}</span>`).join("");
  const pk=PEAT==="feg"?["khg_peat","khg_mineral"]:["khg_gfw_peat","khg_gfw_nonpeat"];
  lineChart("burn",[{n:ZN("peat"),c:"--c-peat",v:DATA.burned.map(r=>[r.year,r[pk[0]]])},{n:ZN("mineral"),c:"--c-min",v:DATA.burned.map(r=>[r.year,r[pk[1]]])},
    {n:ZN("outside"),c:"--c-out",v:DATA.burned.map(r=>[r.year,r.outside_khg_r])}],{unit:"ha · burnt_area_2015_2026_Indonesia (BA_yyyy) · "+peatNote()});
}

function smokeCharts(){
  const Y=M.years;
  document.getElementById("sl").innerHTML=[["--vis",T("Smoke days")],["--c-peat",T("Hotspots ≤ {r} km",{r:FAR})],["--c-reg",T("Hotspots {a} to {b} km",{a:FAR,b:C.regional_km})]]
    .map(a=>`<span><i class="sw" style="background:${css(a[0])}"></i>${a[1]}</span>`).join("");
  const el=document.getElementById("smokeyr");el.innerHTML="";
  const p=[document.createElement("div"),document.createElement("div"),document.createElement("div")];p.forEach(d=>el.appendChild(d));
  const hv=Y.filter(r=>r.year<2026);
  lineChart(p[0],[{n:T("Smoke days, fixed hours"),c:"--vis",v:Y.map(r=>[r.year,r.smoke_days_fixed])}],{h:130,unit:T("Smoke days, fixed hours")+" (METAR FU) · "+T("UTC hours {h}, first report of each hour",{h:M.fixed_hours_utc.join(", ")}),
    extra:k=>{const r=Y.find(r=>r.year===k);return r?`<br><span>${T("Smoke days")}</span> ${r.smoke_days}<br><span>${T("Reports per day")}</span> ${nf(M.reports_per_day[k],1)}<br><span>${T("Days with reports")}</span> ${r.days}`:""}});
  lineChart(p[1],[{n:T("Hotspots ≤ {r} km",{r:FAR}),c:"--c-peat",v:hv.map(r=>[r.year,r.hs_near])}],{h:120,xd:d3.extent(Y,r=>r.year),unit:T("Hotspots ≤ {r} km",{r:FAR})+" · "+T("VIIRS 2012-2025")});
  lineChart(p[2],[{n:T("Hotspots {a} to {b} km",{a:FAR,b:C.regional_km}),c:"--c-reg",v:hv.map(r=>[r.year,r.hs_reg])}],{h:120,xd:d3.extent(Y,r=>r.year),unit:T("Hotspots {a} to {b} km",{a:FAR,b:C.regional_km})+" · "+T("VIIRS 2012-2025")});
}

function eventChart(){
  const y=document.getElementById("evyear").value,ev=DATA.metar.events[y]||[];
  document.getElementById("el").innerHTML=[["--vis",T("Lowest visibility (km)")],["--c-peat",T("Smoke reported")],["--c-peat",T("Hotspots ≤ {r} km",{r:FAR})],["--c-reg",T("Hotspots {a} to {b} km",{a:FAR,b:C.regional_km})]]
    .map((a,i)=>`<span><i class="sw ${i===1?"dot":""}" style="background:${css(a[0])}"></i>${a[1]}</span>`).join("");
  const el=document.getElementById("event");el.innerHTML="";
  const a=document.createElement("div"),b=document.createElement("div"),c=document.createElement("div");el.append(a,b,c);
  const t=ev.map(d=>[new Date(d[0]),d]);const xd=d3.extent(t,d=>d[0]);
  lineChart(a,[{n:T("Lowest visibility (km)"),c:"--vis",w:1.5,v:t.map(d=>[d[0],d[1][1]]),dots:d=>t.find(q=>+q[0]===+d[0])[1][2]>0,dc:"--c-peat"}],
    {time:true,h:150,dec:1,xd,unit:T("Lowest visibility (km)")+" · METAR "+C.airport.icao,extra:k=>{const d=t.find(q=>+q[0]===k);return d?`<br><span>${T("Smoke reported")}</span> ${d[1][2]} ${T("Reports").toLowerCase()}`:""}});
  const src=+y===2026?T("KLH 2026"):"VIIRS";
  lineChart(b,[{n:T("Hotspots ≤ {r} km",{r:FAR}),c:"--c-peat",w:1.5,v:t.map(d=>[d[0],d[1][3]])}],{time:true,h:110,xd,unit:T("Hotspots ≤ {r} km",{r:FAR})+" · "+src});
  lineChart(c,[{n:T("Hotspots {a} to {b} km",{a:FAR,b:C.regional_km}),c:"--c-reg",w:1.5,v:t.map(d=>[d[0],d[1][4]])}],{time:true,h:110,xd,unit:T("Hotspots {a} to {b} km",{a:FAR,b:C.regional_km})+" · "+src});
}

function rose(id,sets,note){
  const el=document.getElementById(id);el.innerHTML="";
  const W=Math.min(el.clientWidth||300,320),R=W/2-26,svg=d3.select(el).append("svg").attr("width",W).attr("height",W+4);
  const g=svg.append("g").attr("transform",`translate(${W/2},${W/2})`);
  const mx=d3.max(sets.flatMap(s=>{const t=d3.sum(s.v);return s.v.map(v=>v/t)}));
  const r=d3.scaleSqrt([0,mx],[0,R]);
  [.25,.5,.75,1].forEach(f=>g.append("circle").attr("r",r(mx*f)).attr("fill","none").attr("stroke",css("--grid")));
  SECT.forEach((s,i)=>{const a=i*Math.PI/4;g.append("text").attr("class","lab").attr("x",(R+14)*Math.sin(a)).attr("y",-(R+14)*Math.cos(a)+4).attr("text-anchor","middle").text(s)});
  const arc=d3.arc().innerRadius(0);
  sets.forEach(s=>{const t=d3.sum(s.v);s.v.forEach((v,i)=>{const a0=(i-.5)*Math.PI/4+.04,a1=(i+.5)*Math.PI/4-.04;
    g.append("path").attr("d",arc({outerRadius:r(v/t),startAngle:a0,endAngle:a1})).attr("fill",s.fill?css(s.c):"none").attr("fill-opacity",s.fill?.8:0)
      .attr("stroke",css(s.c)).attr("stroke-width",s.fill?0:2).attr("data-tip",`${esc(s.n)} · ${SECT[i]}<br><b>${pct(v/t)}</b> (${nf(v)})`)})});
  d3.select(el).append("div").attr("class","legend").html(sets.map(s=>`<span><i class="sw" style="${s.fill?"background:"+css(s.c):"border:2px solid "+css(s.c)}"></i>${esc(s.n)}</span>`).join("")+(note?`<span style="color:${css("--muted")}">${esc(note)}</span>`:""));
}
function roses(){
  rose("rose1",[{n:T("wind from")+" (METAR FU)",c:"--vis",fill:true,v:M.wind_smoke}],T("calm: {n} reports",{n:nf(M.calm_smoke)}));
  rose("rose2",[{n:T("VIIRS 2012-2025"),c:"--c-min",fill:true,v:H.sector_viirs},{n:T("KLH 2026"),c:"--c-peat",fill:false,v:H.sector_now}],"");
  lineChart("hour",[{n:T("Smoke reported"),c:"--vis",v:M.smoke_hour.map((v,i)=>[i,M.obs_hour[i]?100*v/M.obs_hour[i]:null])}],{dec:1,unit:T("share of reports with smoke (%)")+" · "+T("local time (WITA)")});
}

// ---------- tables ----------
let sortCol="year",sortDir=-1;
function table(){
  const cols=[["year",T("Year")],["rpd",T("Reports per day")],["days",T("Days with reports")],["smoke_days",T("Smoke days")],["smoke_days_fixed",T("Smoke days, fixed hours")],
    ["low_smoke_days",T("Smoke with low visibility")+` <small>&lt; ${C.low_vis_km} km</small>`],["haze_days",T("Haze days")],
    ["src_both",T("Fire ≤ {r} km and {r} to {b} km",{r:FAR,b:C.regional_km})],["src_near",T("Only fire ≤ {r} km",{r:FAR})],["src_regional",T("Only fire {a} to {b} km",{a:FAR,b:C.regional_km})],
    ["src_none",T("No fire within {b} km",{b:C.regional_km})],["src_nodata",T("No hotspot data yet")],
    ["smoke_upwind",T("Smoke with fire ≤ {r} km upwind",{r:FAR})],["smoke_calm_only",T("Smoke only in calm")],
    ["hs_near",T("Hotspots ≤ {r} km",{r:FAR})],["hs_reg",T("Hotspots {a} to {b} km",{a:FAR,b:C.regional_km})]];
  M.years.forEach(r=>r.rpd=M.reports_per_day[r.year]);
  const q=document.getElementById("q").value.trim();
  const rows=M.years.filter(r=>!q||String(r.year).includes(q)).sort((a,b)=>sortDir*(a[sortCol]-b[sortCol]));
  const tab=document.getElementById("tab");
  tab.innerHTML=`<thead><tr>${cols.map(c=>`<th data-c="${c[0]}">${c[1]}${sortCol===c[0]?(sortDir>0?" ▲":" ▼"):""}</th>`).join("")}</tr></thead><tbody>`+
    rows.map(r=>`<tr>${cols.map(c=>`<td>${c[0]==="year"?r.year+(r.year===2026?" *":""):nf(r[c[0]],c[0]==="rpd"?1:0)}</td>`).join("")}</tr>`).join("")+"</tbody>";
  document.getElementById("tabnote").textContent=T("same or previous day; fire ≤ {r} km within 45° of the wind direction",{r:FAR})+" · * "+T("Hotspots 2026 are KLH MODIS, not VIIRS: not on the same scale");
  tab.querySelectorAll("th").forEach(th=>th.onclick=()=>{const c=th.dataset.c;sortDir=sortCol===c?-sortDir:-1;sortCol=c;table()});
}
function sources(){
  const yes=T("yes"),no=T("no");
  const rows=[
    ["batas_khg_indonesia.gpkg (SK.129/2017)",no,"—",F.old_nearest?F.old_nearest.name+", "+nf(F.old_nearest.d_km,1)+" km":""],
    ["FEG__Indonesia__2017__Rev_Tipologi.gpkg",no,"—","FEG 2017; nearest polygon "+nf(F.feg2017_nearest_km,1)+" km"],
    ["klhk_khg_feg_50k.gpkg (KLHK via BIG Satu Peta)",yes,"KHG boundary, peat soil, thickness","FEG 1:50,000; SK.270/2022 in the legal basis"],
    ["infrastruktur_hidrologis_existing_BRGM_Indonesia.gpkg",T("name only"),"Identity check",F.brgm_named+" × "+F.brgm_named_detail.join(", ")+", "+F.brgm_named_desa.join(", ")],
    ["peat_extent_gfw_v20230315_z11.tif",yes,"Peat cross-check","GFW composite (Miettinen 2016 ∪ Gumbricht 2017)"],
    ["peat_extent_gpm2022_1km.tif",yes,"Peat cross-check","Global Peatland Map 2.0, 1 km, CC BY-NC-SA"],
    ["hotspot_viirs_snpp_2012_2025.gpkg",yes,"Hotspots 2012-2025","FIRMS VIIRS S-NPP, n/h, type 0"],
    ["_data_hotspot_Januari_September_2026.gpkg",yes,"Hotspots 2026","KLH, MODIS, medium/high, to "+H.now_last],
    ["burnt_area_2015_2026_Indonesia.gpkg",yes,"Burned area",""],
    [F.metar_file,yes,"Visibility, smoke, wind","Iowa Environmental Mesonet ASOS/METAR archive"],
    ["Airport runway",yes,"Runway line",C.airport.runway_source]];
  document.getElementById("src").innerHTML=`<thead><tr><th>${T("Dataset")}</th><th>${T("Has this KHG")}</th><th>${T("Used for")}</th><th>${T("Note")}</th></tr></thead><tbody>`+
    rows.map(r=>`<tr>${r.map(c=>`<td style="text-align:left">${esc(c)}</td>`).join("")}</tr>`).join("")+"</tbody>";
}

// ---------- map ----------
let map,mapReady=false;
const L=DATA.layers;
const pts=(rows,key)=>({type:"FeatureCollection",features:rows.map(r=>({type:"Feature",geometry:{type:"Point",coordinates:[r[0],r[1]]},properties:{[key]:r[2],z:ZONES[PEAT==="feg"?r[3]:r[5]],d:r[4]}}))});
const THICK=["0,5 - 1,0 meter","1,0 - 1,5 meter","1,5 - 2,0 meter","2,0 - 2,5 meter","2,5 - 3,0 meter","3,0 - 3,5 meter"];
const TOG=[["khg","KHG boundary",true],["feg","FEG peat soil",true],["gfw","GFW peat",false],["burned","Burned area",true],["viirs","VIIRS hotspots",true],["now","KLH 2026 hotspots",false],["rings","Rings 5, 10, 20 km",true],["brgm","BRGM structures",true]];
const LAYERS={khg:["khg-line"],feg:["feg-fill"],gfw:["gfw"],burned:["burned"],viirs:["viirs"],now:["now"],rings:["rings","rings-lab"],brgm:["brgm"]};
const vis={};TOG.forEach(t=>vis[t[0]]=t[2]);
let viirsYear="2023",burnYear="2023";
function toggles(){
  const years=[...new Set(L.viirs.map(r=>r[2]))].sort();
  const by=[...new Set(L.burned.features.map(f=>f.properties.year))].sort();
  document.getElementById("toggles").innerHTML=TOG.map(t=>`<label class="tg"><input type="checkbox" data-k="${t[0]}" ${vis[t[0]]?"checked":""}>${T(t[1])}</label>`).join("")+
    ` <label class="tg">${T("Hotspots on the map")} <select id="vy"><option value="all">${T("all years")}</option>${years.map(y=>`<option ${String(y)===viirsYear?"selected":""}>${y}</option>`).join("")}</select></label>`+
    ` <label class="tg">${T("Burned in")} <select id="by"><option value="all">${T("all years")}</option>${by.map(y=>`<option ${String(y)===burnYear?"selected":""}>${y}</option>`).join("")}</select></label>`;
  document.querySelectorAll("#toggles input").forEach(i=>i.onchange=()=>{vis[i.dataset.k]=i.checked;applyVis()});
  document.getElementById("vy").onchange=e=>{viirsYear=e.target.value;applyFilters()};
  document.getElementById("by").onchange=e=>{burnYear=e.target.value;applyFilters()};
  document.getElementById("maplegend").innerHTML=
    `<span><i class="sw" style="border:2px solid ${css("--khg")}"></i>${T("KHG boundary")}</span>`+
    (PEAT==="feg"?`<span>${T("Peat thickness (m)")}: `+THICK.map((t,i)=>`<i class="sw" style="background:${d3.interpolateRgb(css("--ramp0"),css("--ramp1"))(i/(THICK.length-1))}" data-tip="${t}"></i>`).join("")+` 0.5 → 3.5</span>`
      :`<span><i class="sw" style="background:rgb(165,134,96);opacity:.6"></i>${T("GFW peat")}</span>`)+
    `<span><i class="sw" style="background:${css("--burn")};opacity:.45"></i>${T("Burned area")}</span>`+
    ZONES.map(z=>`<span><i class="sw dot" style="background:${css(ZV[z])}"></i>${ZN(z)}</span>`).join("")+
    `<span><i class="sw" style="background:${css("--ink")};height:3px;width:14px"></i>${T("Runway")}</span>`;
}
function applyVis(){if(!mapReady)return;for(const k in LAYERS)LAYERS[k].forEach(l=>map.getLayer(l)&&map.setLayoutProperty(l,"visibility",vis[k]?"visible":"none"))}
function applyFilters(){if(!mapReady)return;
  map.setFilter("viirs",viirsYear==="all"?null:["==",["get","y"],+viirsYear]);
  map.setFilter("burned",burnYear==="all"?null:["==",["get","year"],+burnYear])}
function paint(){if(!mapReady)return;
  map.getSource("viirs").setData(pts(L.viirs,"y"));map.getSource("now").setData(pts(L.now,"m"));
  const ramp=["match",["get","thick"],...THICK.flatMap((t,i)=>[t,d3.interpolateRgb(css("--ramp0"),css("--ramp1"))(i/(THICK.length-1))]),"rgba(0,0,0,0)"];
  map.setPaintProperty("feg-fill","fill-color",ramp);
  map.setPaintProperty("khg-line","line-color",css("--khg"));
  map.setPaintProperty("burned","fill-color",css("--burn"));
  const zc=["match",["get","z"],"peat",css("--c-peat"),"mineral",css("--c-min"),css("--c-out")];
  ["viirs","now"].forEach(l=>{map.setPaintProperty(l,"circle-color",zc);map.setPaintProperty(l,"circle-stroke-color",css("--surface"))});
  map.setPaintProperty("runway","line-color",css("--ink"));
  map.setPaintProperty("rings","line-color",css("--ink2"));
  map.setPaintProperty("rings-lab","text-color",css("--ink2"));
  map.setPaintProperty("brgm","circle-color",css("--ink"));
}
function initMap(){
  const e=C.extent;
  map=new maplibregl.Map({container:"map",style:DATA.style,bounds:[[e[0],e[1]],[e[2],e[3]]],fitBoundsOptions:{padding:10},attributionControl:{compact:true},cooperativeGestures:false});
  map.addControl(new maplibregl.NavigationControl({showCompass:false}),"top-right");
  map.addControl(new maplibregl.ScaleControl({unit:"metric"}),"bottom-left");
  map.on("load",()=>{
    map.addSource("gfw",{type:"image",url:DATA.gfw_png.url,coordinates:DATA.gfw_png.coords});
    map.addLayer({id:"gfw",type:"raster",source:"gfw",paint:{"raster-opacity":.45,"raster-resampling":"nearest"}});
    map.addSource("feg",{type:"geojson",data:{...L.feg,features:L.feg.features.filter(f=>f.properties.peat)}});
    map.addLayer({id:"feg-fill",type:"fill",source:"feg",paint:{"fill-opacity":.75}});
    map.addSource("burned",{type:"geojson",data:L.burned});
    map.addLayer({id:"burned",type:"fill",source:"burned",paint:{"fill-opacity":.35}});
    map.addSource("khg",{type:"geojson",data:L.khg});
    map.addLayer({id:"khg-line",type:"line",source:"khg",paint:{"line-width":2}});
    map.addSource("rings",{type:"geojson",data:L.rings});
    map.addLayer({id:"rings",type:"line",source:"rings",paint:{"line-width":1,"line-dasharray":[3,3]}});
    map.addLayer({id:"rings-lab",type:"symbol",source:"rings",layout:{"symbol-placement":"line","text-field":["concat",["to-string",["get","km"]]," km"],"text-size":11,"text-font":["Noto Sans Regular"]},paint:{"text-halo-color":css("--surface"),"text-halo-width":1.5}});
    map.addSource("viirs",{type:"geojson",data:pts(L.viirs,"y")});
    map.addLayer({id:"viirs",type:"circle",source:"viirs",paint:{"circle-radius":["interpolate",["linear"],["zoom"],9,2,13,4.5],"circle-stroke-width":.5,"circle-opacity":.85}});
    map.addSource("now",{type:"geojson",data:pts(L.now,"m")});
    map.addLayer({id:"now",type:"circle",source:"now",paint:{"circle-radius":["interpolate",["linear"],["zoom"],9,2.5,13,5],"circle-stroke-width":1}});
    map.addSource("runway",{type:"geojson",data:L.runway});
    map.addLayer({id:"runway",type:"line",source:"runway",paint:{"line-width":5}});
    map.addSource("brgm",{type:"geojson",data:L.brgm});
    map.addLayer({id:"brgm",type:"circle",source:"brgm",paint:{"circle-radius":5,"circle-stroke-width":2,"circle-stroke-color":"#fff"}});
    mapReady=true;paint();applyVis();applyFilters();
    const hov=["viirs","now","brgm","feg-fill","burned","runway"];
    map.on("mousemove",ev=>{const f=map.queryRenderedFeatures(ev.point,{layers:hov.filter(l=>map.getLayoutProperty(l,"visibility")!=="none")})[0];
      map.getCanvas().style.cursor=f?"pointer":"";if(!f)return hideTip();const p=f.properties,id=f.layer.id;let h="";
      if(id==="viirs")h=`<b>VIIRS ${p.d}</b><br>${ZN(p.z)}`;
      else if(id==="now")h=`<b>KLH ${p.d||("2026-"+String(p.m).padStart(2,"0"))}</b><br>${ZN(p.z)}`;
      else if(id==="brgm")h=`<b>BRGM ${esc(p.jenis)} ${p.tahun||""}</b><br>${esc(p.khg)}<br><span>${esc(p.desa)}</span>`;
      else if(id==="feg-fill")h=`<b>${T("FEG peat soil")}</b><br>${esc(p.thick)}<br><span>${esc(p.fn)}</span> · ${nf(p.ha,1)} ha`;
      else if(id==="burned")h=`<b>${T("Burned area")} ${p.year}</b>`;
      else if(id==="runway")h=`<b>${esc(C.airport.name)} (${C.airport.icao})</b>`;
      showTip(ev.originalEvent,h)});
    map.on("mouseout",hideTip);
  });
}

// ---------- page ----------
function render(){texts();kpis();checks();peatbars();zoneLegend();hotspotCharts();smokeCharts();eventChart();roses();table();sources();toggles();paint();applyVis();applyFilters()}
const sel=document.getElementById("evyear");sel.innerHTML=C.event_years.map(y=>`<option ${y===2023?"selected":""}>${y}</option>`).join("");
sel.onchange=eventChart;
document.getElementById("q").oninput=table;
document.querySelectorAll("#peatmap button").forEach(b=>b.onclick=()=>{PEAT=b.dataset.p;document.querySelectorAll("#peatmap button").forEach(x=>x.classList.toggle("on",x===b));
  vis.feg=PEAT==="feg";vis.gfw=PEAT==="gfw";render()});
document.querySelectorAll("#lang button").forEach(b=>b.onclick=()=>{LANG=b.dataset.l;document.querySelectorAll("#lang button").forEach(x=>x.classList.toggle("on",x===b));render()});
document.getElementById("theme").onclick=()=>{const r=document.documentElement,dark=r.dataset.theme?r.dataset.theme==="dark":matchMedia("(prefers-color-scheme:dark)").matches;r.dataset.theme=dark?"light":"dark";render()};
let rt;addEventListener("resize",()=>{clearTimeout(rt);rt=setTimeout(render,200)});
initMap();render();
