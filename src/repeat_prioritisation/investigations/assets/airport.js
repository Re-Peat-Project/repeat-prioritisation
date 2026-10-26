// Banjarbaru airport fire check: charts, map and tables from DATA (built by investigations/airport.py).
const ID={
"Syamsudin Noor airport and KHG Sungai Maluka - Sungai Martapura":"Bandara Syamsudin Noor dan KHG Sungai Maluka - Sungai Martapura",
"Theme":"Tema","Map":"Peta","Search":"Cari","Sources":"Sumber",
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
"FEG 1:50,000":"FEG 1:50.000","GFW composite, 76 m":"Komposit GFW, 76 m",
"same or previous day; fire ≤ {r} km within 45° of the wind direction":"hari yang sama atau sebelumnya; api ≤ {r} km dalam 45° dari arah angin",
"UTC hours {h}, first report of each hour":"jam UTC {h}, laporan pertama tiap jam",
"Peat fire 2026 around Syamsudin Noor airport":"Kebakaran gambut 2026 di sekitar Bandara Syamsudin Noor",
"2026 hotspots per month, within 20 km":"Hotspot 2026 per bulan, dalam 20 km",
"Smoke days so far, by fire year":"Hari berasap sejauh ini, per tahun kebakaran",
"2026 hotspots within 5 km of the runway":"Hotspot 2026 dalam 5 km dari landasan",
"Context: 2012 to 2025":"Konteks: 2012 sampai 2025",
"Hotspots 2026 within 5 km":"Hotspot 2026 dalam 5 km","≤ 10 km: {a} · ≤ 20 km: {b}":"≤ 10 km: {a} · ≤ 20 km: {b}",
"Hotspots 2026 inside the KHG":"Hotspot 2026 di dalam KHG","on peat: FEG {a} · GFW {b}":"di gambut: FEG {a} · GFW {b}",
"Nearest 2026 hotspot":"Hotspot 2026 terdekat","Smoke days 2026, fixed hours":"Hari berasap 2026, jam tetap",
"previous high {y}: {n}":"tertinggi sebelumnya {y}: {n}","Smoke days with visibility < 1 km":"Hari berasap dengan jarak pandang < 1 km",
"lowest {v} km on {d}":"terendah {v} km pada {d}","Runway inside the KHG":"Landasan di dalam KHG",
"Date":"Tanggal","Distance (km)":"Jarak (km)","Ground, FEG":"Lahan, FEG","Ground, GFW":"Lahan, GFW","Kabupaten":"Kabupaten","Level":"Tingkat","Direction":"Arah",
"peat":"gambut","not peat":"bukan gambut","outside KHG":"di luar KHG","medium":"sedang","high":"tinggi",
"Smoke days, cumulative from 1 July":"Hari berasap, kumulatif sejak 1 Juli","2012-2025":"2012-2025",
"KLH 2026 to {d}; METAR to {m}":"KLH 2026 sampai {d}; METAR sampai {m}","Month":"Bulan","all months":"semua bulan",
"Smoke days, visibility < 1 km":"Hari berasap, jarak pandang < 1 km",
"KHG boundary, peat soil, thickness":"Batas KHG, tanah gambut, ketebalan","Peat cross-check":"Pembanding gambut",
"Hotspots 2012-2025":"Hotspot 2012-2025","Hotspots 2026":"Hotspot 2026","Visibility, smoke, wind":"Jarak pandang, asap, angin","Runway line":"Garis landasan",
"Burned area (2026 product so far: {v} ha within {r} km)":"Area terbakar (produk 2026 sejauh ini: {v} ha dalam {r} km)",
"Verdict: fire in and around the KHG reaches the airport":"Kesimpulan: kebakaran di dalam dan sekitar KHG sampai ke bandara",
"Airport":"Bandara","Fire nearby":"Api di sekitar","Pattern":"Pola","Limits":"Batasan",
"{n} smoke days in {y} (fixed hours), above the previous high of {p} in {py}; {l} with visibility under 1 km, lowest {v} km on {d}.":"{n} hari berasap pada {y} (jam tetap), di atas rekor sebelumnya {p} pada {py}; {l} hari dengan jarak pandang di bawah 1 km, terendah {v} km pada {d}.",
"Half the runway lies inside the KHG. {y}: {a} hotspots within {r} km, nearest {k} km ({d}); {lv}.":"Separuh landasan berada di dalam KHG. {y}: {a} hotspot dalam {r} km, terdekat {k} km ({d}); {lv}.",
"Smoke years ({s}) are the fire years near the airport; {q} had almost none. Smoke peaks at {h}:00 WITA. In {y} smoke came most often with wind from the {w}; most hotspots within 10 km lay {hs} of the runway. On {u} of {n} smoke days with hotspot data a fire within {r} km was upwind (both levels).":"Tahun berasap ({s}) adalah tahun kebakaran di sekitar bandara; {q} hampir tanpa asap. Asap memuncak pukul {h}:00 WITA. Pada {y} asap paling sering datang dengan angin dari {w}; sebagian besar hotspot dalam 10 km berada di {hs} landasan. Pada {u} dari {n} hari berasap yang punya data hotspot, ada api dalam {r} km di arah datangnya angin (kedua tingkat).",
"Regional fire (up to {b} km) burned on nearly every smoke day, so the local share cannot be measured. Peat depends on the map: FEG {f} vs GFW {g} hotspots in {y} on peat. Hotspots end {e}.":"Api regional (sampai {b} km) ada hampir setiap hari berasap, jadi porsi lokal tidak bisa diukur. Gambut tergantung peta: FEG {f} vs GFW {g} hotspot {y} di gambut. Data hotspot sampai {e}.",
"Confidence":"Kepercayaan","Medium + high":"Sedang + tinggi","High only":"Tinggi saja",
"medium + high {a} · high {b}":"sedang + tinggi {a} · tinggi {b}","high only":"tinggi saja","medium + high":"sedang + tinggi",
"Levels: VIIRS nominal (n) = medium, high (h) = high; KLH Sedang = medium, Tinggi = high. Smoke attribution columns use both levels.":"Tingkat: VIIRS nominal (n) = sedang, high (h) = tinggi; KLH Sedang = sedang, Tinggi = tinggi. Kolom atribusi asap memakai kedua tingkat.",
"Smoke/haze from space":"Asap/kabut dari satelit","Satellite true colour (VIIRS NOAA-20)":"Citra warna asli (VIIRS NOAA-20)",
"Aerosol optical depth (MODIS MAIAC, 1 km)":"Kedalaman optik aerosol (MODIS MAIAC, 1 km)","none":"tidak ada","Date":"Tanggal",
"Airport that day":"Bandara hari itu","smoke":"asap","haze":"kabut (HZ)","clear":"cerah","no report":"tidak ada laporan",
"lowest visibility {v} km":"jarak pandang terendah {v} km","Click a day to show it on the map":"Klik satu hari untuk menampilkannya di peta",
"Haze reported":"Kabut (HZ) dilaporkan","not available before {d}":"tidak tersedia sebelum {d}",
"Satellite layers load from NASA GIBS on the internet; clouds hide smoke on cloudy days.":"Lapisan satelit dimuat dari NASA GIBS (internet); awan menutupi asap pada hari berawan.",
};
let LANG="en";
const T=(s,v)=>{let o=LANG==="id"&&ID[s]?ID[s]:s;if(v)for(const k in v)o=o.replaceAll("{"+k+"}",v[k]);return o};
const css=n=>getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const nf=(x,d=0)=>x==null||isNaN(x)?"–":new Intl.NumberFormat(LANG==="id"?"id-ID":"en-US",{maximumFractionDigits:d,minimumFractionDigits:d}).format(x);
const pct=(x,d=0)=>x==null||isNaN(x)?"–":nf(100*x,d)+"%";
const F=DATA.facts,H=DATA.hot,M=DATA.metar,C=DATA.cfg,RK=C.rings_km,FAR=RK[RK.length-1];
const ZONES=["peat","mineral","outside"],ZV={peat:"--c-peat",mineral:"--c-min",outside:"--c-out"};
let PEAT="feg",CONF="all";
const HC=()=>CONF==="high"?H.high:H;   // hotspot summaries for the chosen confidence
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
  document.getElementById("sub").textContent=`${C.khg.name} (${C.khg.code}, ${nf(F.khg_ha)} ha) · ${C.airport.name} (${C.airport.icao}) · `+
    T("KLH 2026 to {d}; METAR to {m}",{d:H.now_last,m:M.last});
  document.getElementById("foot").textContent=T("Weather reports {a} to {b}, {n} reports; hotspots to {d}",{a:M.first,b:M.last,n:nf(M.n),d:H.now_last})+
    ". "+T("Hotspots 2026 are KLH MODIS, not VIIRS: not on the same scale")+". "+T("Levels: VIIRS nominal (n) = medium, high (h) = high; KLH Sedang = medium, Tinggi = high. Smoke attribution columns use both levels.");
}

