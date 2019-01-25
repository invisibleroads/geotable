import pandas as pd
from geotable import (
    ColorfulGeometryCollection,
    GeoRow,
    GeoTable,
    define_load_with_utm_proj4,
    load,
    load_utm_proj4)
from geotable.exceptions import EmptyGeoTableError, GeoTableError
from geotable.projections import (
    normalize_proj4, LONGITUDE_LATITUDE_PROJ4, SPHERICAL_MERCATOR_PROJ4)
from invisibleroads_macros.disk import replace_file_extension, uncompress
from os.path import exists, join
from pytest import raises
from shapely.geometry import Point, LineString, Polygon

from conftest import FOLDER


UTM_PROJ4 = '+proj=utm +zone=17 +ellps=WGS84 +datum=WGS84 +units=m +no_defs'


class TestGeoTable(object):

    def test_define_load_with_utm_proj4(self):
        source_path = join(FOLDER, 'xyz.kmz')
        load_with_utm_proj4 = define_load_with_utm_proj4(source_path)
        proj4 = load_utm_proj4(source_path)
        t1 = load_with_utm_proj4(source_path)
        t2 = load(source_path)
        t3 = load(source_path, target_proj4=proj4)
        assert t1.geometries[0].wkt != t2.geometries[0].wkt
        assert t1.geometries[0].wkt == t3.geometries[0].wkt

    def test_load_utm_proj4(self):
        assert load_utm_proj4(join(FOLDER, 'xyz.kmz')) == UTM_PROJ4
        assert GeoTable.load_utm_proj4(join(FOLDER, 'shp.zip')) == UTM_PROJ4

    def test_load(self, tmpdir):
        t = load(join(FOLDER, 'xyz.kmz'))
        assert len(t.iloc[0]['geometry_object'].coords[0]) == 3
        assert len(t) == 3

        t = load(join(FOLDER, 'xyz.kmz'), drop_z=True, bounding_box=(
            -83.743038, 42.280826, -83.743037, 42.280825))
        assert len(t.iloc[0]['geometry_object'].coords[0]) == 2
        assert len(t) == 1

        t = GeoTable.load(join(FOLDER, 'shp', 'a.shp'))
        assert t['date'].dtype.name == 'datetime64[ns]'

        t = GeoTable.load(join(FOLDER, 'csv', 'lat-lon.csv'))
        assert t.iloc[0]['geometry_object'].x == -83.7430378

        t = GeoTable.load(join(FOLDER, 'csv', 'latitude-longitude.csv'))
        assert t.iloc[0]['geometry_object'].x == -91.5305465

        t = GeoTable.load(join(FOLDER, 'csv', 'latitude-longitude-wkt.csv'))
        assert t.iloc[0]['geometry_object'].x == -71.10973349999999

        t = GeoTable.load(join(FOLDER, 'csv', 'longitude-latitude-wkt.csv'))
        assert t.iloc[0]['geometry_object'].x == -71.10973349999999

        t = GeoTable.load(join(FOLDER, 'csv', 'wkt.csv'), parse_dates=['date'])
        assert t['date'].dtype.name == 'datetime64[ns]'
        assert t.iloc[0]['geometry_object'].type == 'Point'

        t = GeoTable.load(join(FOLDER, 'csv.zip'), parse_dates=['date'])
        assert t['date'].dtype.name == 'datetime64[ns]'

        x_folder = uncompress(join(FOLDER, 'csv.zip'), tmpdir.join('csv'))
        t = GeoTable.load(x_folder)
        assert len(t) > 1

        x_path_object = tmpdir.join('x.txt')
        x_path_object.write('x')
        x_path = str(x_path_object)
        with raises(GeoTableError):
            GeoTable.load(x_path)

        t = GeoTable.load(join(FOLDER, 'csv-bad.tar.gz'))
        assert len(t) == 1
        t = GeoTable.load(join(FOLDER, 'shp-bad.tar.gz'))
        assert len(t) == 2

        t = GeoTable.load(
            'https://data.cityofnewyork.us/api/geospatial/tqmj-j8zm'
            '?method=export&format=Original')
        assert len(t) == 5

    def test_drop_duplicate_geometries(self):
        t = GeoTable.from_records([
            (0, 0),
            (0, 0),
            (0, 1),
            (1, 2),
        ], columns=['lon', 'lat'])
        assert len(t) == 4
        assert len(t.drop_duplicate_geometries()) == 3
        assert len(t) == 4
        assert len(t.drop_duplicate_geometries(inplace=True)) == 3
        assert len(t) == 3

    def test_from_records(self):
        geometry = Point(0, 0)

        t = GeoTable.from_records([(0, 0)], columns=['lon', 'lat'])
        assert t.iloc[0]['geometry_object'] == geometry

        t = GeoTable.from_records([(geometry.wkt,)], columns=['wkt'])
        assert t.iloc[0]['geometry_object'] == geometry

        t = GeoTable.from_records(pd.DataFrame())
        assert 'geometry_object' in t.columns

    def test_from_gdal(self):
        with raises(GeoTableError):
            GeoTable.from_gdal(join(FOLDER, 'conftest.py'))
        t = GeoTable.from_gdal(join(
            FOLDER, 'shp', 'b.shp'), target_proj4=UTM_PROJ4)
        assert t.iloc[0]['geometry_object'].x == -638500.4251527891

    def test_from_csv(self, tmpdir):
        p = tmpdir.join('x.csv')

        p.write('')
        with raises(EmptyGeoTableError):
            GeoTable.from_csv(str(p))

        p.write('x\n0')
        with raises(GeoTableError):
            GeoTable.from_csv(str(p))

        p.write('wkt\nx')
        with raises(GeoTableError):
            GeoTable.from_csv(str(p))

        t = GeoTable.from_csv(
            join(FOLDER, 'csv', 'proj4-from-row.csv'),
            target_proj4=LONGITUDE_LATITUDE_PROJ4)
        assert type(t.iloc[0]['geometry_object']) == LineString
        assert type(t.iloc[1]['geometry_object']) == Polygon

        t = GeoTable.from_csv(join(FOLDER, 'csv', 'proj4-from-file.csv'))
        assert t.iloc[0]['geometry_proj4'] == normalize_proj4(open(join(
            FOLDER, 'csv', 'proj4-from-file.proj4')).read())

    def test_save_geojson(self, geotable, tmpdir):
        target_path = str(tmpdir.join('x.geojson'))
        geotable.save_geojson(target_path)

        t = GeoTable.load(target_path)
        assert len(t) == 1

    def test_save_kml(self, geotable, tmpdir):
        target_path = str(tmpdir.join('x.kml'))
        geotable.save_kmz(target_path)

        t = GeoTable.load(target_path)
        assert len(t) == 1

    def test_save_kmz(self, geotable, tmpdir):
        target_path = str(tmpdir.join('x.kmz'))
        geotable.save_kmz(target_path)

        t = GeoTable.load(target_path)
        assert len(t) == 1

    def test_save_shp(self, geotable, tmpdir):
        target_path = str(tmpdir.join('x.shp'))
        with raises(GeoTableError):
            geotable.save_shp(target_path)

        target_path = str(tmpdir.join('x.zip'))
        geotable.save_shp(target_path)

        t = GeoTable.load(target_path)
        assert t['float16'].dtype.name == 'float64'
        assert t['float32'].dtype.name == 'float64'
        assert t['float64'].dtype.name == 'float64'
        assert 'float_nan' not in t
        assert t['int8'].dtype.name == 'int64'
        assert t['int16'].dtype.name == 'int64'
        assert t['int32'].dtype.name == 'int64'
        assert t['int64'].dtype.name == 'int64'
        assert t['bool'].dtype.name == 'int64'
        assert t['dt'].dtype.name == 'datetime64[ns]'
        assert t['dt_tz'].dtype.name == 'datetime64[ns]'
        assert t['timedelta'].dtype.name == 'object'
        assert t['category'].dtype.name == 'object'
        assert t['object_dt'].dtype.name == 'object'
        assert t['object_st'].dtype.name == 'object'

        t = GeoTable([
            ('POINT (0 0)',),
            ('LINESTRING (0 0, 1 1)',),
        ], columns=['wkt'])
        with raises(GeoTableError):
            t.save_shp(target_path)

        GeoTable().save_shp(target_path)
        t = GeoTable.load(target_path)
        assert len(t) == 0

    def test_save_csv(self, geotable, tmpdir):
        target_path = str(tmpdir.join('x.csv'))
        geotable.save_csv(target_path)
        t = GeoTable.load(target_path)
        proj4_path = replace_file_extension(target_path, '.proj4')
        assert t['bool'].dtype.name == 'bool'
        assert not exists(proj4_path)
        geotable.save_csv(target_path, target_proj4=SPHERICAL_MERCATOR_PROJ4)
        assert open(proj4_path).read() == SPHERICAL_MERCATOR_PROJ4

        target_path = str(tmpdir.join('x.zip'))
        geotable.save_csv(target_path)
        t = GeoTable.load(target_path)
        assert t['int64'].dtype.name == 'int64'

        GeoTable().save_csv(target_path)
        t = GeoTable.load(target_path)
        assert len(t) == 0

    def test_to_gdal(self, geotable, tmpdir):
        target_path = str(tmpdir.join('x.zip'))
        with raises(GeoTableError):
            geotable.to_gdal(target_path, driver_name='x')

    def test_draw(self, geotable):
        svg = geotable.draw().svg()
        assert 'circle' in svg

        t = GeoTable.load(join(FOLDER, 'csv', 'wkt.csv'))
        svg = t.draw().svg()
        assert 'circle' in svg
        assert 'polyline' in svg
        assert 'path' in svg

    def test_constructor_sliced(self, geotable):
        georow = geotable.iloc[0]
        assert type(georow) == GeoRow
        assert georow['category'] == 'vegetable'

    def test_na_values(self):
        t = GeoTable.from_records([
            (0, 0),
            (None, None),
            (0, 1),
            (1, 2),
        ], columns=['lon', 'lat'])
        assert len(t) == 3


class TestGeoRow(object):

    def test_constructor(self, geotable):
        georow = geotable.iloc[0].copy()
        assert type(georow) == GeoRow
        assert georow['category'] == 'vegetable'

    def test_constructor_expanddim(self, georow):
        assert type(georow.to_frame()) == GeoTable

    def test_draw(self, georow):
        svg = georow.draw().svg()
        assert 'circle' in svg


class TestColorfulGeometryCollection(object):

    def test_svg(self):
        assert ColorfulGeometryCollection().svg() == '<g />'
        assert 'circle' in ColorfulGeometryCollection([Point(0, 0)]).svg()
