import pandas as pd


class GeoTableError(ValueError):
    pass


class EmptyGeoTableError(pd.errors.EmptyDataError, GeoTableError):
    pass


class CoordinateTransformationError(GeoTableError):
    pass


class SpatialReferenceError(GeoTableError):
    pass
