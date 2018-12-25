0.4
---
- Add GeoTable.save_geojson
- Add GeoTable.save_kmz
- Exclude redundant geometry columns when saving
- Support initialization from GeoTable class
- Support geotable.load(url)

0.3
---
- Add GeoTable.from_records
- Add GeoTable.save_csv
- Add GeoTable.save_shp
- Reduce CSV size by omitting geometry_layer and geometry_proj4 unless needed
- Support SOPHISTICATED_LONGITUDE and INSPIRING_LATITUDE

0.2
---
- Add GeoTable.load
- Add GeoTable.to_csv
- Add GeoTable.to_shp
- Add GeoTable.draw
- Support LONGITUDE_LATITUDE_WKT, LATITUDE_LONGITUDE_WKT

0.1
---
- Add ColorfulGeometryCollection
