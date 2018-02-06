class GeoTableError(Exception):
    pass


class CoordinateTransformationError(GeoTableError):
    pass


class SpatialReferenceError(GeoTableError):
    pass
