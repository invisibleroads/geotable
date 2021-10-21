from osgeo import ogr, osr
from shapely import wkb

from .exceptions import CoordinateTransformationError, SpatialReferenceError


def get_proj4_from_epsg(epsg):
    spatial_reference = osr.SpatialReference()
    spatial_reference.ImportFromEPSG(epsg)
    return normalize_proj4(spatial_reference.ExportToProj4())


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


def get_transform_shapely_geometry(source_proj4, target_proj4):
    transform_gdal_geometry = _get_transform_gdal_geometry(
        source_proj4, target_proj4)

    def transform_shapely_geometry(shapely_geometry):
        gdal_geometry = ogr.CreateGeometryFromWkb(shapely_geometry.wkb)
        geometry_wkb = transform_gdal_geometry(gdal_geometry).ExportToWkb()
        return wkb.loads(bytes(geometry_wkb))

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


def _get_coordinate_transformation(source_proj4, target_proj4):
    source_spatial_reference = _get_spatial_reference_from_proj4(source_proj4)
    target_spatial_reference = _get_spatial_reference_from_proj4(target_proj4)

    def run():
        return osr.CoordinateTransformation(
            source_spatial_reference, target_spatial_reference)

    try:
        coordinate_transformation = run()
    except RuntimeError:
        # Workaround weird RuntimeError on first call in GDAL 3.3.2
        coordinate_transformation = run()
    return coordinate_transformation


def _get_spatial_reference_from_proj4(proj4):
    spatial_reference = osr.SpatialReference()
    try:
        spatial_reference.ImportFromProj4(proj4)
    except RuntimeError:
        raise SpatialReferenceError('proj4 unparseable (%s)' % proj4)
    return spatial_reference


LONGITUDE_LATITUDE_PROJ4 = normalize_proj4(
    '+proj=longlat +datum=WGS84 +no_defs')
SPHERICAL_MERCATOR_PROJ4 = normalize_proj4(
    '+proj=merc +a=6378137 +b=6378137 +lat_ts=0.0 +lon_0=0.0 +x_0=0.0 +y_0=0 '
    '+k=1.0 +units=m +nadgrids=@null +wktext +no_defs')