// ---------- KPIs ----------
function kpis(){
  const yr=Object.fromEntries(M.years.map(r=>[r.year,r])),Y=M.now.year,S=HC().now_summary,SA=H.now_summary,SH=H.high.now_summary,NN=HC().nearest_now;
  const both=(a,b)=>T("medium + high {a} · high {b}",{a:nf(a),b:nf(b)});
  const prev=M.years.filter(r=>r.year<Y),hi=prev.reduce((a,b)=>b.smoke_days_fixed>a.smoke_days_fixed?b:a,prev[0]),hl=prev.reduce((a,b)=>b.smoke_lt1_days>a.smoke_lt1_days?b:a,prev[0]);
  const k=[
    [T("Hotspots 2026 within 5 km"),nf(S["r"+RK[0]])+`<small>${T(CONF==="high"?"high only":"medium + high")}</small>`,both(SA["r"+RK[0]],SH["r"+RK[0]])+"<br>"+T("≤ 10 km: {a} · ≤ 20 km: {b}",{a:nf(S["r"+RK[1]]),b:nf(S["r"+FAR])}),"KLH 2026 hotspots (MODIS), "+H.now_first+" to "+H.now_last+"; distance to the runway line. Medium = Sedang, high = Tinggi",true],
    [T("Hotspots 2026 inside the KHG"),nf(S.khg),both(SA.khg,SH.khg)+"<br>"+T("on peat: FEG {a} · GFW {b}",{a:nf(S.khg_peat_feg),b:nf(S.khg_peat_gfw)}),"KLH 2026 hotspots inside "+C.khg.name+". Peat: FEG 1:50,000 peat-soil polygons, or GFW composite peat cells",true],
    [T("Nearest 2026 hotspot"),nf(NN.d_km,1)+"<small>km</small>",NN.day+" · "+T("high only")+": "+nf(H.high.nearest_now.d_km,1)+" km ("+H.high.nearest_now.day+")","Shortest distance from a KLH 2026 hotspot to the runway line",true],
    [T("Smoke days 2026, fixed hours"),nf(yr[Y]?.smoke_days_fixed),T("previous high {y}: {n}",{y:hi.year,n:nf(hi.smoke_days_fixed)}),"METAR "+C.airport.icao+" (Iowa Environmental Mesonet): local days with smoke (FU) on the UTC hours "+M.fixed_hours_utc.join(", ")+", first report of each hour, so that years with more reports per day are not favoured. "+M.now.first_smoke+" to "+M.now.last_smoke,true],
    [T("Smoke days with visibility < 1 km"),nf(yr[Y]?.smoke_lt1_days),T("lowest {v} km on {d}",{v:nf(M.now.vis_min,2),d:M.now.vis_min_day})+" · "+T("previous high {y}: {n}",{y:hl.year,n:nf(hl.smoke_lt1_days)}),"Days with a smoke (FU) report and a lowest METAR visibility under 1 km; the lowest visibility of the day may come from another hour",true],
    [T("Runway inside the KHG"),nf(F.runway_in_khg_m/1000,2)+"<small>km</small>",T("of {v} km",{v:nf(F.runway_m/1000,2)})+" · "+T("Runway to nearest peat")+": FEG "+nf(F.runway_to_peat_km,1)+" · GFW "+nf(F.runway_to_gfw_km,1)+" km","Runway 10/28 from threshold coordinates ("+C.airport.runway_source+"); KHG from the KLHK FEG 1:50,000 layer, "+C.khg.sk,false]];
  document.getElementById("kpis").innerHTML=k.map(a=>`<div class="card kpi${a[4]?" now":""}" data-tip="${esc(a[3])}"><div class="v">${a[1]}</div><div class="l">${a[0]}</div><div class="s">${a[2]}</div></div>`).join("");
}

