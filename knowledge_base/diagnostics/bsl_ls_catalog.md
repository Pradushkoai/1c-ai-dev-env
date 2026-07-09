# Каталог диагностик BSL Language Server

**Источник:** [1c-syntax/bsl-language-server](https://1c-syntax.github.io/bsl-language-server)  
**Всего диагностик:** 184  
**Тегов категорий:** 12

## Теги категорий

| Тег | Описание |
|-----|----------|
| STANDARD | Нарушение стандартов 1С |
| SQL | Проблемы с запросами 1С |
| PERFORMANCE | Проблема производительности |
| BRAINOVERLOAD | Сложный для понимания код |
| BADPRACTICE | Плохая практика |
| CLUMSY | Не нужные конструкции |
| DESIGN | Ошибки проектирования |
| SUSPICIOUS | Странный код |
| UNPREDICTABLE | Непредсказуемое поведение |
| DEPRECATED | Устаревшее |
| ERROR | Ошибки кода |
| LOCALIZE | Проблемы локализации |

---

## SQL — Диагностики запросов (17 шт)

| # | Diagnostic | Описание | Теги | У нас? |
|---|------------|----------|------|--------|
| 1 | AssignAliasFieldsInQuery | Поля без алиасов в SELECT | STANDARD | ❌ |
| 2 | CreateQueryInCycle | Запрос в цикле (N+1) | PERFORMANCE, ERROR | ✅ Q010 |
| 3 | FieldsFromJoinsWithoutIsNull | Поля из JOIN без IS NULL | SUSPICIOUS | ❌ |
| 4 | FullOuterJoinQuery | Полное внешнее соединение | PERFORMANCE | ✅ O003 |
| 5 | IncorrectUseLikeInQuery | Неправильное ПОДОБНО | PERFORMANCE | ✅ Q005 |
| 6 | JoinWithSubQuery | JOIN с подзапросом | PERFORMANCE | ✅ O004 |
| 7 | JoinWithVirtualTable | JOIN с виртуальной таблицей | PERFORMANCE | ❌ |
| 8 | LogicalOrInJoinQuerySection | ИЛИ в секции JOIN | PERFORMANCE | ❌ |
| 9 | LogicalOrInTheWhereSectionOfQuery | ИЛИ в WHERE | PERFORMANCE | ✅ O002 |
| 10 | MultilineStringInQuery | Многострочный литерал в запросе | SUSPICIOUS | ❌ |
| 11 | QueryNestedFieldsByDot | Обращение через точку | DESIGN | ✅ FIELD_CHAIN_INVALID |
| 12 | QueryParseError | Ошибка парсинга | ERROR | ✅ PARSE_ERROR |
| 13 | QueryToMissingMetadata | Запрос к несуществующим метаданным | ERROR | ✅ TABLE_NOT_FOUND |
| 14 | RefOveruse | Чрезмерное .Ссылка | PERFORMANCE | ❌ |
| 15 | SelectTopWithoutOrderBy | TOP без ORDER BY | UNPREDICTABLE | ✅ O001 |
| 16 | UsingLikeInQuery | Использование ПОДОБНО | STANDARD | ⚠️ |
| 17 | VirtualTableCallWithoutParameters | Виртуальная таблица без параметров | PERFORMANCE | ❌ |

---

## PERFORMANCE — Производительность (не только запросы)

| # | Diagnostic | Описание | Теги |
|---|------------|----------|------|
| 1 | CachedPublic | Кэшируемый общий модуль — публичные методы | PERFORMANCE |
| 2 | CodeOutOfRegion | Код вне областей | BRAINOVERLOAD |
| 3 | CognitiveComplexity | Когнитивная сложность | BRAINOVERLOAD |
| 4 | CyclomaticComplexity | Цикломатическая сложность | BRAINOVERLOAD |
| 5 | EmptyCodeBlock | Пустой блок кода | CLUMSY |
| 6 | ExcessiveAutoTestCheck | Чрезмерная проверка ОбменДанными.Загрузка | CLUMSY |

---

## STANDARD — Стандарты 1С (не только запросы)

| # | Diagnostic | Описание | Теги |
|---|------------|----------|------|
| 1 | CanonicalSpellingKeywords | Каноническое написание ключевых слов | STANDARD |
| 2 | CodeBlockBeforeSub | Код до первой процедуры/функции | STANDARD |
| 3 | CommonModuleNameCached | Имя общего модуля — Кэшируемый | STANDARD |
| 4 | CommonModuleNameClient | Имя общего модуля — Клиентский | STANDARD |
| 5 | CommonModuleNameClientServer | Имя общего модуля — КлиентСервер | STANDARD |
| 6 | CommonModuleNameFullAccess | Имя общего модуля — Полные права | STANDARD |
| 7 | CommonModuleNameGlobal | Имя общего модуля — Глобальный | STANDARD |
| 8 | CommonModuleNameServerCall | Имя общего модуля — Серверный вызов | STANDARD |
| 9 | CommonModuleNameWords | Слова в имени общего модуля | STANDARD |
| 10 | CompilationDirectiveLost | Потеряна директива компиляции | STANDARD |
| 11 | CompilationDirectiveNeedLess | Избыточная директива компиляции | STANDARD |
| 12 | ConsecutiveEmptyLines | Подряд идущие пустые строки | STANDARD |
| 13 | DuplicateRegion | Дублирование областей | STANDARD |
| 14 | EmptyRegion | Пустая область | STANDARD |
| 15 | ForbiddenMetadataName | Запрещённое имя метаданных | STANDARD |
| 16 | FunctionNameStartsWithGet | Функция начинается с Получить | STANDARD |
| 17 | MetadataObjectNameLength | Длина имени объекта метаданных | STANDARD |
| 18 | MissingSpace | Отсутствие пробелов | STANDARD |
| 19 | ReservedParameterNames | Зарезервированные имена параметров | STANDARD |
| 20 | SameMetadataObjectAndChildNames | Одинаковые имена объекта и дочернего | STANDARD |

---

## ERROR — Ошибки кода

| # | Diagnostic | Описание | Теги |
|---|------------|----------|------|
| 1 | AllFunctionPathMustHaveReturn | Не все пути функции возвращают значение | ERROR |
| 2 | AssignToReadOnlyProperty | Присвоение readonly свойству | ERROR |
| 3 | CommandModuleExportMethods | Экспортные методы в модуле команды | ERROR |
| 4 | CompareWithBoolean | Сравнение с булевым | CLUMSY |
| 5 | DeletingCollectionItem | Удаление элемента при обходе коллекции | ERROR |
| 6 | EventHandlerInvalidSignature | Неверная сигнатура обработчика | ERROR |
| 7 | EventHandlerOutsideEventRegion | Обработчик вне области событий | STANDARD |
| 8 | MissingCodeTryCatchEx | Код в Try без Catch | ERROR |

---

## BADPRACTICE / DEPRECATED

| # | Diagnostic | Описание | Теги |
|---|------------|----------|------|
| 1 | BadExceptionCategory | Неверная категория исключения | BADPRACTICE |
| 2 | CommentedCode | Закомментированный код | BADPRACTICE |
| 3 | DeprecatedCurrentDate | Устаревший ТекущаяДата() | DEPRECATED |
| 4 | DeprecatedFind | Устаревший Найти() | DEPRECATED |
| 5 | DeprecatedMessage | Устаревший Сообщить() | DEPRECATED |
| 6 | DeprecatedMethodCall | Вызов устаревшего метода | DEPRECATED |
| 7 | DeprecatedTypeManagedForm | Устаревший тип УправляемаяФорма | DEPRECATED |
| 8 | DoubleNegatives | Двойное отрицание | CLUMSY |
| 9 | DuplicateStringLiteral | Дублирование строкового литерала | BADPRACTICE |
| 10 | DuplicatedInsertionIntoCollection | Дублирование вставки в коллекцию | BADPRACTICE |
| 11 | EmptyStatement | Пустой оператор (;) | CLUMSY |

---

## DESIGN / SUSPICIOUS / UNPREDICTABLE

| # | Diagnostic | Описание | Теги |
|---|------------|----------|------|
| 1 | CommonModuleAssign | Присвоение общему модулю | DESIGN |
| 2 | CommonModuleInvalidType | Неверный тип общего модуля | DESIGN |
| 3 | CommonModuleMissingAPI | Общий модуль без API | DESIGN |
| 4 | CommonModuleVariables | Переменные в общем модуле | DESIGN |
| 5 | DataExchangeLoading | Проверка ОбменДанными.Загрузка | SUSPICIOUS |
| 6 | DenyIncompleteValues | Запрет неполных значений | DESIGN |
| 7 | ExecuteExternalCodeInCommonModule | Выполнение внешнего кода | UNPREDICTABLE |
| 8 | MissingCommonModuleMethod | Отсутствует метод общего модуля | ERROR |

---

## TRANSACTIONS

| # | Diagnostic | Описание | Теги |
|---|------------|----------|------|
| 1 | BeginTransactionBeforeTryCatch | BeginTransaction перед TryCatch | ERROR |
| 2 | CommitTransactionOutsideTryCatch | CommitTransaction вне TryCatch | ERROR |
| 3 | PairingBrokenTransaction | Нарушенная пара транзакций | ERROR |
| 4 | WrongUseOfRollbackTransactionMethod | Неправильный откат транзакции | ERROR |

---

## SECURITY

| # | Diagnostic | Описание | Теги |
|---|------------|----------|------|
| 1 | DisableSafeMode | Отключение безопасного режима | UNPREDICTABLE |
| 2 | PrivilegedModuleMethodCall | Вызов привилегированного метода | SUSPICIOUS |
| 3 | SetPrivilegedMode | Установка привилегированного режима | UNPREDICTABLE |
| 4 | UnsafeFindByCode | Небезопасный поиск по коду | SUSPICIOUS |
| 5 | UnsafeSafeModeMethodCall | Небезопасный вызов безопасного режима | UNPREDICTABLE |

---

## Ссылки

- [Полный список диагностик](https://1c-syntax.github.io/bsl-language-server/diagnostics/)
- [Теги категорий](https://1c-syntax.github.io/bsl-language-server/en/contributing/DiagnosticTag)
- [Стандарты 1С на v8std.ru](https://v8std.ru) — 317 стандартов + 809 диагностик
- [Стандарты 1С на ITS](https://its.1c.ru/db/v8std) — официальный источник
