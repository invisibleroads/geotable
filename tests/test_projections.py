from geotable.exceptions import (
    CoordinateTransformationError, SpatialReferenceError)
from geotable.projections import (
    _get_spatial_reference_from_proj4, _get_transform_gdal_geometry,
    get_proj4_from_epsg, get_utm_proj4, LONGITUDE_LATITUDE_PROJ4,
    SPHERICAL_MERCATOR_PROJ4)
from osgeo import ogr
from pytest import raises


def test_get_proj4_from_epsg():
    assert get_proj4_from_epsg(4326) == LONGITUDE_LATITUDE_PROJ4


def test_get_spatial_reference_from_proj4():
    with raises(SpatialReferenceError):
        _get_spatial_reference_from_proj4('')
    _get_spatial_reference_from_proj4(LONGITUDE_LATITUDE_PROJ4)


def test_get_transform_gdal_geometry():
    f = _get_transform_gdal_geometry(
        LONGITUDE_LATITUDE_PROJ4, SPHERICAL_MERCATOR_PROJ4)
    with raises(CoordinateTransformationError):
        f(ogr.CreateGeometryFromWkt('POINT(100 100)'))


def test_get_utm_proj4():
    assert '+south' in get_utm_proj4(22, 'M')
