# Паттерн: Создание документа

## Когда использовать
Когда нужно создать документ для регистрации хозяйственной операции.

## Структура метаданных

```xml
<Document uuid="...">
    <Properties>
        <Name>ИмяДокумента</Name>
        <Synonym>...</Synonym>
        <NumberLength>11</NumberLength>
        <CheckUnique>true</CheckUnique>
        <DefaultObjectForm>Document.Имя.ФормаДокумента</DefaultObjectForm>
        <DefaultListForm>Document.Имя.ФормаСписка</DefaultListForm>
        <RegisterRecords>
            <xr:Item>РегистрНакопления.ОстаткиНоменклатуры</xr:Item>
        </RegisterRecords>
    </Properties>
    <ChildObjects>
        <Attribute uuid="...">
            <Properties>
                <Name>Контрагент</Name>
                <Type>
                    <v8:Type>cfg:CatalogRef.Контрагенты</v8:Type>
                </Type>
            </Properties>
        </Attribute>
        <TabularSection uuid="...">
            <Properties>
                <Name>Товары</Name>
            </Properties>
            <ChildObjects>
                <Attribute uuid="...">
                    <Properties>
                        <Name>Номенклатура</Name>
                        <Type>
                            <v8:Type>cfg:CatalogRef.Номенклатура</v8:Type>
                        </Type>
                    </Properties>
                </Attribute>
                <Attribute uuid="...">
                    <Properties>
                        <Name>Количество</Name>
                        <Type>
                            <v8:Type>xs:decimal</v8:Type>
                            <v8:NumberQualifiers>
                                <v8:Digits>15</v8:Digits>
                                <v8:FractionDigits>3</v8:FractionDigits>
                                <v8:AllowedSign>Nonnegative</v8:AllowedSign>
                            </v8:NumberQualifiers>
                        </Type>
                    </Properties>
                </Attribute>
            </ChildObjects>
        </TabularSection>
    </ChildObjects>
</Document>
```

## Модуль объекта (ObjectModule.bsl)

```bsl
#Область ОбработчикиСобытий

Процедура ОбработкаПроведения(Отказ, Режим)
    
    // Движения по регистрам
    Движения.ОстаткиНоменклатуры.Записывать = Истина;
    
    Для Каждого СтрокаТовары Из Товары Цикл
        Движение = Движения.ОстаткиНоменклатуры.Добавить();
        Движение.ВидДвижения = ВидДвиженияНакопления.Расход;
        Движение.Период = Дата;
        Движение.Номенклатура = СтрокаТовары.Номенклатура;
        Движение.Количество = СтрокаТовары.Количество;
    КонецЦикла;
    
КонецПроцедуры

Процедура ОбработкаУдаленияПроведения(Отказ)
    // Очистка движений
КонецПроцедуры

#КонецОбласти
```

## Best Practices

1. **Нумерация**: NumberLength=11, CheckUnique=true
2. **Регистры**: указывайте RegisterRecords для документов с движениями
3. **Табличные части**: используйте для многострочных данных (Товары, Услуги)
4. **ОбработкаПроведения**: всегда реализуйте для проведения
5. **ВидДвижения**: используйте Приход/Расход для регистров накопления
6. **Период**: всегда устанавливайте Период = Дата

## Антипаттерны

- ❌ Документ без ОбработкаПроведения
- ❌ Прямая запись в регистры (используйте Движения)
- ❌ Отсутствие табличной части для многострочных данных
- ❌ Жёстко заданные номера (используйте автонумерацию)
