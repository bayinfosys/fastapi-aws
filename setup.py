from setuptools import setup

setup(
    name="fastapi-aws",
    use_scm_version={
        "write_to": "fastapi_aws/_version.py",
    },
    packages=["fastapi_aws", "fastapi_aws.integrations"],
    install_requires=[
        "fastapi",
        "httpx",
        "uvicorn[standard]"
    ],
    description="AWS Integrations for FastAPI exported OpenAPI specifications",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
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
