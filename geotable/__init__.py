import pandas as pd
import utm
from functools import partial, wraps
from inspect import signature
from invisibleroads_macros.disk import (
    TemporaryStorage, compress, compress_zip, find_paths, get_file_stem,
    has_archive_extension, move_path, replace_file_extension)
from invisibleroads_macros import geometry
from invisibleroads_macros.html import make_random_color
from invisibleroads_macros.table import load_csv_safely
from invisibleroads_macros.text import unicode_safely
from os.path import join
from osgeo import gdal, ogr, osr
from shapely.geometry import GeometryCollection, box

from .exceptions import EmptyGeoTableError, GeoTableError
from .macros import (
    _clear_cache,
    _ensure_geotable_columns,
    _get_geometry_columns,
    _get_instance_for_csv,
    _get_instance_from_gdal_layer,
    _get_load_geometry_object,
    _get_proj4_from_gdal_layer,
    _get_proj4_from_path,
    _get_source_folder,
    _prepare_gdal_layer,
    _has_one_proj4,
    _make_geotable)
from .projections import (
    _get_transform_gdal_geometry,
    get_transform_shapely_geometry,
    get_utm_proj4,
    normalize_proj4,
    LONGITUDE_LATITUDE_PROJ4,
    SPHERICAL_MERCATOR_PROJ4)


KML_COLUMNS = [
    'description', 'timestamp', 'begin', 'end', 'altitudeMode', 'tessellate',
    'extrude', 'visibility', 'drawOrder', 'icon', 'snippet']
GEOTABLE_EXTENSIONS = [
    '.csv',
    '.geojson',
    '.kml',
    '.kmz',
    '.json',
    '.shp']


