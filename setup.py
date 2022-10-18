from setuptools import setup
from setuptools import find_packages


setup(
    name='Bellatrix',
    version='0.1',
    description='A 32-bit RISC-V soft-processor',
    author='Ángel Terrones',
    author_email='angelterrones@gmail.com',
    license='BSD',
    python_requires='>=3.6',
    install_requires=["amaranth>=0.1rc1"],
    packages=find_packages(),
    project_urls={
        "Source Code": "https://github.com/angelterrones/bellatrix",
        "Bug Tracker": "https://github.com/angelterrones/bellatrix/issues"
    }
)
