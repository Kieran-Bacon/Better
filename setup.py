import os
from setuptools import setup, find_packages

with open(os.path.abspath(os.path.join(os.path.dirname(__file__), "README.md")), "r") as handler:
      README = handler.read()
requires = []

setup(name='better',
      install_requires=requires,
      version="0.0.1",
      description="Extend packages include additional desired features",
      long_description=README,
      long_description_content_type="text/markdown",

      author="Kieran Bacon",
      author_email="Kieran.Bacon@outlook.com",
      url="https://github.com/Kieran-Bacon/Better",

      packages=find_packages()
)