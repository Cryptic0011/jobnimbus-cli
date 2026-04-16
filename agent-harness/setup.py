"""Setup for cli-anything-jobnimbus — read-only CLI for JobNimbus API."""

from setuptools import setup, find_packages

setup(
    name="cli-anything-jobnimbus",
    version="0.2.0",
    description="Read-only agent-native CLI for auditing everything in JobNimbus",
    long_description=open("cli_anything/jobnimbus/README.md").read(),
    long_description_content_type="text/markdown",
    author="Grayson Patterson",
    python_requires=">=3.9",
    packages=find_packages(),
    install_requires=[
        "click>=8.0",
        "requests>=2.28",
    ],
    extras_require={
        "dev": ["pytest>=7.0", "responses>=0.23"],
    },
    entry_points={
        "console_scripts": [
            "cli-anything-jobnimbus=cli_anything.jobnimbus.jobnimbus_cli:main",
            "jn=cli_anything.jobnimbus.jobnimbus_cli:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries",
        "Programming Language :: Python :: 3",
    ],
    package_data={
        "cli_anything.jobnimbus": ["skills/*.md", "tests/*.md", "README.md"],
    },
)
