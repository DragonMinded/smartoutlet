import os
from setuptools import setup  # type: ignore

dir_path = os.path.dirname(os.path.realpath(__file__))
with open(os.path.join(dir_path, "README.md"), "r", encoding="utf-8") as fh:
    long_description = fh.read()


setup(
    name='smartoutlet',
    version='0.1.3',
    description='Collection of utilities for interfacing with various PDUs and smart outlets.',
    long_description=long_description,
    long_description_content_type="text/markdown",
    author='DragonMinded',
    author_email='dragonminded@dragonminded.com',
    license='Public Domain',
    url='https://github.com/DragonMinded/smartoutlet',
    package_data={"smartoutlet": ["py.typed"]},
    packages=[
        'smartoutlet',
    ],
    install_requires=[
        'requests',
        'pysnmplib',
    ],
    python_requires=">=3.6",
)
