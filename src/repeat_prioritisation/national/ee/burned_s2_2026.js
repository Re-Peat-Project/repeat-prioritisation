/**
 * RE-PEAT: burned peat 2026 from Sentinel-2, Google Earth Engine Code Editor version.
 *
 * Same method as repeat_prioritisation.national.final_burned (config final.burned_s2), after Gaveau, Descals & Salim (2026),
 * PLOS One 21(4): e0331831, and KLHK's dNBR protocol:
 *   1. Sentinel-2 L2A harmonized, pixels with Cloud Score+ cs_cdf >= 0.6, NBR = (B8 - B12) / (B8 + B12).
 *   2. One composite per month: median NBR and 20th percentile NBR of the month's images (each image read once).
 *   3. Month m: before = median of the 3 previous monthly medians, after = 20th percentile of m, drop = before - after.
 *   4. Burned in m: drop > DNBR_MIN, after < POST_MAX, and a fire detection near it in m or the 3 months before
 *      (VIIRS S-NPP / NOAA-20 nominal or high within 500 m; MODIS FIRMS confidence >= 30 within 1 km).
 *   5. Year = union of the months; patches below 6.25 ha removed (KLHK minimum mapping unit).
 * The map layers are computed on the fly for KHG; the hectare totals come from the national run's stored tiles (33 of 106 finished).
 * Setting from the partial calibration against KLHK 2026 (2026-11-19): DNBR_MIN 0.20, POST_MAX -0.10.
 *
 * Paste into https://code.earthengine.google.com (project ee-danylaksono, or any project with read access to the two
 * repeat_burned_s2 assets below), set KHG, Run. The national tiles already computed are shown as a layer for comparison.
 */

// ---------------------------------------------------------------- settings
var KHG = 'KHG.61.11.01';              // KHG code (as in the dashboard); its KLH peat is analysed. 61.11.01 lies in a finished national tile
var YEAR = 2026;
var LAST_MONTH = 11;                   // months 1..LAST_MONTH of YEAR
var DNBR_MIN = 0.20;
var POST_MAX = -0.10;
var MIN_PATCH_HA = 6.25;
var SCALE = 20;
var ROOT = 'projects/ee-danylaksono/assets/repeat_burned_s2/';

// ---------------------------------------------------------------- inputs
var peatTable = ee.FeatureCollection(ROOT + 'peat_khg');            // KLH peat outline per KHG (property k = KHG code)
var aoi = peatTable.filter(ee.Filter.eq('k', KHG));
var peatMask = ee.Image(ROOT + 'peat_mask_30m').mask();              // 1 on KLH peat
var cs = ee.ImageCollection('GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED');
var s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(aoi).linkCollection(cs, ['cs_cdf']);

function nbr(img) {
  return img.normalizedDifference(['B8', 'B12']).rename('nbr')
            .updateMask(img.select('cs_cdf').gte(0.6).and(peatMask));
}

var viirs = ee.ImageCollection('NASA/LANCE/SNPP_VIIRS/C2').merge(ee.ImageCollection('NASA/LANCE/NOAA20_VIIRS/C2'));
var vProj = ee.ImageCollection('NASA/LANCE/NOAA20_VIIRS/C2').first().projection();
var firms = ee.ImageCollection('FIRMS');
var mProj = firms.first().projection();

function hot(a, b) {
  var v = viirs.filterDate(a, b).map(function (i) {
    return i.select('frp').mask().and(i.select('confidence').gte(1)).rename('h');
  }).max().unmask(0).setDefaultProjection(vProj).focalMax(500, 'circle', 'meters');
  var m = firms.filterDate(a, b).map(function (i) {
    return i.select('confidence').gte(30).unmask(0).rename('h');
  }).max().unmask(0).setDefaultProjection(mProj).focalMax(1000, 'circle', 'meters');
  return v.or(m);
}

// ---------------------------------------------------------------- monthly composites
var red = ee.Reducer.median().combine(ee.Reducer.percentile([20]), null, true);
var comp = {};
for (var k = -2; k <= LAST_MONTH; k++) {
  var d0 = ee.Date.fromYMD(YEAR, 1, 1).advance(k - 1, 'month');
  var c = s2.filterDate(d0, d0.advance(1, 'month')).map(nbr).reduce(red);
  comp[k] = {med: c.select(0), low: c.select(1)};
}

