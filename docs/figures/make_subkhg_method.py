#!/usr/bin/env python3
"""Write docs/figures/subkhg_method.drawio, the method diagram of docs/subkhg-method.md (plain mxGraph XML; open in draw.io).

  python docs/figures/make_subkhg_method.py
"""
from pathlib import Path
from xml.sax.saxutils import escape

cells, n = [], [1]


def _id():
    n[0] += 1
    return f"c{n[0]}"


def box(x, y, w, h, text, style):
    i = _id()
    cells.append(f'<mxCell id="{i}" value="{escape(text, {chr(34): "&quot;"})}" style="{style}" vertex="1" parent="1">'
                 f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>')
    return i


def edge(a, b, label="", dashed=False):
    st = "edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;endArrow=block;endFill=1;strokeColor=#5f6b7a;fontSize=10;" + ("dashed=1;" if dashed else "")
    cells.append(f'<mxCell id="{_id()}" value="{escape(label)}" style="{st}" edge="1" parent="1" source="{a}" target="{b}"><mxGeometry relative="1" as="geometry"/></mxCell>')


B = "rounded=1;whiteSpace=wrap;html=1;align=left;verticalAlign=top;spacingLeft=6;spacingTop=2;fontSize=11;"
INP, PRO = B + "fillColor=#eef3fb;strokeColor=#5b7db8;", B + "fillColor=#fff4e0;strokeColor=#c98a1b;"
PAR, OUT = B + "fillColor=#f3f3f3;strokeColor=#888888;dashed=1;", B + "fillColor=#e8f5ea;strokeColor=#3f8f50;"
USE, OLD = B + "fillColor=#f5ecf7;strokeColor=#8a5a9c;", B + "fillColor=#fdf3e7;strokeColor=#b07a2a;"
NEW = B + "fillColor=#e9f3fb;strokeColor=#2f6f9f;"
HDR = "text;html=1;fontSize=14;fontStyle=1;align=left;verticalAlign=middle;"
BAND = "rounded=0;whiteSpace=wrap;html=1;fillColor=none;strokeColor=#cccccc;dashed=1;align=left;verticalAlign=top;spacingLeft=8;fontSize=13;fontStyle=1;fontColor=#444444;"

box(20, 10, 1500, 30, "Sub-KHG prioritisation, RE-PEAT: method of 2026-10-26 (repeat-prioritisation, subkhg)", "text;html=1;fontSize=18;fontStyle=1;align=left;")
box(20, 42, 1500, 40, "<b>Per KHG:</b> python -m subkhg.run --config re-peat/sites/&lt;khg&gt;/subkhg.yaml (--fetch-only once for the cloud layers, then --skip-fetch). "
    "Order: KHG inputs → DTM (repeat-dem) → sub-KHG units (repeat-delineation) → neraca air (repeat-neraca) → this ranking → repeat-pump.", PRO)
for x, t in [(30, "INPUTS"), (430, "PROCESSING"), (920, "OUTPUTS  (_khg/&lt;khg&gt;/04_prioritisation/)")]:
    box(x, 88, 360, 24, t, HDR)
box(1280, 88, 230, 24, "USED BY", HDR)
box(15, 115, 1510, 690, "Ranking of the sub-KHG of one KHG by need for rewetting intervention", BAND)
units = box(30, 145, 370, 46, "<b>Sub-KHG units</b> 02_delineation/subkhg_units.gpkg (repeat-delineation)", INP)
nat = box(30, 199, 370, 104, "<b>National layers</b> (_data, as the national profile)<br>• burnt-area polygons 2015-2026 (KLHK)<br>• VIIRS hotspots 2012-2025 (type 0, confidence n/h)<br>• KLH hotspots 2026 (medium, high)<br>• canals with KODE_KANAL · GFW peat extent", INP)
site = box(30, 311, 370, 62, "<b>KHG vectors</b> (00_inputs, clipped from _data)<br>canals (reach, blocks needed), rivers, existing canal blocks<br>FEG 2017 protected function (landstatus)", INP)
ras = box(30, 381, 370, 46, "<b>Rasters</b> DTM (slope, lift) · peat depth model", INP)
cloud = box(30, 435, 370, 62, "<b>Cloud</b> (Planetary Computer)<br>Sentinel-2 L2A NDMI/NDVI, Aug-Oct median, 20 m<br>ESA WorldCover (forest) · JRC water seasonality", INP)
sit = box(30, 505, 370, 46, "<b>SiTMAT</b> stations 2026 (days deeper than 0.4 m, recession)", INP)
ner = box(30, 559, 370, 62, "<b>repeat-neraca</b><br>neraca_balance_unit.csv (P − ET, balance_stable_ok)<br>neraca_khg.csv (KHG deficit)", INP)
p1 = box(430, 199, 440, 104, "<b>1. Fire and canals per unit</b> (subkhg.national_layers → national.profile.build_profile)<br>burnt share per year and repeat burns, hotspots, this year's hotspots, canal km per km² by class; rates per km² of peat; held-out targets v_burned_frac, v_hotspot", PRO)
p2 = box(430, 311, 440, 150, "<b>2. Indicators on a 30 m grid</b> (common.indicators)<br>• NDMI, NDVI: median of Aug-Oct composites, mean over the years<br>• reach: share within 200 m of a canal (60 m on burnt land)<br>• missing blocks (IPG): 1 − existing / needed; spacing 0.4 m ÷ canal slope<br>• distance to dry-season water, lift above it (DTM)<br>• peat depth, forest share, protected share, SiTMAT", PRO)
p3 = box(430, 469, 440, 62, "<b>3. Merge neraca air</b> (extra_indicators): P − ET for the rank-sum water slot; empty where balance_stable_ok = 0", PRO)
p4 = box(430, 539, 440, 130, "<b>4. Score</b> (subkhg.prioritise)<br>• each indicator scaled 0-1 between its 5th and 95th percentile within the KHG, direction applied<br>• urgency U and stakes S: weighted means of the available indicators<br>• <b>need = 0.8 U + 0.2 S</b>; feasibility reported, not ranked<br>• classes: tertiles of need (tinggi, sedang, rendah)<br>• rank-sum (team's earlier method) computed alongside", PRO)
p5 = box(430, 677, 440, 118, "<b>5. Checks</b><br>• indicator pairs with Spearman above 0.8 flagged<br>• weight sensitivity: 300 Dirichlet draws around the weights<br>• held-out validation (scripts/validate_subkhg.py): indicators 2015-2018 → fire 2019; 2015-2022 → fire 2023; Spearman with bootstrap interval, against fire history alone", PRO)
par = box(920, 145, 590, 205, "<b>Weights</b> (provisional, not agreed with the team)<br>Urgency U: burnt share 2 · repeat burns 1 · hotspots 1 · hotspots this year 1 · NDMI 1 · canals primary 0.5, secondary 0.3, tertiary 0.2 · missing blocks 1.5 · reach 1.5 · distance to water 1 · forest share 1 (less forest, more need) · SiTMAT 1 + 1 (only with enough stations)<br>Stakes S: peat depth 2 · protected function 1<br>Weight 0: NDVI, neraca balance, single canal density (replaced by classes)<br>Reported only: lift, rates per area<br>An indicator is scored when at least min(20, n/2) units have a value", PAR)
o1 = box(920, 360, 350, 125, "<b>unit_prioritas.gpkg / .csv</b>: every indicator, normalised values, skor_urgensi, skor_dampak, skor_need, kelas, peringkat; rank-sum and its rank; sensitivity p_prioritas1<br><b>laporan.json</b>: weights, coverage, correlations, sensitivity, validation", OUT)
o2 = box(920, 495, 350, 62, "<b>subkhg_priority.csv</b>: unit_id, priority_rank, deficit_mm (KHG deficit), design_period_days", OUT)
o3 = box(920, 567, 350, 62, "<b>reports</b>: run report (subkhg.report), map page (subkhg.dashboard), validation (re-peat/reports/subkhg_validation.md)", OUT)
u1 = box(1280, 495, 230, 62, "<b>repeat-pump</b> (contract C6): canal blocks and pumping order", USE)
u2 = box(1280, 567, 230, 62, "<b>Team</b>: choice of sub-KHG, weights (AHP session)", USE)
box(920, 640, 590, 155, "<b>Validation, 2026-10-26</b> (Spearman with burned share in the test year, 26-30 units)<br>"
    "Kampar-Gaung 2019 / 2023: need 0.61 / 0.29 · urgency 0.57 / 0.30 · fire history alone 0.38 / 0.22 · rank-sum 0.66 / 0.47<br>"
    "Sugihan-Lumpur 2019 / 2023: need 0.37 / 0.17 · urgency 0.54 / 0.30 · fire history alone 0.64 / 0.36 · rank-sum 0.25 / 0.10<br>"
    "Intervals overlap: no score clearly better. Stakes lower the fire prediction by design; drainage indicators are not testable against fire. "
    "Weights need the team (AHP), with this as a check.", PAR)
edge(units, p1); edge(nat, p1); edge(units, p2); edge(site, p2); edge(ras, p2); edge(cloud, p2); edge(sit, p2); edge(ner, p3)
edge(p1, p4); edge(p2, p4); edge(p3, p4); edge(p4, p5); edge(par, p4, dashed=True); edge(p4, o1); edge(p4, o2); edge(p5, o3)
edge(o2, u1); edge(o3, u2)
# what changed
box(15, 820, 1510, 230, "What changed from the team's earlier method (slide 'Contoh Parameter Penentuan Prioritas Pembasahan dalam 1 KHG', Kahayan-Sebangau)", BAND)
old = box(30, 850, 470, 190, "<b>Earlier method (kept as the rank-sum)</b><br>• 8 indicators ranked, ranks summed, equal weights<br>• NDMI, NDVI, peat depth, water decline, water balance, deficit months, dry days, hotspot count<br>• climate indicators at 4-25 km, nearly constant inside a KHG<br>• no check against later fire", OLD)
new = box(520, 850, 990, 190, "<b>Now</b><br>• Need score: magnitudes scaled within the KHG, explicit weights, urgency and stakes separate, feasibility reported<br>• Fire and canals from the same national layers and code as the national profile, per km² of peat; repeat burns and this year's hotspots added; canals by class<br>• Drainage: canal reach and missing blocks (IPG metric) from the canal layer, DTM and existing blocks<br>• Climate: dry days and TerraClimate dropped (cannot separate sub-KHG); water balance from repeat-neraca, used only where its order is trustworthy<br>• NDMI at Sentinel-2's native 20 m; FEG protected function in the stakes<br>• Held-out validation on two El Nino years, compared with fire history alone", NEW)
edge(old, new, "extended")

xml = ('<mxfile host="repeat-prioritisation"><diagram id="subkhg" name="Sub-KHG prioritisation"><mxGraphModel dx="1600" dy="1100" grid="1" gridSize="10" guides="1" '
       'tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="1560" pageHeight="1080" background="#ffffff" math="0" shadow="0">'
       '<root><mxCell id="0"/><mxCell id="1" parent="0"/>' + "".join(cells) + "</root></mxGraphModel></diagram></mxfile>\n")
out = Path(__file__).with_name("subkhg_method.drawio")
out.write_text(xml, encoding="utf-8")
print(f"wrote {out} ({len(cells)} cells)")
