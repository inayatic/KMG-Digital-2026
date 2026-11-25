# KMG-Digital-2026 — «Глава → курс»
План работ: [PLAN.md](PLAN.md). Инструменты и модели: [MANIFEST.md](MANIFEST.md).

## Запуск
```bash
make course CHAPTER=<имя папки в chapters/>   # результат: out/<chapter>/index.html
```
Повторный запуск пересобирает только стадии, чьи входы изменились (кэш на уровне файлов `build/<chapter>/`).
Стадии пока заглушки (`tools/stage.py`), реализация — Этап 1.

## Журнал ручных правок
```bash
tools/edit-log start <chapter> "что правлю"; tools/edit-log stop
tools/edit-log add <chapter> <минуты> "что"
```
Пишет `metrics/edit-log.csv` с хэшем текущего коммита.

`chapters/` лежит в приватном репозитории; репозиторий нельзя делать публичным (главы не публикуем).
