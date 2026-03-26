from setuptools import setup, find_namespace_packages

setup(
    name="cli-anything-openfoam",
    version="1.0.0",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    install_requires=[
        "click>=8.0.0",
        "prompt-toolkit>=3.0.0",
    ],
    entry_points={
        "console_scripts": [
            "cli-anything-openfoam=cli_anything.openfoam.openfoam_cli:main",
        ],
    },
    python_requires=">=3.10",
    package_data={
        "cli_anything.openfoam": ["skills/*.md"],
    },
)
