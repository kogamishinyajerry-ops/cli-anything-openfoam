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
            "cli-anything-starccm=cli_anything.starccm.starccm_cli:main",
            "cli-anything-xfoil=cli_anything.xfoil.xfoil_cli:main",
            "cli-anything-fluent=cli_anything.fluent.fluent_cli:main",
            "cli-anything-tecplot=cli_anything.tecplot.tecplot_cli:main",
            "cli-anything-visit=cli_anything.visit.visit_cli:main",
            "cli-anything-ragas=cli_anything.ragas.ragas_cli:main",
            "cli-anything-lm-eval=cli_anything.lm_eval.lm_eval_cli:main",
            "cli-anything-composio=cli_anything.composio.composio_cli:main",
            "cli-anything-godot=cli_anything.godot.godot_cli:main",
            "cli-anything-promptfoo=cli_anything.promptfoo.promptfoo_cli:main",
            "cli-anything-ink=cli_anything.ink.ink_cli:main",
            "cli-anything-backtrader=cli_anything.backtrader.backtrader_cli:main",
            "cli-anything-blender=cli_anything.blender.blender_cli:main",
            "cli-anything-calculix=cli_anything.calculix.calculix_cli:main",
            "cli-anything-timescaledb=cli_anything.timescaledb.timescaledb_cli:main",
        ],
    },
    python_requires=">=3.10",
    package_data={
        "cli_anything.openfoam": ["skills/*.md"],
    },
)
