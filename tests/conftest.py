import numpy as np
import pandas as pd
from collections import OrderedDict
from datetime import date, datetime, timedelta, timezone
from osgeo import ogr
from os.path import dirname
from shapely.geometry import Point

from geotable import GeoRow, GeoTable
from geotable.projections import LONGITUDE_LATITUDE_PROJ4
from pytest import fixture


@fixture
def geotable():
    return GEOTABLE.copy()


@fixture
def georow():
    return GEOROW.copy()


def prepare_feature(name_type_value_packs):
    feature_definition = ogr.FeatureDefn()
    for field_name, field_type, field_value in name_type_value_packs:
        field_definition = ogr.FieldDefn(field_name, field_type)
        feature_definition.AddFieldDefn(field_definition)

    feature = ogr.Feature(feature_definition)
    for field_index, (
        field_name, field_type, field_value,
    ) in enumerate(name_type_value_packs):
        feature.SetField2(field_index, field_value)

    field_type_by_name = OrderedDict()
    field_values = []
    for field_name, field_type, field_value in name_type_value_packs:
        field_type_by_name[field_name] = field_type
        field_values.append(field_value)
    return feature, field_type_by_name, tuple(field_values)


FOLDER = dirname(__file__)
TIMEZONE = timezone(timedelta(hours=1))
GEOTABLE = GeoTable(pd.DataFrame([{
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
    'geometry_proj4': LONGITUDE_LATITUDE_PROJ4,
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
GEOROW = GeoRow({
    'geometry_object': Point(-71.10973349999999, 42.3736158),
    'geometry_proj4': LONGITUDE_LATITUDE_PROJ4,
})
