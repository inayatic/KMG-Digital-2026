# KMG-Digital-2026 — «Глава → курс»
План работ: [PLAN.md](PLAN.md). Инструменты и модели: [MANIFEST.md](MANIFEST.md).

## Запуск
```bash
make course CHAPTER=<имя папки в chapters/>   # результат: out/<chapter>/index.html
```
Повторный запуск пересобирает только стадии, чьи входы изменились (кэш на уровне файлов `build/<chapter>/`).
Стадии: `clean_ref` → `make_units` → `nodes` (нарезка `split_sections`, агенты по разделам, ремонт покрытия `fix_cov`) → `verify` → `org` (enrich + формат организаторов) → `course` (задания по разделам + сборка сайтов). Параллельность: `JOBS=8`. Стадии с готовым результатом пропускаются. Время и деньги по стадиям: `metrics/metrics.csv`.

## Журнал ручных правок
```bash
tools/edit-log start <chapter> "что правлю"; tools/edit-log stop
tools/edit-log add <chapter> <минуты> "что"
```
Пишет `metrics/edit-log.csv` с хэшем текущего коммита.

`chapters/` лежит в приватном репозитории; репозиторий нельзя делать публичным (главы не публикуем).

## Чистый эталон (стадия 0)
`tools/clean_ref.py <chapter>` → `build/<chapter>/clean.md` + `clean-report.json`. Страницы md с OCR-мусором заменяются текстом PDF-слоя (`pdf-text`); у сканов (Кузнецов, Барабошкин) мусорные страницы помечены `FLAG-manual` — сверять вручную. Номера страниц = номера PDF-страниц, не печатные.
В md есть блоки `---- ━━━ FORMAT n: ...` — это описания рисунков, добавленные моделью, **не текст автора**: цитировать их как книгу нельзя.

## Формат организаторов
Схемы: `reference/organizers/01_схемы/`. Наш внутренний слой (`build/<ch>/nodes.json`) конвертируется командой `make org CHAPTER=<ch>` в `build/<ch>/org/{layer,coverage,routing}.json`:
`merge_layer` → `to_organizer_schema` (пробелы пустые, список в `conversion-report.md`) → `apply_patches` (патчи агентов `enrich`: тип трудности по расшифровке организаторов, пороговость, термины, «что ломается», video_scores) → `check_org` (схемы + цитаты на странице исходного md).
Патчи пишет `tools/prompts/enrich.md` в `build/<ch>/org/patches/<раздел>.json`.

## Ролики
```bash
python3 tools/tts_eleven.py passports/<id>/voiceover.txt passports/<id>/audio-stress --keep-stress   # озвучка + WER
python3 tools/video/sim_grid.py passports/<id>/scene_spec.json build/video/<id>/sim.json             # расчёт модели
python3 tools/video/timeline.py passports/<id> passports/<id>/audio-stress build/video/<id>           # таймлайн, −16 LUFS
node tools/video/render.js tools/video/<id>.html build/video/<id> build/video/<id>/<id>.mp4          # кадры → mp4
```
Ключ ElevenLabs не хранится в репозитории: его подставляет прокси облачного окружения (заголовок `xi-api-key`).
