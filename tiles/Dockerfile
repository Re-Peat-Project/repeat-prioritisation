# tippecanoe, pinned, for repeat-national-tiles (GeoJSON lines to a PMTiles archive)
FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends build-essential git ca-certificates libsqlite3-dev zlib1g-dev \
 && git clone --depth 1 --branch 2.79.0 https://github.com/felt/tippecanoe /src \
 && make -C /src -j4 && make -C /src install \
 && apt-get purge -y build-essential git && apt-get autoremove -y && rm -rf /src /var/lib/apt/lists/*
ENTRYPOINT ["tippecanoe"]
