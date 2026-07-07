# Карта: BSL LS диагностика → ITS стандарт → исправление

**Источники:** [v8std.ru](https://v8std.ru), [ITS 1С](https://its.1c.ru/db/v8std), [BSL Language Server](https://1c-syntax.github.io/bsl-language-server)  
**Связанные инструменты:** `analyze_queries`, `validate_query_static`, `solve_check`, `check_standards`

> Полная карта cross-reference между диагностиками BSL LS, стандартами 1С (ITS) и нашими правилами QueryAnalyzer. Используется при `solve_check` для перехода "правило → стандарт → как исправить".

---

## 1. Запросы (SQL)

| BSL LS диагностика | ITS стандарт | Что проверяет | Как исправить |
|---|---|---|---|
| `AssignAliasFieldsInQuery` | [#std437](https://its.1c.ru/db/v8std/content/437/hdoc), [#std758](https://its.1c.ru/db/v8std/content/758/hdoc) | Поля в SELECT без алиаса | Добавить `КАК ИмяПоля` для каждого поля |
| `CreateQueryInCycle` | [#std436](https://its.1c.ru/db/v8std/content/436/hdoc) | Запрос в цикле (N+1) | Заменить на один запрос с `В (&Массив)` |
| `FieldsFromJoinsWithoutIsNull` | [#std655](https://its.1c.ru/db/v8std/content/655/hdoc) | Поля из LEFT JOIN без проверки `ЕСТЬ NULL` | Добавить `ЕСТЬNULL(Поле, Значение)` |
| `FullOuterJoinQuery` | [#std435](https://its.1c.ru/db/v8std/content/435/hdoc) | Полное внешнее соединение | Заменить на 2 LEFT JOIN + ОБЪЕДИНИТЬ ВСЕ |
| `IncorrectUseLikeInQuery` | [#std726](https://its.1c.ru/db/v8std/content/726/hdoc) | Неправильное использование `ПОДОБНО` | Использовать `текст%` вместо `%текст` |
| `JoinWithSubQuery` | [#std655](https://its.1c.ru/db/v8std/content/655/hdoc) | JOIN с подзапросом | Вынести подзапрос во временную таблицу с индексом |
| `JoinWithVirtualTable` | [#std655](https://its.1c.ru/db/v8std/content/655/hdoc) | JOIN с виртуальной таблицей | Сначала `ПОМЕСТИТЬ ВТ_... ИНДЕКСИРОВАТЬ ПО`, потом JOIN |
| `LogicalOrInJoinQuerySection` | [#std658](https://its.1c.ru/db/v8std/content/658/hdoc) | ИЛИ в условии JOIN | Разбить на несколько JOIN'ов + ОБЪЕДИНИТЬ ВСЕ |
| `LogicalOrInTheWhereSectionOfQuery` | [#std658](https://its.1c.ru/db/v8std/content/658/hdoc) | ИЛИ в WHERE — блокирует индекс | Заменить на ОБЪЕДИНИТЬ ВСЕ |
| `MultilineStringInQuery` | [#std437](https://its.1c.ru/db/v8std/content/437/hdoc) | Многострочная строка без `\|` | Использовать `\|` в начале каждой строки |
| `QueryNestedFieldsByDot` | [#std654](https://its.1c.ru/db/v8std/content/654/hdoc) | Обращение через точку к составному типу | Использовать `ВЫРАЗИТЬ(... КАК Документ.Имя)` |
| `QueryParseError` | — | Ошибка парсинга SDBL | Проверить синтаксис |
| `QueryToMissingMetadata` | — | Запрос к несуществующей таблице | Проверить имя метаданных |
| `RefOveruse` | [#std654](https://its.1c.ru/db/v8std/content/654/hdoc) | Чрезмерное `.Ссылка` (разыменование) | Использовать `ВЫРАЗИТЬ()` для конкретного типа |
| `SelectTopWithoutOrderBy` | [#std412](https://its.1c.ru/db/v8std/content/412/hdoc) | `ПЕРВЫЕ N` без `УПОРЯДОЧИТЬ ПО` | Добавить `УПОРЯДОЧИТЬ ПО` (какие N?) |
| `UsingLikeInQuery` | [#std726](https://its.1c.ru/db/v8std/content/726/hdoc) | Предупреждение о `ПОДОБНО` | Убедиться что нет `%текст` (full scan) |
| `VirtualTableCallWithoutParameters` | [#std657](https://its.1c.ru/db/v8std/content/657/hdoc) | Виртуальная таблица без параметров | Передать параметры (Период, Условие) |

---

## 2. Производительность

| BSL LS диагностика | ITS стандарт | Что проверяет | Как исправить |
|---|---|---|---|
| `CollectingAttributesInLoop` | [#std436](https://its.1c.ru/db/v8std/content/436/hdoc) | Обращение к метаданным в цикле | Закэшировать метаданные до цикла |
| `DataExchangeLoading` | [#std503](https://its.1c.ru/db/v8std/content/503/hdoc) | Проверка `ОбменДанными.Загрузка` без нужды | Использовать только в обработчиках |
| `MethodsOutOfRegion` | [#std458](https://its.1c.ru/db/v8std/content/458/hdoc) | Методы вне области | Обернуть в `#Область ... #КонецОбласти` |

---

## 3. Стандарты кода (STANDARD)

| BSL LS диагностика | ITS стандарт | Что проверяет | Как исправить |
|---|---|---|---|
| `BeginTransactionBeforeTryCatch` | [#std649](https://its.1c.ru/db/v8std/content/649/hdoc) | `Попытка` до `НачатьТранзакцию` | Сначала `НачатьТранзакцию`, потом `Попытка` |
| `CommitTransactionOutsideTryCatch` | [#std649](https://its.1c.ru/db/v8std/content/649/hdoc) | `ЗафиксироватьТранзакцию` без `Попытка` | Обернуть в `Попытка/Исключение` |
| `IfElseDuplicatedCode` | [#std504](https://its.1c.ru/db/v8std/content/504/hdoc) | Дублирование кода в ветках if/else | Вынести общий код |
| `IfElseIfEndsWithElse` | [#std504](https://its.1c.ru/db/v8std/content/504/hdoc) | Если без Иначе | Добавить `Иначе` или `ВызватьИсключение` |
| `NestedConstructorsInStructureDeclaration` | [#std559](https://its.1c.ru/db/v8std/content/559/hdoc) | Вложенные конструкторы в Структура() | Разбить на отдельные операторы |
| `NonExportMethodsInApiRegion` | [#std458](https://its.1c.ru/db/v8std/content/458/hdoc) | Не-экспортные методы в области ПрограммныйИнтерфейс | Перенести в СлужебныеПроцедурыИФункции |
| `SelfAssign` | [#std508](https://its.1c.ru/db/v8std/content/508/hdoc) | Присваивание переменной самой себе | Убрать или исправить правую часть |
| `UnknownPropertyAccess` | — | Обращение к несуществующему свойству | Проверить имя свойства |
| `UseLessForEach` | [#std504](https://its.1c.ru/db/v8std/content/504/hdoc) | Бесполезный цикл `Для Каждого` | Заменить на прямую выборку |

---

## 4. Транзакции

| BSL LS диагностика | ITS стандарт | Что проверяет | Как исправить |
|---|---|---|---|
| `BeginTransactionBeforeTryCatch` | [#std649](https://its.1c.ru/db/v8std/content/649/hdoc) | Транзакция без Try/Catch | Обернуть в `Попытка/Исключение` |
| `CommitTransactionOutsideTryCatch` | [#std649](https://its.1c.ru/db/v8std/content/649/hdoc) | `ЗафиксироватьТранзакцию` вне Try | Перенести в `Попытка` |
| `RollbackTransactionOutsideTryCatch` | [#std649](https://its.1c.ru/db/v8std/content/649/hdoc) | `ОтменитьТранзакцию` вне `Исключение` | Только в `Исключение` ветке |

---

## 5. Безопасность

| BSL LS диагностика | ITS стандарт | Что проверяет | Как исправить |
|---|---|---|---|
| `ExecutingOfOSCommand` | [#std482](https://its.1c.ru/db/v8std/content/482/hdoc) | `ЗапуститьПриложение()` в коде | Только для клиентских спец-случаев |
| `ExternalAppStarting` | [#std482](https://its.1c.ru/db/v8std/content/482/hdoc) | Запуск внешних приложений | Использовать `НачатьЗапускПриложения` |
| `InternetAccess` | [#std483](https://its.1c.ru/db/v8std/content/483/hdoc) | HTTP-запросы без проверки | Валидировать URL и параметры |
| `PasswordsInCode` | [#std485](https://its.1c.ru/db/v8std/content/485/hdoc) | Пароли в исходниках | Хранить в безопасном хранилище |

---

## 6. Дизайн кода (DESIGN)

| BSL LS диагностика | ITS стандарт | Что проверяет | Как исправить |
|---|---|---|---|
| `CognitiveComplexity` | [#std456](https://its.1c.ru/db/v8std/content/456/hdoc) | Высокая когнитивная сложность | Разбить на методы < 50 строк |
| `CyclomaticComplexity` | [#std456](https://its.1c.ru/db/v8std/content/456/hdoc) | Цикломатическая сложность > 20 | Уменьшить количество if/while/for |
| `DuplicateRegion` | [#std458](https://its.1c.ru/db/v8std/content/458/hdoc) | Дублирующаяся область | Объединить в одну |
| `EmptyRegion` | [#std458](https://its.1c.ru/db/v8std/content/458/hdoc) | Пустая область | Удалить или заполнить |
| `MissingCodeTryCatchEx` | [#std510](https://its.1c.ru/db/v8std/content/510/hdoc) | Пустой `Исключение` | Добавить логирование |

---

## 7. Сопоставление с нашими правилами QueryAnalyzer

| Наше правило | BSL LS эквивалент | Категория | Описание |
|---|---|---|---|
| Q001 | — | SQL | Запрос к виртуальной таблице без параметров |
| Q002 | `QueryNestedFieldsByDot` | SQL | Обращение через точку к составному типу |
| Q003 | — | SQL | Запрос без условий WHERE на большой таблице |
| Q004 | `CreateQueryInCycle` | PERF | Запрос в цикле |
| Q005 | `UsingLikeInQuery` | SQL | ПОДОБНО с `%текст` (full scan) |
| Q010 | `CreateQueryInCycle` | PERF | Запрос в цикле (N+1) |
| Q011 | `VirtualTableCallWithoutParameters` | SQL | Виртуальная таблица без параметров |
| Q012 | `RefOveruse` | PERF | Чрезмерное разыменование ссылок |
| Q013 | — | PERF | `ВЫБРАТЬ *` — выбраны все поля |
| Q014 | `MultilineStringInQuery` | STANDARD | Строка запроса без `\|` |
| Q015 | `FieldsFromJoinsWithoutIsNull` | SQL | Поля из JOIN без ЕСТЬNULL |
| Q016 | `LogicalOrInJoinQuerySection` | SQL | ИЛИ в JOIN |
| Q017 | `AssignAliasFieldsInQuery` | STANDARD | Поля без КАК в SELECT |
| Q018 | `SelectTopWithoutOrderBy` | STANDARD | ПЕРВЫЕ N без УПОРЯДОЧИТЬ ПО |
| Q019 | — | PERF, STANDARD | `Количество() > 0` вместо `Пустой()` (#std438) |

---

## 8. Использование карты в `solve_check`

При вызове `solve_check` с идентификатором диагностики BSL LS или нашего правила:

1. Найти строку в таблице выше
2. Прочитать связанный стандарт ITS по URL
3. Применить шаблон исправления
4. Проверить, что нет других затронутых правил

Пример цепочки:
```
solve_check({diagnostic: "FieldsFromJoinsWithoutIsNull"})
  ↓
[#std655] Ограничения на соединения с вложенными запросами
  ↓
Шаблон: ЕСТЬNULL(Б.Поле, ЗначениеПоУмолчанию)
  ↓
Дополнительная проверка: нет ли других полей из Б без ЕСТЬNULL
```

---

## 9. Источники

- **v8std.ru:** https://v8std.ru — 317 стандартов + 809 диагностик с cross-reference
- **ITS 1С:** https://its.1c.ru/db/v8std — оригинальные стандарты 1С
- **BSL LS:** https://1c-syntax.github.io/bsl-language-server — 184 диагностики
- **Наш предыдущий анализ:** /home/z/my-project/download/KB_SOURCES_RESEARCH.md