// ---------- verdict: short reading of the numbers above, all computed from DATA ----------
function verdict(){
  const Y=M.now.year,yr=Object.fromEntries(M.years.map(r=>[r.year,r])),y=yr[Y],S=HC().now_summary,NN=HC().nearest_now,lv=T(CONF==="high"?"high only":"medium + high");
  const prev=M.years.filter(r=>r.year<Y),hi=prev.reduce((a,b)=>b.smoke_days_fixed>a.smoke_days_fixed?b:a,prev[0]);
  const smoky=M.years.filter(r=>r.smoke_days_fixed>=30).map(r=>r.year),quiet=M.years.filter(r=>r.smoke_days_fixed<=3).map(r=>r.year);
  const rate=M.smoke_hour.map((v,i)=>M.obs_hour[i]?v/M.obs_hour[i]:0),pk=d3.maxIndex(rate);
  const top=a=>SECT[d3.maxIndex(a)],withData=y.smoke_days-y.src_nodata;
  const P=[
    [T("Airport"),T("{n} smoke days in {y} (fixed hours), above the previous high of {p} in {py}; {l} with visibility under 1 km, lowest {v} km on {d}.",
      {n:nf(y.smoke_days_fixed),y:Y,p:nf(hi.smoke_days_fixed),py:hi.year,l:nf(y.smoke_lt1_days),v:nf(M.now.vis_min,2),d:M.now.vis_min_day})],
    [T("Fire nearby"),T("Half the runway lies inside the KHG. {y}: {a} hotspots within {r} km, nearest {k} km ({d}); {lv}.",
      {y:Y,a:nf(S["r"+RK[0]]),r:RK[0],k:nf(NN.d_km,1),d:NN.day,lv})],
    [T("Pattern"),T("Smoke years ({s}) are the fire years near the airport; {q} had almost none. Smoke peaks at {h}:00 WITA. In {y} smoke came most often with wind from the {w}; most hotspots within 10 km lay {hs} of the runway. On {u} of {n} smoke days with hotspot data a fire within {r} km was upwind (both levels).",
      {s:smoky.join(", "),q:quiet.join(", "),h:String(pk).padStart(2,"0"),y:Y,w:top(M.now.wind_smoke),hs:top(HC().sector_now),u:nf(y.smoke_upwind),n:nf(withData),r:FAR})],
    [T("Limits"),T("Regional fire (up to {b} km) burned on nearly every smoke day, so the local share cannot be measured. Peat depends on the map: FEG {f} vs GFW {g} hotspots in {y} on peat. Hotspots end {e}.",
      {b:C.regional_km,f:nf(S.khg_peat_feg),g:nf(S.khg_peat_gfw),y:Y,e:H.now_last})]];
  document.getElementById("verdict").innerHTML=`<h2>${T("Verdict: fire in and around the KHG reaches the airport")}</h2><ul>`+
    P.map(p=>`<li><b>${esc(p[0])}</b>${esc(p[1])}</li>`).join("")+"</ul>";
}

// ---------- 2026 ----------
function nowMonth(){
  const MT=PEAT==="feg"?HC().now_month:HC().now_month_gfw,last=+H.now_last.slice(5,7),rings=[`0-${RK[0]}`,`${RK[0]}-${RK[1]}`,`${RK[1]}-${FAR}`];
  const by=Object.fromEntries(MT.map(r=>[r.month,r]));
  lineChart("nowmonth",ZONES.map(z=>({n:ZN(z),c:ZV[z],v:d3.range(1,last+1).map(mo=>[mo,by[mo]?rings.reduce((s,a)=>s+by[mo][a+"|"+z],0):0])})),
    {h:200,xfmt:mo=>d3.timeFormat("%b")(new Date(2026,mo-1,1)),unit:T("KLH 2026")+", "+T(CONF==="high"?"high only":"medium + high")+" · "+peatNote()});
}
function cumChart(){
  const yrs=C.event_years,cols={};yrs.forEach((y,i)=>cols[y]=y===M.now.year?"--c-peat":["--c-min","--c-out","--c-reg"][i%3]);
  document.getElementById("cl").innerHTML=yrs.map(y=>`<span><i class="sw" style="background:${css(cols[y])}"></i>${y}</span>`).join("");
  const S=yrs.map(y=>{let c=0;return {n:String(y),c:cols[y],w:y===M.now.year?3:1.5,v:(DATA.metar.events[y]||[]).map(d=>{c+=d[5];const t=new Date(d[0]);return [+new Date(2026,t.getMonth(),t.getDate()),c]})}});
  const ev=document.getElementById("event"),h=Math.max(300,(ev.offsetHeight||480)-40);   // as tall as the daily panels beside it
  lineChart("cum",S,{time:true,h,endLab:true,unit:T("Smoke days, cumulative from 1 July")+" · "+T("UTC hours {h}, first report of each hour",{h:M.fixed_hours_utc.join(", ")})});
}
let nearSort=1,nearCol=1;
function nearTable(){
  const zl={peat:T("peat"),mineral:T("not peat"),outside:T("outside KHG")};
  const cols=[T("Date"),T("Distance (km)"),T("Ground, FEG"),T("Ground, GFW"),T("Level"),T("Direction")];
  const q=document.getElementById("qn").value.trim().toLowerCase();
  const rows=H.now_near.filter(r=>CONF==="all"||r[5]==="high").map(r=>[r[0]||"–",r[1],zl[r[2]],zl[r[3]],T(r[5]),r[6]]).filter(r=>!q||r.join(" ").toLowerCase().includes(q))
    .sort((a,b)=>nearSort*(a[nearCol]>b[nearCol]?1:a[nearCol]<b[nearCol]?-1:0));
  const t=document.getElementById("neartab");
  t.innerHTML=`<thead><tr>${cols.map((c,i)=>`<th data-i="${i}">${c}${nearCol===i?(nearSort>0?" ▲":" ▼"):""}</th>`).join("")}</tr></thead><tbody>`+
    rows.map(r=>`<tr>${r.map((c,i)=>`<td>${i===1?nf(c,2):esc(c)}</td>`).join("")}</tr>`).join("")+"</tbody>";
  t.querySelectorAll("th").forEach(th=>th.onclick=()=>{const i=+th.dataset.i;nearSort=nearCol===i?-nearSort:1;nearCol=i;nearTable()});
}

