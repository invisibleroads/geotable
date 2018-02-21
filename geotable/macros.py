import numpy as np
from collections import OrderedDict
from datetime import datetime
from invisibleroads_macros.disk import replace_file_extension
from invisibleroads_macros.geometry import flip_xy, transform_geometries
from invisibleroads_macros.log import get_log
from invisibleroads_macros.text import unicode_safely
from os.path import exists
from osgeo import ogr
from shapely import geometry, wkb, wkt
from shapely.errors import WKTReadingError

from .exceptions import GeoTableError
from .projections import (
    _get_spatial_reference_from_proj4,
    get_transform_shapely_geometry,
    normalize_proj4,
    LONGITUDE_LATITUDE_PROJ4)


L = get_log(__file__)


def _get_field_definitions(geotable):
    field_definitions = []
    for field_name in geotable.field_names:
        dtype_name = geotable[field_name].dtype.name
        if dtype_name in ('bool', 'int8', 'int16', 'int32'):
            field_type = ogr.OFTInteger
        elif dtype_name.startswith('int'):
            field_type = ogr.OFTInteger64
        elif dtype_name.startswith('float'):
            field_type = ogr.OFTReal
        elif dtype_name.startswith('date'):
            field_type = ogr.OFTDate
        elif dtype_name in ('object', 'category'):
            field_type = ogr.OFTString
        else:
            L.warning('dtype not supported (%s)' % dtype_name)
            field_type = ogr.OFTString
        field_definitions.append(ogr.FieldDefn(field_name, field_type))
    return field_definitions


def _get_field_type_by_name(gdal_layer):
    field_type_by_name = OrderedDict()
    gdal_layer_definition = gdal_layer.GetLayerDefn()
    for field_index in range(gdal_layer_definition.GetFieldCount()):
        field_definition = gdal_layer_definition.GetFieldDefn(field_index)
        field_name = field_definition.GetName()
        field_type = field_definition.GetType()
        field_type_by_name[field_name] = field_type
    return field_type_by_name


def _get_geometry_columns(table):
    column_names = table.columns
    for column_name in column_names:
        normalized_column_name = _normalize_column_name(column_name)
        if normalized_column_name == 'wkt':
            return [column_name]
        if normalized_column_name == 'longitudelatitudewkt':
            return [column_name]
        if normalized_column_name == 'latitudelongitudewkt':
            return [column_name]

    paired_columns = _get_paired_columns(
        column_names, lambda _: _ == 'longitude', lambda _: _ == 'latitude')
    if paired_columns:
        return paired_columns

    paired_columns = _get_paired_columns(
        column_names,
        lambda _: _.endswith('longitude'),
        lambda _: _.endswith('latitude'))
    if paired_columns:
        return paired_columns

    paired_columns = _get_paired_columns(
        column_names, lambda _: _ == 'lon', lambda _: _ == 'lat')
    if paired_columns:
        return paired_columns

    paired_columns = _get_paired_columns(
        column_names, lambda _: _ == 'x', lambda _: _ == 'y')
    if paired_columns:
        return paired_columns

    raise GeoTableError('geometry columns expected')


def _get_paired_columns(column_names, is_x, is_y):
    x_column, y_column = None, None
    for column_name in column_names:
        normalized_column_name = _normalize_column_name(column_name)
        if is_x(normalized_column_name):
            x_column = column_name
        elif is_y(normalized_column_name):
            y_column = column_name
    if x_column and y_column:
        return [x_column, y_column]


def _get_get_field_values(field_type_by_name):
    field_types = field_type_by_name.values()

    def get_field_values(feature):
        field_values = []
        for field_index, field_type in enumerate(field_types):
            try:
                method_name = METHOD_NAME_BY_TYPE[field_type]
            except KeyError:
                method_name = 'GetField'
            field_value = getattr(feature, method_name)(field_index)
            field_values.append(_transform_field_value(
                field_value, field_type))
        return tuple(field_values)

    return get_field_values


def _get_instance_for_csv(instance, source_proj4, target_proj4):
    transform_shapely_geometry = get_transform_shapely_geometry(
        source_proj4, target_proj4)
    instance = instance.copy()
    instance['wkt'] = [transform_shapely_geometry(
        x).wkt for x in instance.pop('geometry_object')]
    instance['geometry_proj4'] = normalize_proj4(
        target_proj4 or source_proj4)
    return instance


def _get_instance_from_gdal_layer(Class, gdal_layer, transform_gdal_geometry):
    rows = []
    field_type_by_name = _get_field_type_by_name(gdal_layer)
    get_field_values = _get_get_field_values(field_type_by_name)
    for feature_index in range(gdal_layer.GetFeatureCount()):
        feature = gdal_layer.GetFeature(feature_index)
        if not feature:
            raise GeoTableError('feature unreadable')
        gdal_geometry = feature.GetGeometryRef()
        shapely_geometry = wkb.loads(transform_gdal_geometry(
            gdal_geometry).ExportToWkb()) if gdal_geometry else None
        field_values = get_field_values(feature)
        rows.append(field_values + (shapely_geometry,))
    field_names = tuple(field_type_by_name.keys())
    return Class(rows, columns=field_names + ('geometry_object',))


