import os.path

from setuptools import setup, find_packages


BASE_DIR = os.path.abspath(os.path.dirname(__file__))


with open(os.path.join(BASE_DIR, "README.md")) as f:
    long_description = f.read()

with open(os.path.join(BASE_DIR, os.path.join("drf_ext", "__init__.py"))) as f:
    version = ""
    for line in f:
        if line.startswith("__version__"):
            version = line.partition("=")[-1].strip().strip("\"'")
            break


setup(
    name="drf-ext",
    version=version,
    description="Extensions for the DRF",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/heemayl/drf-ext",
    author="Readul Hasan Chayan [Heemayl]",
    author_email="me@heemayl.net",
    classifiers=[  # Optional
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
    ],
    keywords="django django-rest django_rest rest development",
    packages=find_packages(),
    python_requires=">=3.6",
    install_requires=["djangorestframework"],
    project_urls={
        "Bug Reports": "https://github.com/heemayl/drf-ext/issues",
        "Source": "https://github.com/heemayl/drf-ext",
    },
)