// ---------- peat sources (dot plot) ----------
function peatbars(){
  const el=document.getElementById("peatbars");el.innerHTML="";
  const rows=[[T("KHG"),F.feg_peat_ha/F.khg_ha,F.gfw_share_khg,F.gpm_share_khg],
    ...F.rings.map(r=>[T("Within "+r.km+" km"),r.feg_peat_ha/r.area_ha,r.gfw_share,r.gpm_share])];
  const S=[[T("FEG 50K peat soil"),"--ink"],[T("GFW composite"),"--c-min"],[T("Global Peatland Map 1 km"),"--c-out"]];
  const card=el.closest(".card"),free=card?card.clientHeight-130:0;   // fill the card, which is as tall as the map column beside it
  const W=el.clientWidth||360,m={l:84,r:14,t:6,b:26},rh=Math.max(30,Math.min(70,free/rows.length||30)),h=m.t+m.b+rows.length*rh;
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
  const W=el.clientWidth||520,h=o.h||230,m={l:48,r:o.endLab?48:14,t:10,b:28};
  const xs=series.flatMap(s=>s.v.map(d=>d[0])),ys=series.flatMap(s=>s.v.map(d=>d[1])).filter(v=>v!=null);
  const x=(o.time?d3.scaleTime():d3.scaleLinear()).domain(o.xd||d3.extent(xs)).range([m.l,W-m.r]);
  const y=d3.scaleLinear([0,o.ymax||d3.max(ys)||1],[h-m.b,m.t]).nice();
  const svg=d3.select(el).append("svg").attr("width",W).attr("height",h);
  svg.append("g").attr("class","gridl").attr("transform",`translate(${m.l},0)`).call(d3.axisLeft(y).ticks(4).tickSize(-(W-m.l-m.r)).tickFormat(""));
  svg.append("g").attr("class","axis").attr("transform",`translate(0,${h-m.b})`).call(o.time?d3.axisBottom(x).ticks(6).tickFormat(d3.timeFormat("%b")):d3.axisBottom(x).ticks(Math.min(new Set(xs).size,8)).tickFormat(o.xfmt||d3.format("d")));
  svg.append("g").attr("class","axis").attr("transform",`translate(${m.l},0)`).call(d3.axisLeft(y).ticks(4).tickFormat(v=>nf(v)));
  if(o.yl)svg.append("text").attr("class","lab").attr("x",m.l).attr("y",m.t-1).attr("dy","-0.1em").text("");
  const line=d3.line().defined(d=>d[1]!=null).x(d=>x(d[0])).y(d=>y(d[1]));
  series.forEach(s=>{if(s.w!==0)svg.append("path").attr("d",line(s.v)).attr("fill","none").attr("stroke",css(s.c)).attr("stroke-width",s.w||2).attr("stroke-dasharray",s.dash||null);
    if(s.dots)svg.append("g").selectAll("circle").data(s.v.filter(s.dots)).join("circle").attr("cx",d=>x(d[0])).attr("cy",d=>y(d[1])).attr("r",3).attr("fill",css(s.dc||s.c));
    if(o.endLab){const l=[...s.v].reverse().find(d=>d[1]!=null);if(l)svg.append("text").attr("class","end").attr("x",x(l[0])+6).attr("y",y(l[1])+4).attr("fill",css(s.c)).text(s.n)}});
  // hover
  const xv=[...new Set(xs.map(v=>+v))].sort((a,b)=>a-b);
  const g=svg.append("line").attr("stroke",css("--axis")).attr("y1",m.t).attr("y2",h-m.b).style("display","none");
  svg.append("rect").attr("x",m.l).attr("y",m.t).attr("width",W-m.l-m.r).attr("height",h-m.t-m.b).attr("fill","transparent")
    .on("mousemove",e=>{const px=d3.pointer(e)[0],xi=x.invert(px),k=xv[d3.minIndex(xv,v=>Math.abs(v-xi))];g.style("display",null).attr("x1",x(k)).attr("x2",x(k));
      const lab=o.time?d3.timeFormat(o.endLab?"%d %b":"%d %b %Y")(new Date(k)):o.xfmt?o.xfmt(k):k;
      showTip(e,`<b>${lab}</b>`+series.map(s=>{const d=s.v.find(d=>+d[0]===k);return `<br><span style="color:${css(s.c)}">●</span> ${esc(s.n)} <b>${d&&d[1]!=null?nf(d[1],o.dec||0):"–"}</b>`}).join("")+(o.extra?o.extra(k):""))})
    .on("mouseleave",()=>{g.style("display","none");hideTip()})
    .on("click",e=>{if(!o.click)return;const xi=x.invert(d3.pointer(e)[0]);o.click(xv[d3.minIndex(xv,v=>Math.abs(v-xi))])}).style("cursor",o.click?"pointer":null);
  if(o.unit)d3.select(el).append("div").attr("class","legend").html(`<span style="color:${css("--muted")}">${esc(o.unit)}</span>`);
}
const zoneLegend=()=>document.querySelectorAll(".zl").forEach(e=>e.innerHTML=ZONES.map(z=>`<span><i class="sw" style="background:${css(ZV[z])}"></i>${ZN(z)}</span>`).join(""));

