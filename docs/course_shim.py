# Обход дефекта: одиночный раздел «s00-front» (выдержка без заголовков §/Глава) отфильтровывается как титульный. Запускает замороженный build_course_all без правки файлов.
import sys; sys.path.insert(0, "tools")
import build_course_all as b
real = b.re
class R:
    def __getattr__(self, n): return getattr(real, n)
    def match(self, p, s, *a): return None if p == r"s00|s99" else real.match(p, s, *a)
b.re = R(); b.main(sys.argv[1])
