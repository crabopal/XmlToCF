# xml2cf

Компилятор **штатной XML-выгрузки конфигуратора** (`Configuration.xml` + дерево объектов) в файл **`.cf`** без платформы 1С, ibcmd, информационной базы и лицензии.

> MVP: валидный контейнер `.cf`, распаковывается, содержит ожидаемые UUID.  
> Гарантии загрузки в конфигуратор на всех 8.3.x **нет**. Паритет с ibcmd — только с oracle.

## Установка

```bash
pip install -e ".[dev]"
```

Требование: Python ≥ 3.10, зависимость `v8unpack>=1.2.6,<2`.

## CLI

```bash
python -m xml2cf inspect ./tests/fixtures/cf-empty-infobase
python -m xml2cf compile ./tests/fixtures/cf-empty-infobase ./out.cf
python -m xml2cf compile ./tests/fixtures/cf-small ./small.cf --json
python -m xml2cf unpack ./out.cf ./unpacked
python -m xml2cf types
python -m xml2cf gui
```

Без аргументов (двойной клик по portable exe) открывается GUI.

## Стабильный API

```python
from xml2cf import compile_dump, supported_types

report = compile_dump("path/to/dump", "out.cf", allow_unsupported=False)
print(report.to_json())
print(supported_types())
```

`CompileReport`: `ok`, `output`, `layout`, `configuration_uuid`, `configuration_name`, `objects`, `unsupported`, `warnings`, `error`.

## Поддерживаемые типы (MVP)

| Тип | Статус |
|-----|--------|
| Language | да |
| CommonModule | да (+ `.0` модуль) |
| Constant | да |
| Enum | да (+ `EnumValue` / `EnumValues/`) |
| Catalog | да (реквизиты + табличные части; без форм) |
| Document, Role, … | нет → ошибка или `--allow-unsupported` |

## Схема сборки

1. Распаковать встроенный `skeleton.cf` (layout **32-bit**, `version` token `216`)
2. Пропатчить header: имя, UUID, compat, default language, InternalInfo group UUIDs, includes
3. Сериализовать объекты dump → brace-файлы
4. Пересобрать `versions`, упаковать контейнер

Layout **64-bit** (платформа ≥ 8.3.16) зарезервирован и **не** производится этим MVP.

## Портативная сборка

```bash
./scripts/build-portable.sh
```

Wine для Windows `.exe`: лог в файл, не пайпить stdout; скрипт с таймаутами.

## Тесты

```bash
pytest -q
```

Фикстуры: `tests/fixtures/cf-empty-infobase`, `tests/fixtures/cf-small` (каталог с реквизитом/ТЧ + перечисление со значениями).

## Ограничения

- Это не «просто v8unpack pack» исходников v8unpack — вход всегда **Designer XML**.
- Нет oracle-сравнения с ibcmd в CI (нужна платформа).
- Формы, предопределённые, сложные типы ссылок — вне MVP.
- Visibility Origin: только `private` | `internal`.

## Репозиторий

Исходная линия разработки: Origin `crabopal/cf-direct-build`.  
Этот GitHub-репозиторий (`XmlToCF`) содержит переносимую реализацию MVP по тому же ТЗ.
