"""
Setup configuration for Stock Options ML Agent
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="stock-options-ml-agent",
    version="0.1.0",
    author="Options Trading AI",
    description="Intelligent Multi-Strategy Options Prediction Engine",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/your-org/stock-options-ml-agent",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Intended Audience :: Financial and Insurance Industry",
        "Topic :: Office/Business :: Financial :: Investment",
    ],
    python_requires=">=3.9",
    install_requires=[
        # Data & Analysis
        "pandas>=2.0.0",
        "numpy>=1.24.0",
        "scipy>=1.11.0",

        # Technical Analysis
        "ta-lib>=0.4.28",
        "pandas-ta>=0.3.14b0",

        # Machine Learning
        "scikit-learn>=1.3.0",
        "xgboost>=2.0.0",
        "tensorflow>=2.13.0",

        # APIs & Data
        "yfinance>=0.2.28",
        "requests>=2.31.0",
        "python-dotenv>=1.0.0",

        # Utilities
        "pyyaml>=6.0",
        "python-dateutil>=2.8.2",
        "pytz>=2023.3",

        # Visualization
        "matplotlib>=3.7.0",
        "plotly>=5.15.0",
        "seaborn>=0.12.0",

        # Backtesting
        "backtrader>=1.9.98.123",

        # Database
        "sqlalchemy>=2.0.20",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0",
            "black>=23.7.0",
            "flake8>=6.1.0",
            "mypy>=1.5.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "stock-options-agent=main:main",
        ],
    },
)