function hotspotCharts(){
  const rings=[`0-${RK[0]}`,`${RK[0]}-${RK[1]}`],VY=PEAT==="feg"?HC().viirs_year:HC().viirs_year_gfw;
  ["hs5","hs10"].forEach((id,i)=>lineChart(id,ZONES.map(z=>({n:ZN(z),c:ZV[z],v:VY.map(r=>[r.year,r[rings[i]+"|"+z]])})),{unit:"VIIRS, "+T(CONF==="high"?"high only":"medium + high")+" · "+peatNote()}));
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
  const hv=Y.filter(r=>r.year<M.now.year);
  lineChart(p[0],[{n:T("Smoke days, fixed hours"),c:"--vis",v:Y.map(r=>[r.year,r.smoke_days_fixed]),dots:d=>d[0]===M.now.year,dc:"--c-peat"}],{h:130,unit:T("Smoke days, fixed hours")+" (METAR FU) · "+T("UTC hours {h}, first report of each hour",{h:M.fixed_hours_utc.join(", ")}),
    extra:k=>{const r=Y.find(r=>r.year===k);return r?`<br><span>${T("Smoke days")}</span> ${r.smoke_days}<br><span>${T("Reports per day")}</span> ${nf(M.reports_per_day[k],1)}<br><span>${T("Days with reports")}</span> ${r.days}`:""}});
  const hk=CONF==="high"?"_high":"";
  lineChart(p[1],[{n:T("Hotspots ≤ {r} km",{r:FAR}),c:"--c-peat",v:hv.map(r=>[r.year,r["hs_near"+hk]])}],{h:120,xd:d3.extent(Y,r=>r.year),unit:T("Hotspots ≤ {r} km",{r:FAR})+" · "+T("VIIRS 2012-2025")});
  lineChart(p[2],[{n:T("Hotspots {a} to {b} km",{a:FAR,b:C.regional_km}),c:"--c-reg",v:hv.map(r=>[r.year,r["hs_reg"+hk]])}],{h:120,xd:d3.extent(Y,r=>r.year),unit:T("Hotspots {a} to {b} km",{a:FAR,b:C.regional_km})+" · "+T("VIIRS 2012-2025")});
}

function eventChart(){
  const y=document.getElementById("evyear").value,ev=DATA.metar.events[y]||[];
  document.getElementById("el").innerHTML=[["--vis",T("Lowest visibility (km)")],["--c-peat",T("Smoke reported")],["--c-min",T("Haze reported")],["--c-peat",T("Hotspots ≤ {r} km",{r:FAR})],["--c-reg",T("Hotspots {a} to {b} km",{a:FAR,b:C.regional_km})]]
    .map((a,i)=>`<span><i class="sw ${i===1||i===2?"dot":""}" style="background:${css(a[0])}"></i>${a[1]}</span>`).join("");
  const el=document.getElementById("event");el.innerHTML="";
  const a=document.createElement("div"),b=document.createElement("div"),c=document.createElement("div");el.append(a,b,c);
  const t=ev.map(d=>[new Date(d[0]),d]);const xd=d3.extent(t,d=>d[0]);
  lineChart(a,[{n:T("Lowest visibility (km)"),c:"--vis",w:1.5,v:t.map(d=>[d[0],d[1][1]]),dots:d=>t.find(q=>+q[0]===+d[0])[1][2]>0,dc:"--c-peat"},
      {n:T("Haze reported"),c:"--c-min",w:0,v:t.map(d=>[d[0],d[1][1]]),dots:d=>{const q=t.find(q=>+q[0]===+d[0])[1];return q[8]>0&&!(q[2]>0)}}],
    {time:true,h:150,dec:1,xd,unit:T("Lowest visibility (km)")+" · METAR "+C.airport.icao+" · "+T("Click a day to show it on the map"),
     click:k=>setSmokeDate(d3.timeFormat("%Y-%m-%d")(new Date(k))),
     extra:k=>{const d=t.find(q=>+q[0]===k);return d?`<br><span>${T("Smoke reported")}</span> ${d[1][2]} · <span>${T("Haze reported")}</span> ${d[1][8]}`:""}});
  const now=+y===M.now.year,src=(now?T("KLH 2026"):"VIIRS")+", "+T(CONF==="high"?"high only":"medium + high"),off=CONF==="high"?3:0,
    hs=(d,i)=>now&&d[1][0]>H.now_last?null:d[1][i+off];   // no hotspot data after the KLH file ends; high-only counts sit 3 places later
  lineChart(b,[{n:T("Hotspots ≤ {r} km",{r:FAR}),c:"--c-peat",w:1.5,v:t.map(d=>[d[0],hs(d,3)])}],{time:true,h:110,xd,unit:T("Hotspots ≤ {r} km",{r:FAR})+" · "+(now?T("KLH 2026 to {d}; METAR to {m}",{d:H.now_last,m:M.last}):src)});
  lineChart(c,[{n:T("Hotspots {a} to {b} km",{a:FAR,b:C.regional_km}),c:"--c-reg",w:1.5,v:t.map(d=>[d[0],hs(d,4)])}],{time:true,h:110,xd,unit:T("Hotspots {a} to {b} km",{a:FAR,b:C.regional_km})+" · "+src});
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
  const Y=M.now.year,hist=M.wind_smoke.map((v,i)=>v-M.now.wind_smoke[i]);
  rose("rose1",[{n:T("wind from")+" "+Y,c:"--c-peat",fill:true,v:M.now.wind_smoke},{n:T("2012-2025"),c:"--ink2",fill:false,v:hist}],
    T("calm: {n} reports",{n:nf(M.now.calm_smoke)})+" ("+Y+")");
  rose("rose2",[{n:T("KLH 2026"),c:"--c-peat",fill:true,v:HC().sector_now},{n:T("VIIRS 2012-2025"),c:"--ink2",fill:false,v:HC().sector_viirs}],T(CONF==="high"?"high only":"medium + high"));
  lineChart("hour",[{n:T("Smoke reported"),c:"--vis",v:M.smoke_hour.map((v,i)=>[i,M.obs_hour[i]?100*v/M.obs_hour[i]:null])}],{dec:1,unit:T("share of reports with smoke (%)")+" · "+T("local time (WITA)")});
}

