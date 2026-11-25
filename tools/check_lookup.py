#!/usr/bin/env python3
"""Прокси «поиск фразы»: check_lookup.py <chapter> [--list]. Для single-заданий считает, у какого варианта больше всего слов совпадает с текстом шага
(утверждения и поля слоя узла). Если выигрывает верный, задание решается лексическим поиском без понимания.
Печатает долю таких заданий по разделам и в целом; цель курса ≤ 50 %. Не заменяет новичок-тест, но считается детерминированно."""
import json, re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
stem = lambda w: w[:5]
toks = lambda t: {stem(w) for w in re.findall(r"[а-яёa-z]{4,}", re.sub(r"\[\[.*?\]\]", " ", t.lower()))}

def node_text(n):
    L = n.get("layers", {}) or {}
    parts = [c["text"] for c in n["claims"]] + [v if isinstance(v, str) else " ".join(v) for v in L.values()]
    for k in ("data_implication", "it_analogy"):
        if isinstance(n.get(k), dict): parts += [str(x) for x in n[k].values() if isinstance(x, str)]
    return " ".join(parts)

def main(ch, show=False):
    B = ROOT / "build" / ch; N = {n["id"]: n for n in json.load(open(B / "nodes.json"))}
    tot = hit = 0; rows = []
    for f in sorted((B / "course").glob("final-*.json")):
        t = json.load(open(f)); h = c = 0
        for x in t:
            if x["type"] != "single" or x["node"] not in N: continue
            T = toks(node_text(N[x["node"]]))
            sc = {o: len(toks(o) & T) / max(1, len(toks(o))) for o in x["options"]}
            best = max(sc.values()); winners = [o for o, v in sc.items() if v == best]
            c += 1; solved = winners == [x["answer"]]; h += solved
            if solved and show: print(x["id"], round(best, 2), x["answer"][:80])
        tot += c; hit += h; rows.append((f.stem[6:], c, h))
    print(" ".join(f"{k}:{h}/{c}" for k, c, h in rows))
    print(f"single-заданий {tot}; верный вариант лексически лучший у {hit} ({100*hit//max(tot,1)} %)")

if __name__ == "__main__": main(sys.argv[1], "--list" in sys.argv)
