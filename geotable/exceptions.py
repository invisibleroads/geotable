from pandas.errors import EmptyDataError


class GeoTableError(Exception):
    pass


class EmptyGeoTableError(EmptyDataError, GeoTableError):
    pass


class CoordinateTransformationError(GeoTableError):
    pass


class SpatialReferenceError(GeoTableError):
    pass
