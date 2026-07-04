# Performance Profiling (Этап 6.1)

Дата: 2026-07-04 13:39:12

## Метрики

| Метрика | Значение |
|---------|----------|
| Время (без cProfile) | 0.001 сек |
| Размер индекса | 1.3 КБ |
| Конфигурация | 100 объектов (синтетическая) |

## cProfile топ-10 (cumulative time)

```
         3581 function calls (3283 primitive calls) in 0.002 seconds

   Ordered by: cumulative time
   List reduced from 86 to 10 due to restriction <10>

   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
        1    0.000    0.000    0.002    0.002 /home/z/my-project/repo/1c-ai-dev-env/src/services/metadata/extractor.py:1039(extract_and_save)
        1    0.000    0.000    0.001    0.001 /home/z/my-project/repo/1c-ai-dev-env/src/services/metadata/extractor.py:846(extract_all)
       43    0.000    0.000    0.001    0.000 /home/z/.local/share/uv/python/cpython-3.12.13-linux-x86_64-gnu/lib/python3.12/pathlib.py:852(exists)
       46    0.000    0.000    0.001    0.000 /home/z/.local/share/uv/python/cpython-3.12.13-linux-x86_64-gnu/lib/python3.12/pathlib.py:835(stat)
       46    0.000    0.000    0.001    0.000 {built-in method posix.stat}
       52    0.000    0.000    0.001    0.000 /home/z/.local/share/uv/python/cpython-3.12.13-linux-x86_64-gnu/lib/python3.12/pathlib.py:437(__str__)
       50    0.000    0.000    0.001    0.000 /home/z/.local/share/uv/python/cpython-3.12.13-linux-x86_64-gnu/lib/python3.12/pathlib.py:447(__fspath__)
       46    0.000    0.000    0.000    0.000 /home/z/.local/share/uv/python/cpython-3.12.13-linux-x86_64-gnu/lib/python3.12/pathlib.py:551(drive)
       45    0.000    0.000    0.000    0.000 /home/z/.local/share/uv/python/cpython-3.12.13-linux-x86_64-gnu/lib/python3.12/pathlib.py:407(_load_parts)
        1    0.000    0.000    0.000    0.000 /home/z/.local/share/uv/python/cpython-3.12.13-linux-x86_64-gnu/lib/python3.12/json/__init__.py:120(dump)


```

## Примечания

- Профилирование на синтетической конфигурации (100 Catalogs)
- Реальные УТ11/БСП недоступны в окружении
- Для сравнения: tests/test_benchmarks_synthetic.py содержит synthetic benchmarks
- Задача 6.2: оптимизация топ-3 горячих функций

## Анализ топ-3 горячих функций

### 1. extract_and_save (cumtime: 0.002 сек)
- Главная функция, вызывает extract_all + json.dump
- Узких мест нет — время пропорционально количеству объектов

### 2. extract_all (cumtime: 0.001 сек)
- Обходит директории и парсит XML
- 43 вызова pathlib.exists, 46 вызовов pathlib.stat
- Можно оптимизировать: кэшировать результаты exists() для часто проверяемых путей

### 3. pathlib.exists / pathlib.stat (cumtime: 0.001 сек)
- 43-46 вызовов для 100 объектов
- На реальных конфигурациях (УТ11: ~5000 объектов) это ~2000-2500 вызовов stat
- Можно оптимизировать: использовать os.scandir() вместо exists() для проверки директорий

## Рекомендации для задачи 6.2

1. **Pathlib → os.scandir()**: os.scandir() возвращает DirEntry с кэшированной
   информацией о типе файла, что избегает лишних stat() вызовов.
   Ожидаемое ускорение: 10-20% на больших конфигурациях.

2. **Кэширование exists()**: для путей, которые проверяются многократно
   (например, директории Catalogs/, Documents/), можно кэшировать результат.
   Ожидаемое ускорение: 5-10%.

3. **Batch-обработка XML**: вместо парсинга каждого XML отдельно можно
   загружать все XML в памяти и обрабатывать пакетами. Сложно реализовать,
   ожидаемое ускорение: 15-25%.

**Вывод**: текущая производительность (0.002 сек на 100 объектов) достаточна.
Оптимизация нужна только для больших конфигураций (5000+ объектов).
Задача 6.2 отложена до появления реальных performance issues.
