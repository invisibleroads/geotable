from geotable import ColorfulGeometryCollection, GeoRow, GeoTable
from geotable.exceptions import EmptyGeoTableError, GeoTableError
from geotable.projections import normalize_proj4, LONGITUDE_LATITUDE_PROJ4
from os.path import join
from pytest import raises
from shapely.geometry import Point, LineString, Polygon

from conftest import FOLDER


UTM_PROJ4 = '+proj=utm +zone=17 +ellps=WGS84 +datum=WGS84 +units=m +no_defs'


class TestGeoTable(object):

    def test_load_utm_proj4(self):
        assert GeoTable.load_utm_proj4(join(FOLDER, 'shp.zip')) == UTM_PROJ4

    def test_load(self):
        t = GeoTable.load(join(FOLDER, 'shp', 'a.shp'))
        assert t['date'].dtype.name == 'datetime64[ns]'

        t = GeoTable.load(join(FOLDER, 'csv', 'lat_lon.csv'))
        assert t.iloc[0]['geometry_object'].x == -83.7430378

        t = GeoTable.load(join(FOLDER, 'csv', 'latitude_longitude.csv'))
        assert t.iloc[0]['geometry_object'].x == -91.5305465

        t = GeoTable.load(join(FOLDER, 'csv', 'latitude_longitude_wkt.csv'))
        assert t.iloc[0]['geometry_object'].x == -71.10973349999999

        t = GeoTable.load(join(FOLDER, 'csv', 'longitude_latitude_wkt.csv'))
        assert t.iloc[0]['geometry_object'].x == -71.10973349999999

        t = GeoTable.load(join(FOLDER, 'csv', 'wkt.csv'), parse_dates=['date'])
        assert t['date'].dtype.name == 'datetime64[ns]'
        assert t.iloc[0]['geometry_object'].type == 'Point'

        with raises(GeoTableError):
            GeoTable.load(join(FOLDER, 'conftest.py'))

        t = GeoTable.load(join(FOLDER, 'csv.zip'), parse_dates=['date'])
        assert t['date'].dtype.name == 'datetime64[ns]'

    def test_from_shp(self):
        with raises(GeoTableError):
            GeoTable.from_shp(join(FOLDER, 'conftest.py'))
        t = GeoTable.from_shp(join(
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
            join(FOLDER, 'csv', 'proj4_from_row.csv'),
            target_proj4=LONGITUDE_LATITUDE_PROJ4)
        assert type(t.iloc[0]['geometry_object']) == LineString
        assert type(t.iloc[1]['geometry_object']) == Polygon

        t = GeoTable.from_csv(join(FOLDER, 'csv', 'proj4_from_file.csv'))
        assert t.iloc[0]['geometry_proj4'] == normalize_proj4(open(join(
            FOLDER, 'csv', 'proj4_from_file.proj4')).read())

    def test_to_shp(self, geotable, tmpdir):
        target_path = str(tmpdir.join('x.shp'))
        with raises(GeoTableError):
            geotable.to_shp(target_path)

        target_path = str(tmpdir.join('x.zip'))
        geotable.to_shp(target_path)

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

    def test_to_csv(self, geotable, tmpdir):
        target_path = str(tmpdir.join('x.csv'))
        geotable.to_csv(target_path)
        t = GeoTable.load(target_path)
        assert t['bool'].dtype.name == 'bool'

        target_path = str(tmpdir.join('x.zip'))
        geotable.to_csv(target_path)
        t = GeoTable.load(target_path)
        assert t['int64'].dtype.name == 'int64'

    def test_to_gdal(self, geotable, tmpdir):
        target_path = str(tmpdir.join('x.zip'))
        with raises(GeoTableError):
            geotable.to_gdal(target_path, driver_name='x')

    def test_draw(self, geotable):
        colorful_geometry_collection = geotable.draw()
        assert 'circle' in colorful_geometry_collection.svg()

    def test_constructor_sliced(self, geotable):
        georow = geotable.iloc[0]
        assert type(georow) == GeoRow
        assert georow['category'] == 'vegetable'


class TestGeoRow(object):

    def test_constructor(self, geotable):
        georow = geotable.iloc[0].copy()
        assert type(georow) == GeoRow
        assert georow['category'] == 'vegetable'

    def test_constructor_expanddim(self, georow):
        assert type(georow.to_frame()) == GeoTable

    def test_draw(self, georow):
        geometry = georow.draw()
        assert 'circle' in geometry.svg()


class TestColorfulGeometryCollection(object):

    def test_svg(self):
        assert ColorfulGeometryCollection().svg() == '<g />'
        assert 'circle' in ColorfulGeometryCollection([Point(0, 0)]).svg()