// ---------------------------------------------------------------- monthly test, union over the year
var best = ee.Image(-1);
var month = ee.Image(0);                // month of the largest qualifying drop
for (var m = 1; m <= LAST_MONTH; m++) {
  var start = ee.Date.fromYMD(YEAR, m, 1);
  var pre = ee.ImageCollection([comp[m - 1].med, comp[m - 2].med, comp[m - 3].med]).median();
  var post = comp[m].low;
  var drop = pre.subtract(post);
  var ok = drop.updateMask(post.lt(POST_MAX).and(hot(start.advance(-3, 'month'), start.advance(1, 'month'))));
  var bm = ok.gt(DNBR_MIN).unmask(0);
  var better = ok.unmask(-1).gt(best);
  month = month.where(better.and(bm), m);
  best = best.max(ok.unmask(-1));
}
var npx = Math.ceil(MIN_PATCH_HA * 1e4 / (SCALE * SCALE));
var burned = best.gt(DNBR_MIN).selfMask().reproject({crs: 'EPSG:4326', scale: SCALE});   // fixed 20 m grid, so patch sizes do not depend on the zoom
burned = burned.updateMask(burned.connectedPixelCount(npx + 1, true).gte(npx));

// ---------------------------------------------------------------- numbers (from the stored national tiles: cheap)
// The on-the-fly layers below are drawn tile by tile as you pan; summing them over a whole KHG interactively usually times
// out, so the totals come from the national run's stored tiles where the KHG is covered.
var tiles = ee.data.listAssets(ROOT.replace(/\/$/, '')).assets
  .filter(function (a) { return a.type === 'IMAGE' && a.id.indexOf('a2026m11_') >= 0; })
  .map(function (a) { return ee.Image(a.id); });
var nat = ee.ImageCollection(tiles).mosaic();
var natBurned = nat.select('d_m10').gt(DNBR_MIN * 1000).selfMask().reproject({crs: 'EPSG:4326', scale: SCALE});
natBurned = natBurned.updateMask(natBurned.connectedPixelCount(npx + 1, true).gte(npx));
var area = ee.Image.pixelArea().divide(1e4);
var stats = area.updateMask(natBurned).rename('burned_ha')
  .addBands(area.updateMask(nat.select('obs').mask()).rename('peat_ha_covered'))
  .addBands(area.updateMask(peatMask).rename('peat_ha'))
  .reduceRegion({reducer: ee.Reducer.sum(), geometry: aoi.geometry(), scale: SCALE, maxPixels: 1e10, tileScale: 8});
print('Burned peat ' + YEAR + ' (national run tiles), ' + KHG + ' (ha; peat_ha_covered < peat_ha means partly computed)', stats);

// ---------------------------------------------------------------- map
var fc = function (a, b) {
  return ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(aoi).filterDate(a, b).linkCollection(cs, ['cs_cdf'])
    .map(function (i) { return i.updateMask(i.select('cs_cdf').gte(0.6)); }).median();
};
var vis = {bands: ['B12', 'B8', 'B4'], min: 0, max: 4000};
Map.centerObject(aoi, 10);
Map.addLayer(fc(YEAR + '-05-01', YEAR + '-07-01'), vis, 'Sentinel-2 May-June (SWIR-NIR-red)', false);
Map.addLayer(fc(YEAR + '-09-01', YEAR + '-11-01'), vis, 'Sentinel-2 September-October (SWIR-NIR-red)', true);
Map.addLayer(best.updateMask(best.gt(0)).clip(aoi), {min: 0, max: 0.8, palette: ['ffffcc', 'fd8d3c', 'bd0026']}, 'Largest NBR drop (with fire detection)', false);
Map.addLayer(month.updateMask(burned).clip(aoi), {min: 1, max: LAST_MONTH, palette: ['2c7bb6', 'abd9e9', 'ffffbf', 'fdae61', 'd7191c']}, 'Month burned', false);
Map.addLayer(burned.clip(aoi), {palette: ['e31a1c']}, 'Burned peat ' + YEAR, true);
Map.addLayer(ee.Image().byte().paint(aoi, 1, 2), {palette: ['000000']}, 'KLH peat outline', true);
Map.addLayer(viirs.filterDate(YEAR + '-01-01', YEAR + '-12-31').map(function (i) { return i.select('frp').mask().selfMask(); }).max(),
             {palette: ['ffff00']}, 'VIIRS fire detections ' + YEAR, false);
Map.addLayer(natBurned, {palette: ['ff00ff']}, 'Burned peat, national run (finished tiles only)', false);
