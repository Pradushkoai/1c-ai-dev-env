1C AI Development Environment
=============================

.. toctree::
   :maxdepth: 2
   :caption: API Reference

   api/services
   api/models
   api/mcpserver

.. toctree::
   :maxdepth: 2
   :caption: Guides

   guides/architecture
   guides/mcp_integration

.. toctree::
   :maxdepth: 1
   :caption: References

   references/changelog

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

---

**P2.6: Documentation as Code** — автогенерация документации из docstring + doctest.

Запуск::

    sphinx-build -b html docs/sphinx/ docs/sphinx/_build/html
    pytest --doctest-modules src/
