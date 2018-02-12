from collections import OrderedDict
from invisibleroads_macros.text import unicode_safely
from osgeo import ogr, osr
from shapely import wkb, wkt
from shapely.errors import WKTReadingError

from .exceptions import (
    CoordinateTransformationError, GeoTableError, SpatialReferenceError)


def get_proj4_from_epsg(epsg):
    spatial_reference = osr.SpatialReference()
    spatial_reference.ImportFromEPSG(epsg)
    return spatial_reference.ExportToProj4()


def get_transform_shapely_geometry(source_proj4, target_proj4):
    transform_gdal_geometry = _get_transform_gdal_geometry(
        source_proj4, target_proj4)

    def transform_shapely_geometry(shapely_geometry):
        gdal_geometry = ogr.CreateGeometryFromWkb(shapely_geometry.wkb)
        return wkb.loads(transform_gdal_geometry(gdal_geometry).ExportToWkb())

    return transform_shapely_geometry


def get_utm_proj4(zone_number, zone_letter):
    parts = []
    parts.extend([
        '+proj=utm',
        '+zone=%s' % zone_number])
    if zone_letter.upper() < 'N':
        parts.append('+south')
    parts.extend([
        '+ellps=WGS84',
        '+datum=WGS84',
        '+units=m',
        '+no_defs'])
    return ' '.join(parts)


def normalize_proj4(proj4):
    spatial_reference = _get_spatial_reference_from_proj4(proj4)
    return spatial_reference.ExportToProj4().strip()


def normalize_geotable(t, excluded_column_names=None):
    if not excluded_column_names:
        excluded_column_names = []
    if _has_one_layer(t):
        excluded_column_names.append('geometry_layer')
    if _has_standard_proj4(t):
        excluded_column_names.append('geometry_proj4')
    return t.drop(excluded_column_names, axis=1, errors='ignore')


def _get_coordinate_transformation(source_proj4, target_proj4):
    source_spatial_reference = _get_spatial_reference_from_proj4(source_proj4)
    target_spatial_reference = _get_spatial_reference_from_proj4(target_proj4)
    return osr.CoordinateTransformation(
        source_spatial_reference, target_spatial_reference)


def _get_field_type_by_name(layer):
    field_type_by_name = OrderedDict()
    layer_definition = layer.GetLayerDefn()
    for field_index in range(layer_definition.GetFieldCount()):
        field_definition = layer_definition.GetFieldDefn(field_index)
        field_name = field_definition.GetName()
        field_type = field_definition.GetType()
        field_type_by_name[field_name] = field_type
    return field_type_by_name


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


def _get_instance_from_layer(Class, layer, transform_gdal_geometry):
    rows = []
    field_type_by_name = _get_field_type_by_name(layer)
    get_field_values = _get_get_field_values(field_type_by_name)
    for feature_index in range(layer.GetFeatureCount()):
        feature = layer.GetFeature(feature_index)
        gdal_geometry = feature.GetGeometryRef()
        shapely_geometry = wkb.loads(transform_gdal_geometry(
            gdal_geometry).ExportToWkb()) if gdal_geometry else None
        field_values = get_field_values(feature)
        rows.append(field_values + (shapely_geometry,))
    field_names = tuple(field_type_by_name.keys())
    return Class(rows, columns=field_names + ('geometry_object',))


def _get_proj4_from_layer(layer):
    spatial_reference = layer.GetSpatialRef()
    try:
        proj4 = spatial_reference.ExportToProj4().strip()
    except AttributeError:
        proj4 = None
    return proj4


def _get_spatial_reference_from_proj4(proj4):
    spatial_reference = osr.SpatialReference()
    try:
        spatial_reference.ImportFromProj4(proj4)
    except RuntimeError:
        raise SpatialReferenceError(
            "bad spatial reference (proj4='%s')" % proj4)
    return spatial_reference


def _get_transform_gdal_geometry(source_proj4, target_proj4):
    if not target_proj4 or source_proj4 == target_proj4:
        return lambda x: x
    coordinate_transformation = _get_coordinate_transformation(
        source_proj4, target_proj4)

    def transform_gdal_geometry(gdal_geometry):
        try:
            gdal_geometry.Transform(coordinate_transformation)
        except RuntimeError:
            raise CoordinateTransformationError((
                "coordinate transformation failed "
                "(source_proj4='%s', target_proj4='%s', wkt='%s')"
            ) % (source_proj4, target_proj4, gdal_geometry.ExportToWkt()))
        return gdal_geometry

    return transform_gdal_geometry


def _has_one_layer(t):
    if 'geometry_layer' not in t.columns:
        return True
    return len(t['geometry_layer'].unique()) == 1


def _has_one_proj4(t):
    if 'geometry_proj4' not in t.columns:
        return True
    return len(t['geometry_proj4'].unique()) == 1


def _has_standard_proj4(t):
    if 'geometry_proj4' not in t.columns:
        return True
    geometry_proj4s = t['geometry_proj4'].unique()
    geometry_proj4s = [normalize_proj4(x) for x in geometry_proj4s]
    return geometry_proj4s == [PROJ4_LONLAT]


def _load_geometry_object_from_wkt(geometry_wkt):
    try:
        geometry_object = wkt.loads(geometry_wkt)
    except WKTReadingError:
        raise GeoTableError("wkt unparseable (wkt='%s')" % geometry_wkt)
    return geometry_object


def _transform_field_value(field_value, field_type):
    if field_type in (ogr.OFTString, ogr.OFTWideString):
        field_value = unicode_safely(field_value)
    elif field_type in (ogr.OFTStringList, ogr.OFTWideStringList):
        field_value = [unicode_safely(x) for x in field_value]
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
PROJ4_LONLAT = normalize_proj4('+proj=longlat +datum=WGS84 +no_defs')
