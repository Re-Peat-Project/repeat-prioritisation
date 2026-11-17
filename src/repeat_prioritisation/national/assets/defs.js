// Shared definitions of the prioritisation (types, dimensions, indicators, interventions), used by every page.
// Needs t, fx, fmt in scope at call time.
const TYPE_ORDER=["A","B","C","D","E"];
const TYPE_LABEL={A:"Quick action",B:"Multi-party coordination",C:"Staged restoration",D:"Protect and monitor",E:"Monitor"};
const TYPE_NOTE={A:"High urgency, low or medium complexity: act now through KLH and the villages.",
  B:"High urgency, high complexity: needs coordination of companies, the Ministry of Forestry, KLH and villages.",
  C:"Medium urgency: restore in stages.",D:"Low urgency, high stake (deep peat, dome, protected function, conservation areas): protect and monitor.",
  E:"Low urgency, low or medium stake: monitor."};
const TYPE_RULE={A:"urgency high, complexity low or medium",B:"urgency high, complexity high",C:"urgency medium",D:"urgency low, stake high",E:"urgency low, stake low or medium"};
const DIMS=[["u","Urgency","urgency"],["s","Stake","stake"],["c","Complexity","complexity"],["f","Feasibility","feasibility"],["p","People","people"]];
const DIM_TIP={
  u:"How likely the peat is to burn and degrade further. High urgency: the KHG burns often and widely, its peat is damaged and drained by canals.",
  s:"What would be lost if the peat burns or keeps draining: deep peat, peat domes, peat with a protected function, conservation areas, and the size of the peat.",
  c:"How hard it is to act: how many parties hold or claim the peat and how tangled their claims are, how many kinds of actors hold the damaged peat, how many villages are involved.",
  f:"How easy rewetting is on the ground: water nearby to fill the canals, road access for building blocks, and a smaller dry-season water shortfall. A flag only: it does not change the type.",
  p:"Who is affected: people living on the peat and within 10 km of the KHG (haze from peat fires), and villages with land on the peat. A flag only: it does not change the type."};
