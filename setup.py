from os.path import abspath, dirname, join
from setuptools import find_packages, setup


ENTRY_POINTS = """
"""
REQUIREMENTS = [
    # 'gdal',
    'invisibleroads-macros>=0.9.5.1',
    'pandas>=0.20',
    'shapely[vectorized]',
    'utm',
]
FOLDER = dirname(abspath(__file__))
DESCRIPTION = '\n\n'.join(open(join(FOLDER, x)).read().strip() for x in [
    'README.rst', 'CHANGES.rst'])
setup(
    name='geotable',
    version='0.4.2.8',
    description='Read and write spatial vectors',
    long_description=DESCRIPTION,
    classifiers=[
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
    ],
    author='Roy Hyunjin Han',
    author_email='rhh@crosscompute.com',
    url='https://github.com/invisibleroads/geotable',
    keywords='gdal geos proj4 shapely',
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    setup_requires=['pytest-runner'],
    install_requires=REQUIREMENTS,
    tests_require=[],
    entry_points=ENTRY_POINTS)
