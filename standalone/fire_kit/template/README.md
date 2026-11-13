# Kebakaran lahan menurut status lahan

Menghitung luas area terbakar dan jumlah titik panas di Indonesia menurut status lahan: konsesi (izin usaha), fungsi kawasan hutan, desa DMPG dan gambut. Hasilnya berupa tabel (CSV dan Excel), layer untuk QGIS, dan kamus kolom.

Paket ini berisi kode saja. Data masukan disiapkan sendiri (lihat bagian Data).

## Kebutuhan

- Windows 64-bit dengan Python 3.11, 3.12 atau 3.13 (64-bit, dari python.org; saat memasang centang "Add python.exe to PATH").
- Ruang disk sekitar 1,5 GB untuk hasil, di luar data masukan.
- Internet hanya saat pemasangan.

## Langkah

1. Ekstrak zip ini ke sebuah folder, misalnya `D:\kebakaran_lahan`.
2. Klik dua kali `pasang.bat` (sekali saja). Skrip ini membuat folder `.venv` dan memasang pustaka Python.
3. Salin data masukan ke folder `data` (atau tulis lokasi lengkapnya di `config.yaml`).
4. Buka `config.yaml` dengan Notepad. Sesuaikan nama file, tahun (`years`) dan, bila perlu, filter gambut (`peat_where`).
5. Periksa data: buka Command Prompt di folder ini lalu jalankan `jalankan.bat --steps check`. Skrip memeriksa setiap file dan kolom yang dibutuhkan, lalu berhenti dengan pesan yang jelas bila ada yang kurang.
6. Uji satu provinsi: `jalankan.bat --province Riau` (nama provinsi seperti tertulis di kolom PROV_2023).
7. Seluruh Indonesia: `jalankan.bat` (atau klik dua kali).

Waktu proses di komputer pengembang (4 proses paralel): Riau sekitar 4 menit, seluruh Indonesia (1.250 petak) sekitar 1 sampai 1,5 jam. Komputer yang lebih lemah butuh lebih lama.

Proses dibagi menjadi petak 90 km yang disimpan satu per satu di `hasil/fire_landstatus/cache`. Bila proses terhenti, jalankan lagi dan petak yang sudah selesai tidak dihitung ulang. **Bila data masukan diganti, jalankan dengan `--force`** (atau hapus folder `cache`), karena petak lama tidak tahu bahwa datanya berubah.

Pilihan lain: `--workers 2` (lebih sedikit proses paralel bila memori kurang; bawaan 4), `--no-rasters` (tanpa raster 30 m), `--steps tables export` (membuat ulang tabel dan paket dari hitungan terakhir), `--bbox BUJUR0 LINTANG0 BUJUR1 LINTANG1` (kotak tertentu).

## Data

| Kunci di config.yaml | Isi | Kolom yang dibaca |
|---|---|---|
| `villages` | Batas desa 2023: daratan, provinsi, kabupaten | PULAU, PROV_2023, KABKO_2023 |
| `khg` | Batas KHG | NAMA_KHG (kode KHG dari `khg_registry.csv`, dicocokkan dengan nama) |
| `forest_area` | Fungsi kawasan hutan | Fungsi (CA, SM, TN, TWA, TAHURA, HL, HP, HPT, HPK, APL, TUBUH AIR, ...) |
| `licences` | Izin usaha | IZIN_USAHA (Perkebunan Kelapa Sawit, Pertambangan, PBPH, PPHTR, PPHKM) |
| `dmpg` | Desa DMPG | hanya poligon (layer `dmpg_layer`) |
| `burned` | Area terbakar | BA_<tahun> untuk setiap tahun di `years`, terisi bila poligon terbakar pada tahun itu |
| `peat` | Gambut: poligon (misalnya file analisis integrasi PPEG dengan `peat_where`) atau raster 0/1 | sesuai `peat_where` |
| `modis` | Titik panas MODIS tahun berjalan | acq_date, dan confidence 0-100 (format FIRMS) atau level low/medium/high (atau rendah/sedang/tinggi); month dipakai bila ada |
| `viirs` | Titik panas VIIRS S-NPP semua tahun (FIRMS) | acq_date, confidence (l/n/h), type pada file pertama |

Nama kolom file MODIS tidak peka huruf besar-kecil; file VIIRS memakai nama kolom FIRMS (huruf kecil). Titik panas FIRMS dapat diunduh dari firms.modaps.eosdis.nasa.gov (arsip negara untuk tahun lalu, API area untuk tahun berjalan).

## Hasil

Di `hasil/`:

- `fire_landstatus/tables/t_*.csv`: tabel ringkasan (nasional, pulau, provinsi, KHG, jenis konsesi, konsesi × kawasan hutan, fungsi kawasan, DMPG, frekuensi terbakar, titik panas per tahun dan per bulan). Setiap tabel memberi baris `basis = all` (seluruh daratan) dan `basis = peat` (gambut saja).
- `fire_landstatus/checks.csv`: total yang harus cocok (tabel terhadap total nasional, grid terhadap luas poligon, titik panas terhadap file). Periksa kolom `diff`.
- `fire_landstatus/layers/`: `summary.gpkg` (provinsi dan KHG), `hotspots_<tahun>.gpkg` (setiap titik panas tahun berjalan dengan kelasnya), `status.vrt` (raster 30 m: kawasan, konsesi, DMPG, gambut, KHG, frekuensi dan tahun terbakar). Penjelasan band di `layers/README.md`.
- `paket_kebakaran_lahan_<tanggal>.zip`: semua di atas dalam satu folder, ditambah `fire_tables.xlsx` (satu sheet per tabel) dan `README.md` dengan kamus kolom.

## Metode singkat

Indonesia dibagi menjadi grid sel 30 m dengan luas sama (EPSG:6933). Setiap layer dirasterkan pada grid itu (sel mengambil nilai poligon yang memuat titik tengahnya). Sel dengan kombinasi kelas yang sama dijumlahkan. Izin yang tumpang tindih disimpan per jenis; untuk tabel konsesi, sel mengambil jenis pertama dalam urutan sawit, tambang, PPHTR, PBPH. PPHKM bukan konsesi. Kawasan hutan yang tumpang tindih mengambil kelas pertama dalam urutan konservasi, lindung, produksi, HPK, APL, lainnya. Titik panas mengambil kelas sel tempatnya jatuh. Bawaan tabel: kepercayaan sedang dan tinggi; titik panas dalam radius `static_radius_m` dari deteksi VIIRS bertipe gunung api, sumber panas statis atau lepas pantai ditandai `static` dan dipisahkan. Perbandingan antar tahun memakai bagian tahun yang sama (1 Januari sampai tanggal terakhir VIIRS tahun berjalan, kolom `_ytd`).

---

## English

Burned area and hotspots by land status (concession, forest area function, DMPG village, peat) on a 30 m equal-area grid. Install once with `pasang.bat` (Python 3.11-3.13, 64-bit), put the inputs in `data/`, edit `config.yaml`, then run `jalankan.bat --steps check`, `jalankan.bat --province Riau` (test) and `jalankan.bat` (all of Indonesia). Tiles are cached, so an interrupted run resumes; after changing an input, run with `--force`. Results: `hasil/fire_landstatus/` (tables, checks, layers) and `hasil/paket_kebakaran_lahan_<date>.zip` (the same with an Excel workbook and a data dictionary).