class GeoTable(pd.DataFrame):

    @classmethod
    def define_load_with_utm_proj4(Class, source_path):
        utm_proj4 = Class.load_utm_proj4(source_path)
        f = Class.load
        f_signature = signature(f)

        @wraps(f)
        def load_geotable_with_utm_proj4(*args, **kw):
            kw = f_signature.bind(*args, **kw).arguments
            if 'target_proj4' not in kw:
                kw['target_proj4'] = utm_proj4
            return f(**kw)

        return load_geotable_with_utm_proj4

    @classmethod
    def load_utm_proj4(Class, source_path_or_url):
        geotable = Class.load(
            source_path_or_url, target_proj4=LONGITUDE_LATITUDE_PROJ4)
        lonlat_point = GeometryCollection(geotable.geometries).centroid
        longitude, latitude = lonlat_point.x, lonlat_point.y
        zone_number, zone_letter = utm.from_latlon(latitude, longitude)[-2:]
        return get_utm_proj4(zone_number, zone_letter)

    @classmethod
    def load(
            Class,
            source_path_or_url,
            source_proj4=None,
            target_proj4=None,
            drop_z=False,
            bounding_box=None,
            bounding_polygon=None,
            **kw):
        t = Class._load(
            source_path_or_url, source_proj4, target_proj4, **kw)
        if drop_z:
            t['geometry_object'] = geometry.transform_geometries(
                t['geometry_object'], geometry.drop_z)
        if bounding_box and bounding_box != (-180, -90, +180, +90):
            f = get_transform_shapely_geometry(
                LONGITUDE_LATITUDE_PROJ4, target_proj4)
            bounding_polygon = f(box(*bounding_box))
        if bounding_polygon:
            indices = [i for i, g in enumerate(t.geometries) if g.intersects(
                bounding_polygon)]
            t = t.iloc[indices].copy()
        return t

    @classmethod
    def _load(
            Class,
            source_path_or_url,
            source_proj4=None,
            target_proj4=None,
            **kw):
        with TemporaryStorage() as storage:
            try:
                source_folder = _get_source_folder(
                    source_path_or_url, storage.folder, GEOTABLE_EXTENSIONS)
            except GeoTableError as e:
                source_path = str(e)
                if source_path.endswith('.csv'):
                    return Class.from_csv(
                        source_path, source_proj4, target_proj4, **kw)
                else:
                    return Class.from_gdal(
                        source_path, source_proj4, target_proj4)
            tables = []
            for path in find_paths(source_folder, '*.csv'):
                try:
                    t = Class.from_csv(path, source_proj4, target_proj4, **kw)
                except (GeoTableError, ValueError):
                    continue
                tables.append(t)
            for path in find_paths(source_folder, '*.shp'):
                try:
                    t = Class.from_gdal(path, source_proj4, target_proj4)
                except (GeoTableError, ValueError):
                    continue
                tables.append(t)
            if tables:
                return concatenate_tables(tables)
        return Class()

    def drop_duplicate_geometries(self, inplace=False):
        t = self if inplace else self.copy()
        t['geometry_wkb'] = [g.wkb for g in t.geometries]
        t.drop_duplicates(subset=['geometry_wkb'], inplace=True)
        t.drop(columns=['geometry_wkb'], inplace=True)
        return t

    @classmethod
    def from_records(Class, *args, **kw):
        t = super(GeoTable, Class).from_records(*args, **kw)
        return _make_geotable(t)

    @classmethod
    def from_gdal(Class, source_path, source_proj4=None, target_proj4=None):
        try:
            gdal_dataset = gdal.OpenEx(source_path)
        except RuntimeError:
            raise GeoTableError('file unloadable (%s)' % source_path)
        instances = []
        for layer_index in range(gdal_dataset.GetLayerCount()):
            gdal_layer = gdal_dataset.GetLayer(layer_index)
            row_proj4 = _get_proj4_from_gdal_layer(gdal_layer, source_proj4)
            f = _get_transform_gdal_geometry(row_proj4, target_proj4)
            t = _get_instance_from_gdal_layer(Class, gdal_layer, f)
            t['geometry_layer'] = unicode_safely(gdal_layer.GetName())
            t['geometry_proj4'] = normalize_proj4(target_proj4 or row_proj4)
            instances.append(t)
        t = concatenate_tables(instances)
        if source_path.endswith('.kmz') or source_path.endswith('.kml'):
            t = t.drop(columns=KML_COLUMNS, errors='ignore')
        return t

    @classmethod
    def from_csv(
            Class, source_path, source_proj4=None, target_proj4=None, **kw):
        try:
            t = load_csv_safely(source_path, **kw)
        except pd.errors.EmptyDataError:
            raise EmptyGeoTableError('file empty (%s)' % source_path)
        try:
            geometry_columns = _get_geometry_columns(t)
        except GeoTableError as e:
            raise GeoTableError(str(e) + ' (%s)' % source_path)
        load_geometry_object = _get_load_geometry_object(geometry_columns)
        source_proj4 = _get_proj4_from_path(source_path, source_proj4)
        geometry_objects = []
        if 'geometry_layer' not in t:
            t['geometry_layer'] = unicode_safely(get_file_stem(source_path))
        if _has_one_proj4(t):
            row_proj4 = t.iloc[0].get('geometry_proj4', source_proj4)
            f = get_transform_shapely_geometry(row_proj4, target_proj4)
            for index, row in t.iterrows():
                geometry_objects.append(f(load_geometry_object(row)))
            t['geometry_proj4'] = normalize_proj4(target_proj4 or row_proj4)
        else:
            geometry_proj4s = []
            for index, row in t.iterrows():
                row_proj4 = row.get('geometry_proj4', source_proj4)
                f = get_transform_shapely_geometry(row_proj4, target_proj4)
                geometry_objects.append(f(load_geometry_object(row)))
                geometry_proj4s.append(normalize_proj4(
                    target_proj4 or row_proj4))
            t['geometry_proj4'] = geometry_proj4s
        t['geometry_object'] = geometry_objects
        return Class(t.drop(geometry_columns, axis=1))

    def save_geojson(self, target_path, target_proj4=None):
        self.to_geojson(target_path, target_proj4)
        return target_path

    def save_kmz(self, target_path, target_proj4=None):
        self.to_kmz(target_path, target_proj4)
        return target_path

    def save_shp(self, target_path, target_proj4=None):
        self.to_shp(target_path, target_proj4)
        return target_path

    def save_csv(self, target_path, target_proj4=None, **kw):
        if 'index' not in kw:
            kw['index'] = False
        self.to_csv(target_path, target_proj4, **kw)
        return target_path

    def to_geojson(self, target_path, target_proj4=None):
        self.to_gdal(
            target_path,
            target_proj4=LONGITUDE_LATITUDE_PROJ4,
            driver_name='GeoJSON')
        return target_path

    def to_kmz(self, target_path, target_proj4=None):
        self.to_gdal(
            target_path,
            target_proj4=LONGITUDE_LATITUDE_PROJ4,
            driver_name='LIBKML')
        return target_path

    def to_shp(self, target_path, target_proj4=None):
        if not has_archive_extension(target_path):
            raise GeoTableError(
                'archive extension expected (%s)' % (target_path))
        return self.to_gdal(
            target_path, target_proj4, driver_name='ESRI Shapefile')

    @_ensure_geotable_columns
    def to_csv(self, target_path, target_proj4=None, **kw):
        try:
            t = concatenate_tables(_get_instance_for_csv(
                x, source_proj4 or LONGITUDE_LATITUDE_PROJ4, target_proj4,
            ) for source_proj4, x in self.groupby('geometry_proj4'))
        except ValueError:
            t = self

        excluded_column_names = []
        unique_geometry_layers = t['geometry_layer'].unique()
        unique_geometry_proj4s = t['geometry_proj4'].unique()
        if len(unique_geometry_layers) == 1:
            excluded_column_names.append('geometry_layer')
        if len(unique_geometry_proj4s) == 1:
            excluded_column_names.append('geometry_proj4')
            geometry_proj4 = unique_geometry_proj4s[0]
            if geometry_proj4 != LONGITUDE_LATITUDE_PROJ4:
                open(replace_file_extension(
                    target_path, '.proj4'), 'wt').write(geometry_proj4)
        if len(t) == 0:
            excluded_column_names.extend([
                'geometry_layer',
                'geometry_proj4',
                'geometry_object'])
            t['wkt'] = ''
        t = t.drop(columns=excluded_column_names)
        if len(t.columns) == 1:
            t[''] = ''

        with TemporaryStorage() as storage:
            temporary_path = join(storage.folder, 'geotable.csv')
            super(GeoTable, t).to_csv(temporary_path, **kw)
            if has_archive_extension(target_path):
                compress(storage.folder, target_path)
            else:
                move_path(target_path, temporary_path)

    @_ensure_geotable_columns
    def to_gdal(
            self, target_path, target_proj4=None,
            driver_name='ESRI Shapefile'):
        gdal_driver = gdal.GetDriverByName(driver_name)
        if not gdal_driver:
            raise GeoTableError('gdal driver missing (%s)' % driver_name)
        try:
            geometry_columns = _get_geometry_columns(self)
        except GeoTableError:
            table = self
        else:
            table = self.drop(columns=geometry_columns)
        as_archive = has_archive_extension(target_path)
        as_kmz = target_path.endswith('.kmz')
        with TemporaryStorage() as storage:
            if as_archive:
                gdal_dataset_path = storage.folder
            elif as_kmz:
                gdal_dataset_path = join(storage.folder, get_file_stem(
                    target_path) + '.kml')
            else:
                gdal_dataset_path = target_path
            gdal_dataset = gdal_driver.Create(gdal_dataset_path, 0, 0)
            for layer_name, layer_t in table.groupby('geometry_layer'):
                _prepare_gdal_layer(
                    layer_t, gdal_dataset, target_proj4, layer_name)
            gdal_dataset.FlushCache()
            if as_archive:
                compress(storage.folder, target_path)
            elif as_kmz:
                compress_zip(storage.folder, target_path)

    @_ensure_geotable_columns
    def draw(self):
        'Render layers in Jupyter Notebook'
        return ColorfulGeometryCollection([GeometryCollection(
            x.get_geometries(SPHERICAL_MERCATOR_PROJ4)
        ) for _, x in self.groupby('geometry_layer')])

    @_ensure_geotable_columns
    def get_geometries(self, target_proj4=None):
        geometry_by_index = {}
        for source_proj4, proj4_t in self.groupby('geometry_proj4'):
            f = get_transform_shapely_geometry(source_proj4, target_proj4)
            for index, row in proj4_t.iterrows():
                geometry_by_index[index] = f(row['geometry_object'])
        return list(pd.Series(geometry_by_index)[self.index])

    @property
    def field_names(self):
        return [x for x in self.columns if x not in [
            'geometry_object', 'geometry_layer', 'geometry_proj4']]

    @property
    @_ensure_geotable_columns
    def geometries(self):
        return list(self['geometry_object'])

    @property
    def _constructor(self):
        return GeoTable

    @property
    def _constructor_sliced(self):
        return GeoRow


