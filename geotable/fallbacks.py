try:
    from pandas.errors import EmptyDataError
except ImportError:
    from pandas.io.common import EmptyDataError
