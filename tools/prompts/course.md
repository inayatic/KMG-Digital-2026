# Промпт стадии «course» (course-builder), вся глава
Подставляется: CHAPTER. Следуй .claude/agents/course-builder.md.
Вход: build/CHAPTER/{nodes,routing,units}.json, org/layer.json, org/routing.json, domain-pack/, tools/build_course.py и tools/course_config/latyshova.json (образец обвязки). Источник фактов только слой.
Создай tools/course_config/CHAPTER.json по образцу и собери курс: для каждого раздела с узлами python3 -I tools/build_course.py CHAPTER --prefix <префикс раздела>. --out out/CHAPTER/<раздел>; затем out/CHAPTER/index.html как оглавление разделов. Не придумывай ответы к задачам книги без ключа. Отчёт ≤6 строк.
