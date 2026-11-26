# Модуль проверки: пакет test_asquith (глава Asquith, гл. 7)
Запуск: `make review PACKAGE=<папка с package.json, asquith_ch7.md>` (JOBS=6), 0,6 мин, ≈ $0,75, 7 срезов агентом verifier.
Ответ: `ответ.json` (копия `build/review/test_asquith/ответ.json`), валиден по `review_output.schema.json`: 19 замечаний на 95 целей (18 significant, 1 minor), одно на цель.
Ограничения: PNG кадров в пакете не было (приложены только README, package.json и md), 9 целей-кадров проверены только по описанию `shows`, `label`, `plaque`. Ключ к пакету не выдавался, оценка организаторов; точность и полнота против заложенных ошибок мне неизвестны.
Копия главы Asquith в git не коммитится.