def _get_proj4_from_path(source_path, default_proj4):
    proj4_path = replace_file_extension(source_path, '.proj4')
    if not exists(proj4_path):
        return default_proj4 or LONGITUDE_LATITUDE_PROJ4
    return normalize_proj4(open(proj4_path).read())


def _get_load_geometry_object(geometry_columns):
    if len(geometry_columns) == 2:
        return lambda row: geometry.Point(*list(row[geometry_columns]))

    def load_geometry_object(row):
        [geometry_wkt] = row[geometry_columns]
        try:
            geometry_object = wkt.loads(geometry_wkt)
        except WKTReadingError:
            raise GeoTableError('wkt unparseable (%s)' % geometry_wkt)
        return geometry_object

    column_name = _normalize_column_name(geometry_columns[0])
    if column_name in ('wkt', 'longitudelatitudewkt'):
        return load_geometry_object
    elif column_name == 'latitudelongitudewkt':

        def load_flipped_geometry_object(row):
            geometry_object = load_geometry_object(row)
            return transform_geometries([geometry_object], flip_xy)[0]

        return load_flipped_geometry_object
    else:
        raise GeoTableError(
            'geometry columns not supported (%s)' % ' '.join(geometry_columns))


def _get_proj4_from_gdal_layer(gdal_layer, default_proj4=None):
    spatial_reference = gdal_layer.GetSpatialRef()
    try:
        proj4 = spatial_reference.ExportToProj4().strip()
    except AttributeError:
        proj4 = default_proj4 or LONGITUDE_LATITUDE_PROJ4
    return normalize_proj4(proj4)


def _has_one_proj4(t):
    if len(t) < 1:
        return False
    if 'geometry_proj4' not in t.columns:
        return True
    return len(t['geometry_proj4'].unique()) == 1


def _normalize_column_name(x):
    return str(x).lower().replace('_', '')


def _prepare_gdal_layer(t, gdal_dataset, target_proj4, layer_name):
    # Drop columns that have no values
    t = t.dropna(axis=1, how='all').copy()
    # Coerce objects into strings to prevent errors
    for field_name in t.field_names:
        column = t[field_name]
        if column.dtype.name == 'object':
            t[field_name] = column.fillna('').astype(str)
    # Create layer
    layer_proj4 = target_proj4 or t.iloc[0]['geometry_proj4']
    gdal_layer = gdal_dataset.CreateLayer(
        layer_name, _get_spatial_reference_from_proj4(layer_proj4))
    for field_definition in _get_field_definitions(t):
        gdal_layer.CreateField(field_definition)
    layer_definition = gdal_layer.GetLayerDefn()
    # Add features
    for source_proj4, proj4_t in t.groupby('geometry_proj4'):
        f = get_transform_shapely_geometry(source_proj4, layer_proj4)
        for index, row in proj4_t.iterrows():
            ogr_feature = ogr.Feature(layer_definition)
            for field_index, field_name in enumerate(t.field_names):
                ogr_feature.SetField2(field_index, row[field_name])
            ogr_feature.SetGeometry(ogr.CreateGeometryFromWkb(
                f(row['geometry_object']).wkb))
            try:
                gdal_layer.CreateFeature(ogr_feature)
            except RuntimeError:
                raise GeoTableError(
                    'mutually incompatible geometry types '
                    'must be in separate layers')
    return gdal_layer


def _transform_field_value(field_value, field_type):
    if field_type in (ogr.OFTInteger, ogr.OFTInteger64):
        field_value = int(field_value)
    elif field_type in (ogr.OFTIntegerList, ogr.OFTInteger64List):
        field_value = [int(x) for x in field_value]
    elif field_type in (ogr.OFTString, ogr.OFTWideString):
        field_value = unicode_safely(field_value)
    elif field_type in (ogr.OFTStringList, ogr.OFTWideStringList):
        field_value = [unicode_safely(x) for x in field_value]
    elif field_type in (ogr.OFTDate, ogr.OFTDateTime):
        try:
            field_value = datetime(*map(int, field_value))
        except ValueError:
            field_value = np.nan
    return field_value


METHOD_NAME_BY_TYPE = {
    ogr.OFTBinary: 'GetFieldAsBinary',
    ogr.OFTDate: 'GetFieldAsDateTime',
    ogr.OFTDateTime: 'GetFieldAsDateTime',
    ogr.OFTInteger: 'GetFieldAsInteger',
    ogr.OFTIntegerList: 'GetFieldAsIntegerList',
    ogr.OFTInteger64: 'GetFieldAsInteger64',
    ogr.OFTInteger64List: 'GetFieldAsInteger64List',
    ogr.OFTReal: 'GetFieldAsDouble',
    ogr.OFTRealList: 'GetFieldAsDoubleList',
    ogr.OFTString: 'GetFieldAsString',
    ogr.OFTStringList: 'GetFieldAsStringList',
    ogr.OFTTime: 'GetFieldAsDateTime',
    ogr.OFTWideString: 'GetFieldAsString',
    ogr.OFTWideStringList: 'GetFieldAsStringList',
}
