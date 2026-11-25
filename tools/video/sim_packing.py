#!/usr/bin/env python3
"""Модель sphere_packing_3d из scene_spec.json: sim_packing.py <scene_spec.json> <out sim.json>

Пористость периодической укладки шаров считается двумя способами:
  1) точно (геометрия элементарной ячейки);
  2) подсчётом вокселей в той же ячейке (numpy), чтобы видеть, что картинка и число из одного состояния.
Укладки: кубическая (простая кубическая решётка), ромбоэдрическая (самая плотная; ячейка ГЦК),
ромбоэдрическая + мелкие шары в октаэдрических пустотах, + ещё мелкие в тетраэдрических пустотах.
Пишет числа, срезы для кадров (маски 2D) и проверяет инварианты. Случайности нет.
"""
import json
import sys

import numpy as np

SQ2 = np.sqrt(2.0)


def cell(kind, R):
    """Возвращает (сторона кубической ячейки L, список (центр, радиус)) для укладки kind при радиусе крупного шара R."""
    if kind == "cubic":
        L = 2 * R
        return L, [((0.0, 0.0, 0.0), R)]
    a = 2 * SQ2 * R  # ГЦК: шары касаются по диагонали грани
    big = [(0, 0, 0), (0, .5, .5), (.5, 0, .5), (.5, .5, 0)]
    spheres = [(tuple(a * np.array(p)), R) for p in big]
    if kind in ("rhomb_oct", "rhomb_oct_tet"):
        r_o = (SQ2 - 1) * R  # радиус шара, касающегося шести соседей в октаэдрической пустоте
        octa = [(.5, .5, .5), (.5, 0, 0), (0, .5, 0), (0, 0, .5)]
        spheres += [(tuple(a * np.array(p)), r_o) for p in octa]
    if kind == "rhomb_oct_tet":
        r_t = (np.sqrt(1.5) - 1) * R  # касается четырёх соседей в тетраэдрической пустоте
        tet = [(x, y, z) for x in (.25, .75) for y in (.25, .75) for z in (.25, .75)]
        spheres += [(tuple(a * np.array(p)), r_t) for p in tet]
    return a, spheres


def exact_porosity(L, spheres):
    v = sum(4 / 3 * np.pi * r ** 3 for _, r in spheres)
    return 1 - v / L ** 3


def voxel_solid(L, spheres, n, reps=1):
    """Маска твёрдого в кубе со стороной reps*L, n вокселей на сторону, периодические границы."""
    box = reps * L
    c = (np.arange(n) + 0.5) * box / n
    X, Y, Z = np.meshgrid(c, c, c, indexing="ij")
    solid = np.zeros((n, n, n), bool)
    for i in range(reps):
        for j in range(reps):
            for k in range(reps):
                for (p, r) in spheres:
                    q = np.array(p) + L * np.array([i, j, k])
                    d2 = np.zeros_like(X)
                    for ax, A in enumerate((X, Y, Z)):
                        dx = np.abs(A - q[ax]); dx = np.minimum(dx, box - dx)
                        d2 += dx * dx
                    solid |= d2 <= r * r
    return solid


def min_gap(L, spheres):
    """Минимальный зазор между поверхностями шаров (с учётом периодичности); <0 — перекрытие."""
    best = np.inf
    for i, (p, r) in enumerate(spheres):
        for j, (q, s) in enumerate(spheres):
            for sh in np.array(np.meshgrid([-1, 0, 1], [-1, 0, 1], [-1, 0, 1])).T.reshape(-1, 3):
                if i == j and not sh.any():
                    continue
                d = np.linalg.norm(np.array(p) - np.array(q) - L * sh)
                best = min(best, d - r - s)
    return best


