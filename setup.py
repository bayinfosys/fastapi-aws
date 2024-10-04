# setup.py
from setuptools import setup, find_packages

setup(
    name='fastapi-aws',
    version='0.1.0',
    packages=find_packages(),
    install_requires=[
        'fastapi>=0.70.0',
    ],
    description='AWS Integration for FastAPI',
    author='Edward Grundy',
    author_email='ed@bayis.co.uk',
    url='https://github.com/bayinfosys/fastapi-aws',
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.6',
)
