GeoTable
========
Read and write spatial vectors from shapefiles and CSVs thanks to `GDAL <http://www.gdal.org>`_ and `pandas <http://pandas.pydata.org>`_.


Install
-------
::

    sudo dnf -y install gdal-python3
    # sudo apt-get -y install python3-gdal
    virtualenv -p $(which python3) --system-site-packages \
        ~/.virtualenvs/crosscompute
    source ~/.virtualenvs/crosscompute/bin/activate
    pip install geotable


Use
---
Load shapefiles. ::

    In [1]: from geotable import GeoTable

    In [2]: t = GeoTable.load('shp.zip')

    In [3]: t.iloc[0]
    Out[3]:
    name                                                 b
    quantity                                             2
    cost                                              0.66
    date                               1990-01-01 00:00:00
    geometry_object         POINT (-91.5305465 14.8520705)
    geometry_layer                                       b
    geometry_proj4     +proj=longlat +datum=WGS84 +no_defs
    Name: 0, dtype: object

Load CSVs containing spatial information. ::

    GeoTable.load('wkt.csv')  # Load single CSV
    GeoTable.load('csv.zip')  # Load archive of multiple CSVs
    GeoTable.load('csv.zip', parse_dates=['date'])  # Configure pandas.read_csv

Handle CSVs with different geometry columns. ::

    $ cat latitude_longitude.csv
    name,quantity,cost,date,latitude,longitude
    b,2,0.66,1990-01-01,14.8520705,-91.5305465

    $ cat lat_lon.csv
    name,quantity,cost,date,lat,lon
    c,3,0.99,2000-01-01,42.2808256,-83.7430378

    $ cat latitude_longitude_wkt.csv
    name,quantity,cost,date,latitude_longitude_wkt
    a,1,0.33,1980-01-01,POINT(42.3736158 -71.10973349999999)

    $ cat longitude_latitude_wkt.csv
    name,quantity,cost,date,longitude_latitude_wkt
    a,1,0.33,1980-01-01,POINT(-71.10973349999999 42.3736158)

    $ cat wkt.csv
    name,quantity,cost,date,wkt
    aaa,1,0.33,1980-01-01,"POINT(-71.10973349999999 42.3736158)"
    bbb,1,0.33,1980-01-01,"LINESTRING(-122.1374637 37.3796627,-92.5807231 37.1067189)"
    ccc,1,0.33,1980-01-01,"POLYGON ((-83.10973350093332 42.37361082304877, -103.5305394806998 14.85206885307358, -95.7430260175515 42.28082607112266, -83.10973350093332 42.37361082304877))"

Handle CSVs with different spatial references. ::

    $ cat proj4_from_file.csv
    name,wkt
    aaa,"POLYGON((326299 4693415,-1980130 1771892,-716771 4787516,326299 4693415))"

    $ cat proj4_from_file.proj4
    +proj=utm +zone=17 +ellps=WGS84 +datum=WGS84 +units=m +no_defs

    $ cat proj4_from_row.csv
    name,wkt,geometry_layer,geometry_proj4
    aaa,"LINESTRING(-122.1374637 37.3796627,-92.5807231 37.1067189)",l1,+proj=longlat +datum=WGS84 +no_defs
    aaa,"POLYGON((326299 4693415,-1980130 1771892,-716771 4787516,326299 4693415))",l2,+proj=utm +zone=17 +ellps=WGS84 +datum=WGS84 +units=m +no_defs

Load and save in `different spatial references <http://spatialreference.org>`_. ::

    from geotable.projections import SPHERICAL_MERCATOR_PROJ4
    t = GeoTable.load('shp.zip', target_proj4=SPHERICAL_MERCATOR_PROJ4)

    from geotable.projections import LONGITUDE_LATITUDE_PROJ4
    t.to_shp('/tmp/shp.zip', target_proj4=LONGITUDE_LATITUDE_PROJ4)

Use LONGITUDE_LATITUDE_PROJ4 for compatibility with algorithms that use geodesic distance such as those found in `geopy <https://pypi.python.org/pypi/geopy>`_ and `pysal <http://pysal.readthedocs.io/en/latest>`_. Geodesic distance is also known as arc distance and is the distance between two points as measured using the curvature of the Earth. If your locations are spread over a large geographic extent, geodesic longitude and latitude coordinates provide greater accuracy than Euclidean XY coordinates. ::

    from geotable.projections import LONGITUDE_LATITUDE_PROJ4
    t = GeoTable.load('shp.zip', target_proj4=LONGITUDE_LATITUDE_PROJ4)
    t.to_csv('/tmp/csv.zip', target_proj4=LONGITUDE_LATITUDE_PROJ4)
    t.to_shp('/tmp/shp.zip', target_proj4=LONGITUDE_LATITUDE_PROJ4)

Use the `Universal Transverse Mercator (UTM) <https://en.wikipedia.org/wiki/Universal_Transverse_Mercator_coordinate_system>`_ projection for compatibility with algorithms that use Euclidean distance on XY coordinates such as those found in `scipy.spatial <https://docs.scipy.org/doc/scipy/reference/spatial.html>`_. If you know that your locations are confined to a small region, you can use the projected XY coordinates with standard Euclidean based algorithms, which tend to be significantly faster than their geodesic variants. ::

    utm_proj4 = GeoTable.load_utm_proj4('shp.zip')
    t = GeoTable.load('csv.zip', target_proj4=utm_proj4)
    t.to_csv('/tmp/csv.zip', target_proj4=utm_proj4)
    t.to_shp('/tmp/shp.zip', target_proj4=utm_proj4)

Use the `Spherical Mercator <https://en.wikipedia.org/wiki/Web_Mercator>`_ projection when visualization is more important than accuracy. Do not use this projection for algorithms where spatial accuracy is important. ::

    from geotable.projections import SPHERICAL_MERCATOR_PROJ4
    t = GeoTable.load('wkt.csv', target_proj4=SPHERICAL_MERCATOR_PROJ4)
    t.to_csv('/tmp/csv.zip', target_proj4=SPHERICAL_MERCATOR_PROJ4)
    t.to_shp('/tmp/shp.zip', target_proj4=SPHERICAL_MERCATOR_PROJ4)

You can render your spatial vectors in Jupyter Notebook with the ``draw`` function. ::

    t = GeoTable.load('wkt.csv')
    t.draw()  # Render the geometries in Jupyter Notebook