def main(spec_path, out_path):
    spec = json.load(open(spec_path, encoding="utf-8"))
    m = spec["state_model"]["parameters"]
    R = m["R_big_mm"]["value"]
    n = m["voxels_per_side"]["value"]
    tol = m["voxel_tolerance"]["value"]
    out = {"model": "sphere_packing_3d", "R_big_mm": R, "voxels_per_side": n, "packings": {}, "slices": {}, "invariants": {}}
    kinds = ["cubic", "rhomb", "rhomb_oct", "rhomb_oct_tet"]
    for kind in kinds:
        L, sph = cell(kind, R)
        ex = exact_porosity(L, sph)
        solid = voxel_solid(L, sph, n)
        vx = 1 - solid.mean()
        out["packings"][kind] = {
            "cell_side_mm": float(L), "n_spheres": len(sph),
            "radii_mm": sorted({round(float(r), 6) for _, r in sph}, reverse=True),
            "porosity_exact": float(ex), "porosity_voxel": float(vx),
            "porosity_pct_rounded": round(100 * ex), "min_gap_mm": float(min_gap(L, sph)),
        }
        # срезы для кадров: плоскость z = 0 (через центры крупных шаров) и z = L/4
        k0, k4 = 0, n // 4
        out["slices"][kind] = {
            "z0": solid[:, :, k0].astype(int).tolist(),
            "z_quarter": solid[:, :, k4].astype(int).tolist(),
            "area_pore_fraction_z0": float(1 - solid[:, :, k0].mean()),
        }
    # масштабная инвариантность: тот же куб 1 мм, шары R и R/2 (8 ячеек), одинаковый воксель
    Lc, s1 = cell("cubic", R)
    _, s2 = cell("cubic", R / 2)
    nb = m["scale_test_voxels"]["value"]
    p_big = 1 - voxel_solid(Lc, s1, nb, reps=1).mean()
    p_small = 1 - voxel_solid(Lc / 2, s2, nb, reps=2).mean()
    out["scale_test"] = {"box_mm": float(Lc), "R_mm": [R, R / 2], "porosity_voxel": [float(p_big), float(p_small)]}

    P = out["packings"]
    inv = out["invariants"]
    inv["voxel_vs_exact"] = all(abs(P[k]["porosity_voxel"] - P[k]["porosity_exact"]) < tol for k in kinds)
    inv["no_overlap"] = all(P[k]["min_gap_mm"] > -1e-9 for k in kinds)
    inv["cubic_matches_book_48"] = P["cubic"]["porosity_pct_rounded"] == 48
    inv["rhomb_matches_book_26"] = P["rhomb"]["porosity_pct_rounded"] == 26
    inv["exact_cubic_formula"] = abs(P["cubic"]["porosity_exact"] - (1 - np.pi / 6)) < 1e-12
    inv["exact_rhomb_formula"] = abs(P["rhomb"]["porosity_exact"] - (1 - np.pi / (3 * SQ2))) < 1e-12
    inv["size_invariance"] = abs(p_big - p_small) < tol
    inv["monotone_fill"] = (P["cubic"]["porosity_exact"] > P["rhomb"]["porosity_exact"]
                            > P["rhomb_oct"]["porosity_exact"] > P["rhomb_oct_tet"]["porosity_exact"])
    inv["slice_area_differs_from_volume"] = abs(out["slices"]["cubic"]["area_pore_fraction_z0"]
                                                - P["cubic"]["porosity_exact"]) > 0.05
    for k in inv:
        inv[k] = bool(inv[k])
    out["all_invariants_ok"] = all(inv.values())
    json.dump(out, open(out_path, "w", encoding="utf-8"), ensure_ascii=False)
    for k in kinds:
        print(k, "exact %.4f voxel %.4f gap %.2e" % (P[k]["porosity_exact"], P[k]["porosity_voxel"], P[k]["min_gap_mm"]))
    print("scale test", out["scale_test"]["porosity_voxel"])
    print("slice z0 area pore fraction (cubic)", out["slices"]["cubic"]["area_pore_fraction_z0"])
    print(json.dumps(inv, ensure_ascii=False))
    if not out["all_invariants_ok"]:
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