class GeoRow(pd.Series):

    def draw(self):
        'Render geometry in Jupyter Notebook'
        return self.get_geometry(SPHERICAL_MERCATOR_PROJ4)

    def get_geometry(self, target_proj4=None):
        source_proj4 = self['geometry_proj4']
        f = get_transform_shapely_geometry(source_proj4, target_proj4)
        return f(self['geometry_object'])

    @property
    def _constructor(self):
        return GeoRow

    @property
    def _constructor_expanddim(self):
        return GeoTable


class ColorfulGeometryCollection(GeometryCollection):

    def __init__(self, geoms=None, colors=None):
        super(ColorfulGeometryCollection, self).__init__(geoms)
        self.colors = colors or [make_random_color() for x in range(len(
            geoms or []))]

    def svg(self, scale_factor=1.0, color=None):
        if self.is_empty:
            return '<g />'
        return '<g>%s</g>' % ''.join(p.svg(scale_factor, c) for p, c in zip(
            self, self.colors))


def define_load_with_utm_proj4(source_path):
    return GeoTable.define_load_with_utm_proj4(source_path)


def load_utm_proj4(source_path):
    return GeoTable.load_utm_proj4(source_path)


def load(
        source_path_or_url,
        source_proj4=None,
        target_proj4=None,
        drop_z=False,
        bounding_box=None,
        bounding_polygon=None,
        **kw):
    return GeoTable.load(
        source_path_or_url,
        source_proj4,
        target_proj4,
        drop_z,
        bounding_box,
        bounding_polygon,
        **kw)


clear_cache = _clear_cache
concatenate_tables = partial(pd.concat, ignore_index=True, sort=False)


gdal.SetConfigOption('GDAL_NUM_THREADS', 'ALL_CPUS')
gdal.UseExceptions()
ogr.UseExceptions()
osr.UseExceptions()
__all__ = [
    'GeoTable',
    'GeoRow',
    'GeoTableError',
    'EmptyGeoTableError',
    'LONGITUDE_LATITUDE_PROJ4']
