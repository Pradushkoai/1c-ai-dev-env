# Sphinx configuration for 1c-ai-dev-env (P2.6: Documentation as Code)
#
# Автогенерация документации из docstring + doctest.
# Запуск: sphinx-build -b html docs/sphinx/ docs/sphinx/_build/html

import os
import sys

# Добавляем корень проекта в sys.path для autodoc
sys.path.insert(0, os.path.abspath("../.."))

project = "1C AI Development Environment"
author = "Pradushkoai"
copyright = "2026, Pradushkoai"
release = "5.4.0"

# Extensions
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.doctest",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "myst_parser",
    "sphinx_autodoc_typehints",
]

# MyST parser for Markdown
myst_enable_extensions = [
    "dollarmath",
    "amsmath",
    "deflist",
    "html_admonition",
    "html_image",
    "colon_fence",
    "smartquotes",
    "replacements",
    "linkify",
    "substitution",
]

# autodoc settings
autodoc_default_options = {
    "members": True,
    "member-order": "bysource",
    "special-members": "__init__",
    "undoc-members": True,
    "exclude-members": "__weakref__",
}
autodoc_typehints = "description"

# Napoleon settings (Google/NumPy docstrings)
napoleon_google_docstring = True
napoleon_numpy_docstring = False

# doctest settings
doctest_global_setup = """
import sys
sys.path.insert(0, ".")
"""

# Intersphinx
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "networkx": ("https://networkx.org/documentation/stable/", None),
}

# HTML output
html_theme = "alabaster"
html_static_path = ["_static"]
html_theme_options = {
    "github_user": "Pradushkoai",
    "github_repo": "1c-ai-dev-env",
    "github_banner": True,
    "github_button": True,
    "show_powered_by": False,
    "show_related": False,
    "note_bg": "#FFF59D",
}

# Source files
source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

# Warnings
suppress_warnings = ["myst.header"]

# Master document
master_doc = "index"