// ---------- tables ----------
let sortCol="year",sortDir=-1;
function table(){
  const cols=[["year",T("Year")],["rpd",T("Reports per day")],["days",T("Days with reports")],["smoke_days",T("Smoke days")],["smoke_days_fixed",T("Smoke days, fixed hours")],
    ["low_smoke_days",T("Smoke with low visibility")+` <small>&lt; ${C.low_vis_km} km</small>`],["smoke_lt1_days",T("Smoke days, visibility < 1 km")],["haze_days",T("Haze days")],
    ["src_both",T("Fire ≤ {r} km and {r} to {b} km",{r:FAR,b:C.regional_km})],["src_near",T("Only fire ≤ {r} km",{r:FAR})],["src_regional",T("Only fire {a} to {b} km",{a:FAR,b:C.regional_km})],
    ["src_none",T("No fire within {b} km",{b:C.regional_km})],["src_nodata",T("No hotspot data yet")],
    ["smoke_upwind",T("Smoke with fire ≤ {r} km upwind",{r:FAR})],["smoke_calm_only",T("Smoke only in calm")],
    ["hs_near",T("Hotspots ≤ {r} km",{r:FAR})+` <small>${T("medium + high")}</small>`],["hs_near_high",T("Hotspots ≤ {r} km",{r:FAR})+` <small>${T("high only")}</small>`],
    ["hs_reg",T("Hotspots {a} to {b} km",{a:FAR,b:C.regional_km})+` <small>${T("medium + high")}</small>`],["hs_reg_high",T("Hotspots {a} to {b} km",{a:FAR,b:C.regional_km})+` <small>${T("high only")}</small>`]];
  M.years.forEach(r=>r.rpd=M.reports_per_day[r.year]);
  const q=document.getElementById("q").value.trim();
  const rows=M.years.filter(r=>!q||String(r.year).includes(q)).sort((a,b)=>sortDir*(a[sortCol]-b[sortCol]));
  const tab=document.getElementById("tab");
  tab.innerHTML=`<thead><tr>${cols.map(c=>`<th data-c="${c[0]}">${c[1]}${sortCol===c[0]?(sortDir>0?" ▲":" ▼"):""}</th>`).join("")}</tr></thead><tbody>`+
    rows.map(r=>`<tr${r.year===M.now.year?' class="now"':""}>${cols.map(c=>`<td>${c[0]==="year"?r.year+(r.year===2026?" *":""):nf(r[c[0]],c[0]==="rpd"?1:0)}</td>`).join("")}</tr>`).join("")+"</tbody>";
  document.getElementById("tabnote").textContent=T("same or previous day; fire ≤ {r} km within 45° of the wind direction",{r:FAR})+" · * "+T("Hotspots 2026 are KLH MODIS, not VIIRS: not on the same scale");
  tab.querySelectorAll("th").forEach(th=>th.onclick=()=>{const c=th.dataset.c;sortDir=sortCol===c?-sortDir:-1;sortCol=c;table()});
}
function sources(){
  const b26=DATA.burned.find(r=>r.year===M.now.year);
  const rows=[
    ["_data_hotspot_Januari_September_2026.gpkg",T("Hotspots 2026"),"KLH, MODIS, Sedang/Tinggi (medium/high), "+H.now_first+" to "+H.now_last],
    [F.metar_file,T("Visibility, smoke, wind"),"Iowa Environmental Mesonet ASOS/METAR archive, to "+M.last],
    ["klhk_khg_feg_50k.gpkg",T("KHG boundary, peat soil, thickness"),"KLHK FEG 1:50,000 via BIG Satu Peta; "+C.khg.sk],
    ["peat_extent_gfw_v20230315_z11.tif",T("Peat cross-check"),"GFW composite (Miettinen 2016 ∪ Gumbricht 2017)"],
    ["peat_extent_gpm2022_1km.tif",T("Peat cross-check"),"Global Peatland Map 2.0, 1 km, CC BY-NC-SA"],
    ["hotspot_viirs_snpp_2012_2025.gpkg",T("Hotspots 2012-2025"),"FIRMS VIIRS S-NPP, nominal/high (medium/high), type 0; 2026 not yet published"],
    ["burnt_area_2015_2026_Indonesia.gpkg",T("Burned area"),b26?T("Burned area (2026 product so far: {v} ha within {r} km)",{v:nf(b26["r"+FAR]),r:FAR}):""],
    ["infrastruktur_hidrologis_existing_BRGM_Indonesia.gpkg","BRGM",F.brgm_named+" × "+F.brgm_named_detail.join(", ")+", "+F.brgm_named_desa.join(", ")],
    [T("Runway"),T("Runway line"),C.airport.runway_source],
    ...(C.gibs?C.gibs.layers.map(g=>["NASA GIBS: "+g.layer,T("Smoke/haze from space"),T(g.title)+"; "+T("Satellite layers load from NASA GIBS on the internet; clouds hide smoke on cloudy days.")]):[])];
  document.getElementById("src").innerHTML=`<thead><tr><th>${T("Dataset")}</th><th>${T("Used for")}</th><th>${T("Note")}</th></tr></thead><tbody>`+
    rows.map(r=>`<tr>${r.map(c=>`<td style="text-align:left">${esc(c)}</td>`).join("")}</tr>`).join("")+"</tbody>";
}

// ---------- satellite smoke/haze ----------
let smokeDate=M.now.vis_min_day||M.last,satLayer="none";
const gibsUrl=(g,d)=>C.gibs.url.replace("{layer}",g.layer).replace("{date}",d).replace("{tms}",g.tms).replace("{ext}",g.ext).replace("{z}","{z}");
function aptPaint(){if(!mapReady)return;const r=M.daily[smokeDate],st=!r?"none":r[1]>0?"smoke":r[2]>0?"haze":"clear";
  map.setPaintProperty("apt","circle-color",st==="smoke"?css("--c-peat"):st==="haze"?css("--c-min"):st==="clear"?css("--c-out"):css("--c-reg"));
  map.setLayoutProperty("apt-lab","text-field",r&&r[0]!=null?nf(r[0],1)+" km":"")}
function setSmokeDate(d){smokeDate=d;const el=document.getElementById("sd");if(el)el.value=d;
  if(mapReady&&C.gibs)C.gibs.layers.forEach(g=>{const src=map.getSource("sat-"+g.id);if(src)src.setTiles([gibsUrl(g,d)])});aptPaint();smokeLegend()}
