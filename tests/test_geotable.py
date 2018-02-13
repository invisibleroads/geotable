from geotable import GeoTable
from geotable.exceptions import GeoTableError
from os.path import join
from pytest import raises

from conftest import FOLDER


class TestGeoTable(object):

    def test_load_utm_proj4(self):
        assert GeoTable.load_utm_proj4(join(FOLDER, 'shp.zip')) == (
            '+proj=utm +zone=17 +ellps=WGS84 +datum=WGS84 +units=m +no_defs')

    def test_load(self):
        t = GeoTable.load(join(FOLDER, 'shp', 'a.shp'))
        assert t['date'].dtype.name == 'datetime64[ns]'

        t = GeoTable.load(join(FOLDER, 'csv', 'a.csv'), parse_dates=['date'])
        assert t['date'].dtype.name == 'datetime64[ns]'

        with raises(GeoTableError):
            GeoTable.load(join(FOLDER, 'conftest.py'))

        t = GeoTable.load(join(FOLDER, 'csv.zip'), parse_dates=['date'])
        assert t['date'].dtype.name == 'datetime64[ns]'

    def test_to_shp(self, geotable, tmpdir):
        target_path = str(tmpdir.join('x.zip'))
        geotable.to_shp(target_path)
        t = GeoTable.load(target_path)
        assert t['float16'].dtype.name == 'float64'
        assert t['float32'].dtype.name == 'float64'
        assert t['float64'].dtype.name == 'float64'
        assert t['float_nan'].dtype.name == 'float64'
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
