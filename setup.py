from setuptools import setup

setup(
    name="fastapi-aws",
    version="0.1.0",
    packages=["fastapi_aws"],
    install_requires=[
        "fastapi",
    ],
    description="AWS Integration for FastAPI",
    author="Edward Grundy",
    author_email="ed@bayis.co.uk",
    url="https://github.com/bayinfosys/fastapi-aws",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
)
