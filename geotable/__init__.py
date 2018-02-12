import utm
from glob import glob
from invisibleroads_macros.disk import (
    TemporaryFolder, get_file_stem, uncompress)
from invisibleroads_macros.exceptions import BadFormat
from invisibleroads_macros.text import unicode_safely
from os.path import join
from osgeo import gdal, ogr, osr
from pandas import DataFrame, Series, concat, read_csv
from shapely.geometry import GeometryCollection

from .exceptions import GeoTableError
from .macros import (
    _get_instance_from_layer, _get_proj4_from_layer,
    _get_transform_gdal_geometry, _has_one_proj4,
    _load_geometry_object_from_wkt, get_transform_shapely_geometry,
    get_utm_proj4, normalize_geotable, normalize_proj4, PROJ4_LONLAT)


class GeoTable(DataFrame):

    @classmethod
    def load(Class, source_path, source_proj4=PROJ4_LONLAT, target_proj4=None):
        with TemporaryFolder() as temporary_folder:
            try:
                source_folder = uncompress(source_path, str(temporary_folder))
            except BadFormat:
                if source_path.endswith('.shp'):
                    return Class.from_shp(
                        source_path, source_proj4, target_proj4)
                if source_path.endswith('.csv'):
                    return Class.from_csv(
                        source_path, source_proj4, target_proj4)
                raise GeoTableError(
                    'file format not supported (%s)' % source_path)
            else:
                try:
                    return Class.from_shp(
                        source_folder, source_proj4, target_proj4)
                except GeoTableError:
                    pass
                instances = []
                for path in glob(join(source_folder, '*.csv')):
                    instance = Class.from_csv(path, source_proj4, target_proj4)
                    instance['geometry_layer'] = get_file_stem(path)
                return normalize_geotable(concat(instances))

    @classmethod
    def from_shp(
            Class, source_path, source_proj4=PROJ4_LONLAT, target_proj4=None):
        try:
            gdal_dataset = gdal.OpenEx(source_path)
        except RuntimeError:
            raise GeoTableError('shapefile unreadable (%s)' % source_path)
        if not data_source:
            raise GeoTableError('shapefile unloadable (%s)' % source_path)
        try:
            layer_count = data_source.GetLayerCount()
        except AttributeError:
            raise GeoTableError('shapefile empty (%s)' % source_path)
        instances = []
        for layer_index in range(layer_count):
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
        return normalize_geotable(concat(instances))

    @classmethod
    def from_csv(
            Class, source_path, source_proj4=PROJ4_LONLAT,
            target_proj4=None, **kw):
        t = read_csv(source_path, **kw)
        if 'wkt' not in t.columns:
            raise GeoTableError('wkt column expected (%s)' % source_path)
        geometry_objects, geometry_proj4s = [], []
        if _has_one_proj4(t):
            if 'geometry_proj4' in t:
                source_proj4 = t['geometry_proj4'][0]
            transform_shapely_geometry = get_transform_shapely_geometry(
                source_proj4, target_proj4)
            for index, row in t.iterrows():
                geometry_objects.append(transform_shapely_geometry(
                    _load_geometry_object_from_wkt(row['wkt'])))
                geometry_proj4s.append(target_proj4 or source_proj4)
        else:
            t['geometry_proj4'].fillna(source_proj4, inplace=True)
            for index, row in t.iterrows():
                source_proj4 = row['geometry_proj4']
                transform_shapely_geometry = get_transform_shapely_geometry(
                    source_proj4, target_proj4)
                geometry_objects.append(transform_shapely_geometry(
                    _load_geometry_object_from_wkt(row['wkt'])))
                geometry_proj4s.append(target_proj4 or source_proj4)
        t['geometry_object'] = geometry_objects
        t['geometry_proj4'] = geometry_proj4s
        return normalize_geotable(Class(t), excluded_column_names=['wkt'])

    def to_shp(self, target_path, target_proj4=None):
        pass

    def to_csv(self, target_path, target_proj4=None, **kw):
        if 'geometry_proj4' in self:
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
        else:
            source_proj4 = PROJ4_LONLAT
            transform_shapely_geometry = get_transform_shapely_geometry(
                source_proj4, target_proj4)
            instance = self.copy()
            instance['wkt'] = [transform_shapely_geometry(
                x).wkt for x in instance.pop('geometry_object')]
            instance['geometry_proj4'] = target_proj4 or source_proj4
            t = instance
        return super(GeoTable, normalize_geotable(t)).to_csv(target_path, **kw)

    @property
    def geometries(self):
        return list(self['geometry_object'])

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


class UTMZone(object):

    def __init__(self, zone_number, zone_letter):
        self.zone_number = zone_number
        self.zone_letter = zone_letter
        self.proj4 = get_utm_proj4(zone_number, zone_letter)

    @classmethod
    def load(Class, geotable_path):
        t = GeoTable.load(geotable_path, target_proj4=PROJ4_LONLAT)
        lonlat_point = GeometryCollection(t.geometries).centroid
        longitude, latitude = lonlat_point.x, lonlat_point.y
        zone_number, zone_letter = utm.from_latlon(latitude, longitude)[-2:]
        return Class(zone_number, zone_letter)


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


gdal.SetConfigOption('GDAL_NUM_THREADS', 'ALL_CPUS')
gdal.UseExceptions()
ogr.UseExceptions()
osr.UseExceptions()
