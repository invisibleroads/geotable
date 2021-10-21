from os import getenv
from os.path import expanduser, join


USER_FOLDER = expanduser('~')
CACHE_FOLDER = getenv(
    'GEOTABLE_CACHE_FOLDER',
    join(USER_FOLDER, '.cache', 'geotable'))