function smokeLegend(){const el=document.getElementById("smokeleg");if(!el)return;const r=M.daily[smokeDate],g=(C.gibs?C.gibs.layers:[]).find(x=>x.id===satLayer);
  const st=!r?"no report":r[1]>0?"smoke":r[2]>0?"haze":"clear";
  el.innerHTML=`<span><b>${T("Airport that day")}</b>: ${T(st)}${r&&r[0]!=null?" · "+T("lowest visibility {v} km",{v:nf(r[0],1)}):""}</span>`+
    (g&&smokeDate<g.from?`<span style="color:${css("--c-peat")}">${esc(T(g.title))}: ${T("not available before {d}",{d:g.from})}</span>`:"")+
    (g&&g.legend?`<img src="${g.legend}" alt="" style="height:38px;filter:var(--icon-filter)">`:"")}
function smokeControls(){
  const el=document.getElementById("smokectl");if(!el||!C.gibs)return;
  el.innerHTML=`<span class="lab2">${T("Smoke/haze from space")}</span> <select id="sl2"><option value="none">${T("none")}</option>`+
    C.gibs.layers.map(g=>`<option value="${g.id}" ${g.id===satLayer?"selected":""}>${esc(T(g.title))}</option>`).join("")+`</select>`+
    ` <label class="tg">${T("Date")} <input type="date" id="sd" value="${smokeDate}" min="2012-01-01" max="${M.last}"></label><span id="smokeleg" class="legend" style="margin:0"></span>`;
  document.getElementById("sl2").onchange=e=>{satLayer=e.target.value;applyVis();smokeLegend()};
  document.getElementById("sd").onchange=e=>setSmokeDate(e.target.value);
  smokeLegend()}

// ---------- map ----------
let map,mapReady=false;
const L=DATA.layers;
const pts=(rows,key)=>({type:"FeatureCollection",features:rows.map(r=>({type:"Feature",geometry:{type:"Point",coordinates:[r[0],r[1]]},properties:{[key]:r[2],z:ZONES[PEAT==="feg"?r[3]:r[5]],d:r[4],h:r[6]}}))});
const THICK=["0,5 - 1,0 meter","1,0 - 1,5 meter","1,5 - 2,0 meter","2,0 - 2,5 meter","2,5 - 3,0 meter","3,0 - 3,5 meter"];
const TOG=[["now","KLH 2026 hotspots",true],["khg","KHG boundary",true],["feg","FEG peat soil",true],["gfw","GFW peat",false],["burned","Burned area",false],["viirs","VIIRS hotspots",false],["rings","Rings 5, 10, 20 km",true],["brgm","BRGM structures",false]];
const LAYERS={khg:["khg-line"],feg:["feg-fill"],gfw:["gfw"],burned:["burned"],viirs:["viirs"],now:["now"],rings:["rings","rings-lab"],brgm:["brgm"]};
const vis={};TOG.forEach(t=>vis[t[0]]=t[2]);
let viirsYear="2023",burnYear="2023",nowMonthSel="all";
function toggles(){
  const years=[...new Set(L.viirs.map(r=>r[2]))].sort();
  const by=[...new Set(L.burned.features.map(f=>f.properties.year))].sort();
  const months=[...new Set(L.now.map(r=>r[2]))].sort((a,b)=>a-b);
  document.getElementById("toggles").innerHTML=TOG.map(t=>`<label class="tg"><input type="checkbox" data-k="${t[0]}" ${vis[t[0]]?"checked":""}>${T(t[1])}</label>`).join("")+
    ` <label class="tg">${T("Month")} 2026 <select id="nm"><option value="all">${T("all months")}</option>${months.map(mo=>`<option value="${mo}" ${String(mo)===nowMonthSel?"selected":""}>${d3.timeFormat("%b")(new Date(2026,mo-1,1))}</option>`).join("")}</select></label>`+
    ` <label class="tg">${T("Hotspots on the map")} <select id="vy"><option value="all">${T("all years")}</option>${years.map(y=>`<option ${String(y)===viirsYear?"selected":""}>${y}</option>`).join("")}</select></label>`+
    ` <label class="tg">${T("Burned in")} <select id="by"><option value="all">${T("all years")}</option>${by.map(y=>`<option ${String(y)===burnYear?"selected":""}>${y}</option>`).join("")}</select></label>`;
  document.querySelectorAll("#toggles input").forEach(i=>i.onchange=()=>{vis[i.dataset.k]=i.checked;applyVis()});
  document.getElementById("vy").onchange=e=>{viirsYear=e.target.value;applyFilters()};
  document.getElementById("by").onchange=e=>{burnYear=e.target.value;applyFilters()};
  document.getElementById("nm").onchange=e=>{nowMonthSel=e.target.value;applyFilters()};
  document.getElementById("maplegend").innerHTML=
    `<span><i class="sw" style="border:2px solid ${css("--khg")}"></i>${T("KHG boundary")}</span>`+
    (PEAT==="feg"?`<span>${T("Peat thickness (m)")}: `+THICK.map((t,i)=>`<i class="sw" style="background:${d3.interpolateRgb(css("--ramp0"),css("--ramp1"))(i/(THICK.length-1))}" data-tip="${t}"></i>`).join("")+` 0.5 → 3.5</span>`
      :`<span><i class="sw" style="background:rgb(165,134,96);opacity:.6"></i>${T("GFW peat")}</span>`)+
    `<span><i class="sw" style="background:${css("--burn")};opacity:.45"></i>${T("Burned area")}</span>`+
    ZONES.map(z=>`<span><i class="sw dot" style="background:${css(ZV[z])}"></i>${ZN(z)}</span>`).join("")+
    `<span><i class="sw" style="background:${css("--ink")};height:3px;width:14px"></i>${T("Runway")}</span>`;
}
function applyVis(){if(!mapReady)return;for(const k in LAYERS)LAYERS[k].forEach(l=>map.getLayer(l)&&map.setLayoutProperty(l,"visibility",vis[k]?"visible":"none"));
  (C.gibs?C.gibs.layers:[]).forEach(g=>map.setLayoutProperty("sat-"+g.id,"visibility",g.id===satLayer?"visible":"none"))}