const SCORE_NOTE="Score 0 to 1: weighted mean of the indicators' percentile ranks among the KHG with at least {m} km2 of peat (0.8 = higher than 80% of them). Ticks mark the tercile cuts.";
const pc=(v,d=0)=>fx(v*100,d)+"%";
// indicator: [label, what it measures and where it comes from, format]
const IND={
  u_fire_freq:["Burned share of peat per year","Average share of the KHG's peat burned each year, 2015-2025 (KLHK burnt-area polygons on KLH peat). Counts double.",v=>pc(v,2)],
  u_burn_repeat:["Peat burned twice or more","Share of the peat burned in two or more years, 2015-2025.",v=>pc(v,1)],
  u_hotspot:["Hotspots per km2 of peat per year","VIIRS hotspots on peat, nominal and high confidence, 2012-2025, per km2 of peat per year.",v=>fx(v,2)],
  u_hotspot_now:["Hotspots this year per km2 of peat","MODIS hotspots on peat this year, medium and high confidence, per km2 of peat.",v=>fx(v,2)],
  damage_share:["Damaged peat (SKEG 2024)","Share of the peat in KLH's damage map SKEG 2024 (the PPEG priority area).",v=>pc(v)],
  u_canal_primary:["Primary canal density","Primary canal length per km2 of the KHG (the project's canal map). The canal measure of the earlier fire ranking; weight 0 by default because canal-affected peat already measures drainage.",v=>fx(v,2)+" km/km2"],
  u_canal_secondary:["Secondary canal density","Secondary canal length per km2 of the KHG. Weight 0 by default.",v=>fx(v,2)+" km/km2"],
  u_canal_tertiary:["Tertiary canal density","Tertiary canal length per km2 of the KHG. Weight 0 by default.",v=>fx(v,2)+" km/km2"],
  canal_share:["Canal-affected peat","Share of the peat within KLH's canal-influence zones (PPEG KET_KANAL).",v=>pc(v)],
  thick3m_share:["Peat 3 m or deeper","Share of the peat 3 m or deeper (KLHK FEG thickness classes).",v=>pc(v)],
  dome_share:["Peat dome","Share of the peat on the dome landform (BBSDLP, in KLH's PPEG analysis): ombrogenous peat that feeds the whole KHG.",v=>pc(v)],
  protected_share:["Protected peat function","Share of the peat with the protected (lindung) peat ecosystem function.",v=>pc(v)],
  peat_km2:["Peat area","KLH peat inside the KHG (PPEG 2026): more peat, more carbon at stake.",v=>fmt(v,0)+" km2"],
  conservation_share:["Conservation areas","Share of the peat in conservation areas: national parks, nature and wildlife reserves (Kawasan Hutan 2023).",v=>pc(v)],
  tenure_complexity:["Tenure complexity","Index 0-1 from four parts: licences on village or community land, contested land, number of claim types on the same peat, number of licence holders. Counts double.",v=>fx(v,2)],
  actor_types:["Actor types on damaged peat","How many of four actor types hold SKEG-damaged peat: companies, company buffers, the Ministry of Forestry, KLH (of 4).",v=>fmt(v,0)],
  villages:["Villages involved","Bluebook target villages plus DMPG villages in the KHG.",v=>fmt(v,0)],
  water_dist_km:["Distance to a large river or lake","Median distance from the peat to the nearest large river (drawn with two banks in RBI) or lake. Shorter is better: water to fill the canals.",v=>fx(v,1)+" km"],
  road_dist_km:["Distance to a road","Median distance from the peat to the nearest road (RBI detailed roads, footpaths excluded). Shorter is better: access to build and maintain blocks.",v=>fx(v,1)+" km"],
  dry_balance_mm:["Dry-season water balance","Rainfall minus evaporation over the dry season (P - E). Higher is better: less water to make up.",v=>fmt(v,0)+" mm"],
  pop_on_peat:["People on the peat","People living on the KHG's peat (IHME Populace 2025, 40 m grid).",v=>fmt(v,0)],
  pop_10km:["People within 10 km","People within 10 km of the KHG boundary: a proxy for exposure to haze from peat fires (IHME Populace 2025, 40 m).",v=>fmt(v,0)],
  villages_peat:["Villages on the peat","2023 villages (KLH boundaries) with land on the KHG's peat.",v=>fmt(v,0)],
  brgm_blocks_per_km2:["BRGM structures per km2","Canal blocks and other BRGM structures per km2 of peat. Reported, not scored: blocks were built where fires were, so it echoed urgency.",v=>fx(v,2)],
  peat_volume_mm3:["Peat volume","Peat area by BBSDLP depth class times the class mid-depth, million m3. Reported, not scored: the depth class is blank for part of the peat.",v=>fmt(v,0)+" Mm3"],
  open_share:["Open or degraded cover","Share of the peat with open or degraded cover in KLH's land cover 2022 (PL_2022): swamp shrub, shrub, open land, open swamp, savanna. Plantations, crops and settlements are not counted.",v=>pc(v)],
  forest_share:["Forest cover","Share of the peat under forest in KLH's land cover 2022 (swamp, dryland and mangrove forest; plantation forest not counted).",v=>pc(v)],
  tma_deep_share:["Water table below 0.4 m","SiTMAT loggers: share of days with the water table deeper than 0.4 m. Reported, not scored: loggers in 164 KHG only.",v=>pc(v)]};
const IV_ORDER=["rewetting and revegetation","rewetting","revegetation","protect"];
const IV_SHORT={"rewetting and revegetation":"Rewet + revegetate","rewetting":"Rewet","revegetation":"Revegetate","protect":"Protect"};
const IV_NOTE={"rewetting and revegetation":"At least {a}% of the peat is drained by canals and at least {b}% has open or degraded cover: block the canals and replant.",
  "rewetting":"At least {a}% of the peat is drained by canals, less than {b}% is open or degraded: block the canals; the cover is still largely there.",
  "revegetation":"At least {b}% of the peat has open or degraded cover, less than {a}% is drained by canals: replant; drainage is limited.",
  "protect":"Less than {a}% drained and less than {b}% open or degraded: the peat is largely intact; protect it and keep it wet."};
const IV_COL={"rewetting and revegetation":"#2b6f9e","rewetting":"#5fa3cf","revegetation":"#7aa95c","protect":"#b9b6ab"};
