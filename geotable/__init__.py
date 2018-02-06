from invisibleroads_macros.disk import TemporaryFolder
from invisibleroads_macros.text import unicode_safely
from osgeo import gdal, ogr, osr
from pandas import DataFrame, Series, concat, read_csv
from shapely.geometry import GeometryCollection

from .exceptions import GeoTableError
from .macros import (
    _get_instance_from_layer, _get_proj4_from_layer,
    _get_transform_gdal_geometry, _has_one_layer, _has_one_proj4,
    _has_standard_proj4, _load_geometry_object_from_wkt, _resolve_source_path,
    get_transform_shapely_geometry, normalize_proj4, PROJ4_LONLAT)


class GeoTable(DataFrame):

    @classmethod
    def load(Class, source_path, source_proj4=PROJ4_LONLAT, target_proj4=None):
        with TemporaryFolder() as temporary_folder:
            target_folder = str(temporary_folder)
            source_path = _resolve_source_path(source_path, target_folder)
            if source_path.endswith('.shp'):
                return Class.from_shp(source_path, source_proj4, target_proj4)
            if source_path.endswith('.csv'):
                return Class.from_csv(source_path, source_proj4, target_proj4)

    @classmethod
    def from_shp(
            Class, source_path, source_proj4=PROJ4_LONLAT, target_proj4=None):
        try:
            data_source = ogr.Open(source_path)
        except RuntimeError:
            raise GeoTableError(
                "shapefile unreadable (source_path='%s')" % source_path)
        if not data_source:
            raise GeoTableError(
                "shapefile unloadable (source_path='%s')" % source_path)
        instances = []
        for layer_index in range(data_source.GetLayerCount()):
            layer = data_source.GetLayer(layer_index)
            layer_name = layer.GetName()
            source_proj4 = _get_proj4_from_layer(layer) or source_proj4
            transform_gdal_geometry = _get_transform_gdal_geometry(
                source_proj4, target_proj4)
            instance = _get_instance_from_layer(
                Class, layer, transform_gdal_geometry)
            instance['geometry_layer'] = unicode_safely(layer_name)
            instance['geometry_proj4'] = normalize_proj4(
                target_proj4 or source_proj4)
            instances.append(instance)
        return concat(instances)

    @classmethod
    def from_csv(
            Class, source_path, source_proj4=PROJ4_LONLAT,
            target_proj4=None, **kw):
        t = read_csv(source_path, **kw)
        if 'wkt' not in t.columns:
            raise GeoTableError((
                "column expected (source_path='%s', column_name='wkt')"
            ) % source_path)
        geometry_objects = []
        geometry_proj4s = []
        if _has_one_proj4(t):
            if 'geometry_proj4' in t:
                source_proj4 = t['geometry_proj4'].unique()[0]
            transform_shapely_geometry = get_transform_shapely_geometry(
                source_proj4, target_proj4)
            for index, row in t.iterrows():
                geometry_objects.append(transform_shapely_geometry(
                    _load_geometry_object_from_wkt(row['wkt'])))
                geometry_proj4s.append(target_proj4 or source_proj4)
        else:
            for index, row in t.iterrows():
                source_proj4 = row['geometry_proj4'] or source_proj4
                transform_shapely_geometry = get_transform_shapely_geometry(
                    source_proj4, target_proj4)
                geometry_objects.append(transform_shapely_geometry(
                    _load_geometry_object_from_wkt(row['wkt'])))
                geometry_proj4s.append(target_proj4 or source_proj4)
        t['geometry_object'] = geometry_objects
        if normalize_proj4(target_proj4) != PROJ4_LONLAT:
            t['geometry_proj4'] = geometry_proj4s
        t.drop(['wkt'], inplace=True)
        return t

    def to_shp(self, target_path, target_proj4=None):
        pass

    def to_csv(self, target_path, target_proj4=None, **kw):
        instances = []
        for source_proj4, instance in self.groupby('geometry_proj4'):
            transform_shapely_geometry = get_transform_shapely_geometry(
                source_proj4, target_proj4)
            instance = instance.copy()
            instance['wkt'] = [transform_shapely_geometry(
                x).wkt for x in instance.pop('geometry_object')]
            instance['geometry_proj4'] = target_proj4 or source_proj4
            instances.append(instance)
        t = concat(instances)
        excluded_column_names = []
        if _has_one_layer(t):
            excluded_column_names.append('geometry_layer')
        if _has_standard_proj4(t):
            excluded_column_names.append('geometry_proj4')
        t.drop(excluded_column_names, axis=1, inplace=True)
        return super(GeoTable, t).to_csv(target_path, **kw)

    @property
    def _constructor(self):
        return GeoTable

    @property
    def _constructor_sliced(self):
        return GeoRow


class GeoRow(Series):

    @property
    def _constructor(self):
        return GeoRow

    @property
    def _constructor_expanddim(self):
        return GeoTable


class ColorfulGeometryCollection(GeometryCollection):

    def __init__(self, geoms=None, colors=None):
        super(ColorfulGeometryCollection, self).__init__(geoms)
        self.colors = colors or []

    def svg(self, scale_factor=1.0, color=None):
        if self.is_empty:
            return '<g />'
        if not self.colors:
            return super(ColorfulGeometryCollection, self).svg(
                scale_factor, color)
        return '<g>%s</g>' % ''.join(p.svg(scale_factor, c) for p, c in zip(
            self, self.colors))


gdal.UseExceptions()
ogr.UseExceptions()
osr.UseExceptions()