function applyFilters(){if(!mapReady)return;
  const hf=CONF==="high"?[["==",["get","h"],1]]:[];
  map.setFilter("viirs",["all",...hf,...(viirsYear==="all"?[]:[["==",["get","y"],+viirsYear]])]);
  map.setFilter("burned",burnYear==="all"?null:["==",["get","year"],+burnYear]);
  map.setFilter("now",["all",...hf,...(nowMonthSel==="all"?[]:[["==",["get","m"],+nowMonthSel]])])}
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
  map.setPaintProperty("apt","circle-stroke-color",css("--surface"));map.setPaintProperty("apt-lab","text-color",css("--ink"));map.setPaintProperty("apt-lab","text-halo-color",css("--surface"));
  aptPaint();
}
function initMap(){
  const e=C.extent;
  map=new maplibregl.Map({container:"map",style:DATA.style,bounds:[[e[0],e[1]],[e[2],e[3]]],fitBoundsOptions:{padding:10},attributionControl:{compact:true},cooperativeGestures:false});
  map.addControl(new maplibregl.NavigationControl({showCompass:false}),"top-right");
  map.addControl(new maplibregl.ScaleControl({unit:"metric"}),"bottom-left");
  map.on("load",()=>{
    (C.gibs?C.gibs.layers:[]).forEach(g=>{map.addSource("sat-"+g.id,{type:"raster",tileSize:256,maxzoom:g.maxzoom,attribution:"NASA GIBS",
      tiles:[gibsUrl(g,smokeDate)]});map.addLayer({id:"sat-"+g.id,type:"raster",source:"sat-"+g.id,layout:{visibility:"none"},paint:{"raster-opacity":g.id==="aod"?.7:1}})});
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
    const rw=L.runway.features[0].geometry.coordinates[0],mid=rw[Math.floor(rw.length/2)];
    map.addSource("apt",{type:"geojson",data:{type:"FeatureCollection",features:[{type:"Feature",geometry:{type:"Point",coordinates:mid},properties:{}}]}});
    map.addLayer({id:"apt",type:"circle",source:"apt",paint:{"circle-radius":9,"circle-stroke-width":2.5}});
    map.addLayer({id:"apt-lab",type:"symbol",source:"apt",layout:{"text-field":"","text-size":12,"text-offset":[0,-1.6],"text-font":["Noto Sans Bold"]},paint:{"text-halo-width":1.8}});
    map.addSource("brgm",{type:"geojson",data:L.brgm});
    map.addLayer({id:"brgm",type:"circle",source:"brgm",paint:{"circle-radius":5,"circle-stroke-width":2,"circle-stroke-color":"#fff"}});
    mapReady=true;paint();applyVis();applyFilters();setSmokeDate(smokeDate);
    const hov=["apt","viirs","now","brgm","feg-fill","burned","runway"];
    map.on("mousemove",ev=>{const f=map.queryRenderedFeatures(ev.point,{layers:hov.filter(l=>map.getLayoutProperty(l,"visibility")!=="none")})[0];
      map.getCanvas().style.cursor=f?"pointer":"";if(!f)return hideTip();const p=f.properties,id=f.layer.id;let h="";
      const lv=T(p.h?"high":"medium");
      if(id==="viirs")h=`<b>VIIRS ${p.d}</b><br>${ZN(p.z)}<br><span>${lv}</span>`;
      else if(id==="now")h=`<b>KLH ${p.d||("2026-"+String(p.m).padStart(2,"0"))}</b><br>${ZN(p.z)}<br><span>${lv}</span>`;
      else if(id==="apt"){const r=M.daily[smokeDate];h=`<b>${esc(C.airport.name)} · ${smokeDate}</b><br>`+(r?`${T(r[1]>0?"smoke":r[2]>0?"haze":"clear")} · ${T("lowest visibility {v} km",{v:nf(r[0],1)})}`:T("no report"))}
      else if(id==="brgm")h=`<b>BRGM ${esc(p.jenis)} ${p.tahun||""}</b><br>${esc(p.khg)}<br><span>${esc(p.desa)}</span>`;
      else if(id==="feg-fill")h=`<b>${T("FEG peat soil")}</b><br>${esc(p.thick)}<br><span>${esc(p.fn)}</span> · ${nf(p.ha,1)} ha`;
      else if(id==="burned")h=`<b>${T("Burned area")} ${p.year}</b>`;
      else if(id==="runway")h=`<b>${esc(C.airport.name)} (${C.airport.icao})</b>`;
      showTip(ev.originalEvent,h)});
    map.on("mouseout",hideTip);
  });
}

// ---------- page ----------
function render(){texts();kpis();verdict();nowMonth();peatbars();zoneLegend();eventChart();cumChart();nearTable();roses();hotspotCharts();smokeCharts();table();sources();toggles();smokeControls();paint();applyVis();applyFilters()}
const sel=document.getElementById("evyear");sel.innerHTML=C.event_years.map(y=>`<option ${y===M.now.year?"selected":""}>${y}</option>`).join("");
sel.onchange=eventChart;
document.getElementById("q").oninput=table;
document.getElementById("qn").oninput=nearTable;
document.querySelectorAll("#peatmap button").forEach(b=>b.onclick=()=>{PEAT=b.dataset.p;document.querySelectorAll("#peatmap button").forEach(x=>x.classList.toggle("on",x===b));
  vis.feg=PEAT==="feg";vis.gfw=PEAT==="gfw";render()});
document.querySelectorAll("#conf button").forEach(b=>b.onclick=()=>{CONF=b.dataset.c;document.querySelectorAll("#conf button").forEach(x=>x.classList.toggle("on",x===b));render()});
document.querySelectorAll("#lang button").forEach(b=>b.onclick=()=>{LANG=b.dataset.l;document.querySelectorAll("#lang button").forEach(x=>x.classList.toggle("on",x===b));render()});
document.getElementById("theme").onclick=()=>{const r=document.documentElement,dark=r.dataset.theme?r.dataset.theme==="dark":matchMedia("(prefers-color-scheme:dark)").matches;r.dataset.theme=dark?"light":"dark";render()};
let rt;addEventListener("resize",()=>{clearTimeout(rt);rt=setTimeout(render,200)});
initMap();render();
