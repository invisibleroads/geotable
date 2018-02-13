import numpy as np
from datetime import date, datetime, timedelta, timezone
from os.path import dirname
from pandas import DataFrame
from shapely.geometry import Point

from geotable import GeoTable
from geotable.macros import LONLAT_PROJ4
from pytest import fixture


@fixture
def geotable():
    return GEOTABLE.copy()


FOLDER = dirname(__file__)
TIMEZONE = timezone(timedelta(hours=1))
GEOTABLE = GeoTable(DataFrame([{
    'float16': 0.1,
    'float32': 0.1,
    'float64': 0.1,
    'float_nan': np.nan,
    'int8': 1,
    'int16': 1,
    'int32': 1,
    'int64': 1,
    'bool': True,
    'dt': datetime(2000, 1, 1, 1, 0),
    'dt_tz': datetime(2000, 1, 1, 1, 0).astimezone(TIMEZONE),
    'timedelta': datetime(2000, 1, 1, 1, 0) - datetime(2000, 1, 1, 0, 0),
    'category': 'vegetable',
    'object_dt': date(2000, 1, 1),
    'object_st': 'whee',
    'geometry_object': Point(0, 0),
    'geometry_layer': 'layer_name',
    'geometry_proj4': LONLAT_PROJ4,
}]).astype({
    'float16': 'float16',
    'float32': 'float32',
    'float64': 'float64',
    'float_nan': 'float64',
    'int8': 'int8',
    'int16': 'int16',
    'int32': 'int32',
    'int64': 'int64',
    'bool': 'bool',
    'category': 'category',
}))
