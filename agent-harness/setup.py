from setuptools import setup, find_namespace_packages

setup(
    name="cli-anything-cfd",
    version="2.0.0",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    install_requires=[
        "click>=8.0.0",
        "prompt-toolkit>=3.0.0",
    ],
    entry_points={
        "console_scripts": [
            "cli-anything-openfoam=cli_anything.openfoam.openfoam_cli:main",
            "cli-anything-gmsh=cli_anything.gmsh.gmsh_cli:main",
            "cli-anything-freecad=cli_anything.freecad.freecad_cli:main",
            "cli-anything-paraview=cli_anything.paraview.paraview_cli:main",
            "cli-anything-su2=cli_anything.su2.su2_cli:main",
            "cli-anything-dakota=cli_anything.dakota.dakota_cli:main",
        ],
    },
    python_requires=">=3.10",
    package_data={
        "cli_anything.openfoam": ["skills/*.md"],
    },
)
