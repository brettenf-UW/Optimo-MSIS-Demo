"""
Setup script for the school scheduling optimizer.
"""
from setuptools import setup, find_packages

setup(
    name="school-schedule-optimizer",
    version="0.1.0",
    description="School scheduling optimization tools",
    author="Optimo MSIS",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[
        "numpy>=1.22.0",
        "pandas>=1.4.0",
        "flask>=2.0.0",
        "flask-cors>=3.0.0",
        "werkzeug>=2.0.0",
        "python-dotenv>=0.19.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=2.0.0",
            "black>=22.0.0",
            "mypy>=0.900"
        ],
        "gurobi": ["gurobipy>=9.5.0"],
        "pulp": ["pulp>=2.6.0"]
    },
    entry_points={
        "console_scripts": [
            "schedule-optimizer=main:main",
        ],
    },
)