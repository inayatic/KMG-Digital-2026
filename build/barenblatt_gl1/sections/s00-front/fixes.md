# Fixes: barenblatt_gl1 / s00-front

Замечаний V-… в verify.md: 0. Править нечего, nodes.json, coverage.md, routing.json и report.md не менялись.

- Ask-mentor п.1 (титул главы в узлы не идёт): отложено ментору, сейчас 3 единицы титула покрыты с причиной «титул».
- Ask-mentor п.2 (в report.md написано «доменного пакета нет», хотя domain-pack/geology/ есть): отложено ментору. Сам не решаю, на пустой сегмент это не влияет.

Проверка: `python3 -I tools/check_nodes.py …/nodes.json …/units.json` → nodes=0, units=3, errors=0. uncovered = [p005-01, p005-02, p005-03], совпадает с coverage.md.
