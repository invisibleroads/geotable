from geotable import GeoTable
from geotable.exceptions import GeoTableError
from os.path import join
from pytest import raises

from conftest import FOLDER


UTM_PROJ4 = '+proj=utm +zone=17 +ellps=WGS84 +datum=WGS84 +units=m +no_defs'


class TestGeoTable(object):

    def test_load_utm_proj4(self):
        assert GeoTable.load_utm_proj4(join(FOLDER, 'shp.zip')) == UTM_PROJ4

    def test_load(self):
        t = GeoTable.load(join(FOLDER, 'shp', 'a.shp'))
        assert t['date'].dtype.name == 'datetime64[ns]'

        t = GeoTable.load(join(FOLDER, 'csv', 'a.csv'), parse_dates=['date'])
        assert t['date'].dtype.name == 'datetime64[ns]'

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

        p.write('x\n0')
        with raises(GeoTableError):
            GeoTable.from_csv(str(p))

        p.write('wkt\nx')
        with raises(GeoTableError):
            GeoTable.from_csv(str(p))

        GeoTable.from_csv(join(FOLDER, 'csv', 'd.csv'))

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

        target_path = str(tmpdir.join('x.zip'))
        geotable.to_csv(target_path)

    def test_to_gdal(self, geotable, tmpdir):
        target_path = str(tmpdir.join('x.zip'))
        with raises(GeoTableError):
            geotable.to_gdal(target_path, driver_name='x')
