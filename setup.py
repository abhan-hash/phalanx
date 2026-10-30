from setuptools import setup, find_packages

setup(
    name="phalanx",
    version="0.1.0",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    install_requires=[
        "openai>=1.0.0",
        "pydantic>=2.0.0",
        "pyyaml>=6.0",
        "rich>=13.0.0",
        "click>=8.0.0",
        "fastapi>=0.100.0",
        "uvicorn>=0.22.0",
        "requests>=2.28.0",
        "python-dotenv>=1.0.0",
    ],
    entry_points={
        "console_scripts": [
            "phalanx = phalanx.cli:main",
        ],
    },
)
