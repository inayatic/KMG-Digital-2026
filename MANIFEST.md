# MANIFEST — инструменты и модели
Версии на момент последнего обновления; финальные фиксируются при заморозке (тег).

Команда: _заполнить_ · Тег заморозки: _заполнить_

## Модели

| Этап | Модель | Версия | Где работает | Что уходит наружу | Как заменить |
|---|---|---|---|---|---|
| Учебный слой, enrich | Claude через Claude Code (`claude -p`, агент layer-extractor) | модель сессии, по умолчанию claude-sonnet-5-5 | облако Anthropic | текст главы и фрагменты | переменная `LLM_MODEL` (передаётся как `--model`) |
| Модуль проверки | Claude, агент verifier | то же | облако | пакет проверки, текст главы | `LLM_MODEL` |
| Курс | Claude, агент course-builder (проверено на новой книге: Барабошкин, 8 разделов, 298 заданий) | то же | облако | слой | `LLM_MODEL` |
| Сценарии роликов | Claude, агент scenario-writer | то же | облако | слой и сценарий | `LLM_MODEL` |
| Озвучка | ElevenLabs TTS, голос Alice (`Xb7hH8MSUJpSbSDYk0k2`) | `eleven_multilingual_v2` | облако ElevenLabs | только текст озвучки ролика (voiceover.txt); ключ подставляет прокси окружения, в коде и в git его нет | `--voice ID` в `tools/tts_eleven.py`; модель — константа `MODEL` |
| Проверка озвучки | ElevenLabs Scribe (распознавание: WER и времена слов для субтитров и монтажа) | `scribe_v1` | облако ElevenLabs | только синтезированный mp3 | `tools/tts_eleven.py` |
| Иллюстрации и кадры роликов | генеративные модели не используются: кадры рисует детерминированный код (canvas) по расчёту модели | — | локально | ничего | — |

Отправка текста глав во внешний API: допущение, **не подтверждено** у организаторов. Если запрещено, нужна локальная модель; конвейер модель-независим только на уровне вызова `claude -p`.

## Инструменты

| Инструмент | Версия | Для чего | Данные наружу |
|---|---|---|---|
| Python 3 + jsonschema | см. `python3 --version` | стадии, проверки | нет |
| GNU make | — | запуск `make course CHAPTER=…` | нет |
| poppler (pdftotext, pdftoppm) | — | текст и сканы страниц | нет |
| Claude Code CLI | 2.1.332 | запуск агентов | да (см. выше) |
| FFmpeg | 6.1.1 | сборка видео (H.264/AAC), громкость −16 LUFS (loudnorm, 2 прохода) | нет |
| Node.js + Playwright (Chromium) | 22.23.5 / 1.63.0 | кадры роликов (`tools/video/render.js`), новичок-тесты курсов | нет |
| numpy, scipy | 2.5.3 / 1.18.1 | расчёт моделей роликов (`tools/video/sim_grid.py`) | нет |

## Запуск
Одна команда на главу: `make course CHAPTER=<имя>` (стадии: clean_ref → make_units → nodes → verify → org → course). Метрики токенов и денег пишет `tools/stage.py` в `metrics/metrics.csv`; ручные правки: `tools/edit-log` → `metrics/manual_edits.csv`.

Ролик: `passports/<id>/` (паспорт, сценарий, озвучка, scene_spec) → `tools/tts_eleven.py` → `tools/video/sim_grid.py` → `tools/video/timeline.py` → `node tools/video/render.js`; команды и замеры в `passports/<id>/render.md`.
