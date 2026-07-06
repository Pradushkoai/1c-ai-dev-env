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

Этапы улучшения (4.4)
----------------------

Sphinx-документация актуализирована под архитектуру после Этапов 1-2:

- **Этап 1.2**: 14 скриптов перенесено в ``src/services/``.
  Добавлены модули: ``analyzers/`` (9 анализаторов + ``standards/``),
  ``diff``, ``code_generator``, ``code_validator``, ``epf_builder``, ``cf/``.
- **Этап 2.1**: ``check_1c_standards.py`` декомпозирован на 5 модулей в ``standards/``.
- **Этап 2.2**: ``epf_factory.py`` декомпозирован на 4 модуля в ``epf/``.
- **Этап 2.3**: ``metadata_extractor.py`` перенесён в ``metadata/``.
- **Этап 2.4**: ``build_config_index_generic.py`` перенесён в ``builders/``.
- **Этап 2.5**: ``cfe_manager.py`` декомпозирован — dataclasses и CLI в ``cfe/``.

См. также:

- `Stability Matrix <https://github.com/Pradushkoai/1c-ai-dev-env#stability-matrix>`_
  — маркировка стабильности каждой подсистемы.
- `ADR <https://github.com/Pradushkoai/1c-ai-dev-env/tree/main/adr>`_
  — архитектурные решения (ADR-0006 scope reduction, ADR-0007 v8unpack,
  ADR-0008 language policy).
- `CONTRIBUTING.md <https://github.com/Pradushkoai/1c-ai-dev-env/blob/main/CONTRIBUTING.md>`_
  — how-to гайды для контрибьюторов.
