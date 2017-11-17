from shapely.geometry import GeometryCollection


class ColorfulGeometryCollection(GeometryCollection):

    def __init__(self, geoms=None, colors=None):
        """
        Parameters
        ----------
        geoms : list
            A list of shapely geometry instances, which may be heterogenous.
        colors : list
            A list of html colors to render the geometries in Jupyter Notebook.

        Example
        -------
        Create a GeometryCollection with a Point and a LineString.

          >>> p = Point(51, -1)
          >>> l = LineString([(52, -1), (49, 2)])
          >>> gc = GeometryCollection([p, l], colors=['red', 'blue'])
        """
        super(ColorfulGeometryCollection, self).__init__(geoms)
        self.colors = colors or []

    def svg(self, scale_factor=1., color=None):
        """Returns a group of SVG elements for the multipart geometry.

        Parameters
        ==========
        scale_factor : float
            Multiplication factor for the SVG stroke-width.  Default is 1.
        color : str, optional
            Hex string for stroke or fill color. Default is to use "#66cc99"
            if geometry is valid, and "#ff3333" if invalid.
        """
        if self.is_empty:
            return '<g />'
        if not self.colors:
            return super(ColorfulGeometryCollection, self).svg(
                scale_factor, color)
        return '<g>' + ''.join(p.svg(scale_factor, c) for p, c in zip(
            self, self.colors)) + '</g>'
