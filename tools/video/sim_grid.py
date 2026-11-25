#!/usr/bin/env python3
"""Модель resistor_grid_2d из scene_spec.json: sim_grid.py <scene_spec.json> <out sim.json>
Стационарное растекание тока div(σ grad φ)=0 на сетке N×N (конечные объёмы), σ зерна = 0, σ поры = 1/ρв.
Левая грань φ=1, правая φ=0, верх/низ изолированы. Пишет маску, |j|, линии тока и R(ρв); проверяет инварианты."""
import json, sys
from collections import deque
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla


def voronoi_mask(n, seeds, seed, width):
    rng = np.random.default_rng(seed)
    pts = rng.random((seeds, 2)) * n
    yy, xx = np.mgrid[0:n, 0:n] + 0.5
    d = np.stack([(xx - p[0]) ** 2 + (yy - p[1]) ** 2 for p in pts])
    srt = np.sort(np.sqrt(d), axis=0)
    owner = np.argmin(d, axis=0)
    pore = (srt[1] - srt[0]) < width  # ячейки у границы двух ячеек Вороного — поровые каналы
    return pore, owner


def percolates(pore):
    n = pore.shape[0]
    seen = np.zeros_like(pore); q = deque((i, 0) for i in range(n) if pore[i, 0])
    for c in q: seen[c] = True
    while q:
        i, j = q.popleft()
        if j == n - 1: return True
        for a, b in ((i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)):
            if 0 <= a < n and 0 <= b < n and pore[a, b] and not seen[a, b]:
                seen[a, b] = True; q.append((a, b))
    return False


def solve(pore, rho_w):
    n = pore.shape[0]
    sig = np.where(pore, 1.0 / rho_w, 0.0)
    idx = -np.ones((n, n), int); act = np.argwhere(pore)
    for k, (i, j) in enumerate(act): idx[i, j] = k
    m = len(act); A = sp.lil_matrix((m, m)); b = np.zeros(m)
    hm = lambda s1, s2: 0.0 if s1 == 0 or s2 == 0 else 2 * s1 * s2 / (s1 + s2)
    for k, (i, j) in enumerate(act):
        for a, c in ((i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)):
            if 0 <= a < n and 0 <= c < n and pore[a, c]:
                g = hm(sig[i, j], sig[a, c]); A[k, k] += g; A[k, idx[a, c]] -= g
        if j == 0: g = 2 * sig[i, j]; A[k, k] += g; b[k] += g * 1.0  # грань φ=1 (полъячейки)
        if j == n - 1: g = 2 * sig[i, j]; A[k, k] += g  # грань φ=0
    # изолированные кластеры пор (не связаны с электродами) делают матрицу вырожденной: закрепляем их
    A = A.tocsr(); diag = A.diagonal()
    A = A + sp.diags(np.where(diag == 0, 1.0, 0.0)); A = A + sp.eye(m) * 1e-14
    phi_v = spla.spsolve(A.tocsc(), b)
    phi = np.full((n, n), np.nan); phi[pore] = phi_v[idx[pore]]
    I = sum(2 * sig[i, n - 1] * phi[i, n - 1] for i in range(n) if pore[i, n - 1])
    resid = np.abs(A @ phi_v - b).max()
    # плотность тока в центрах ячеек
    jx = np.zeros((n, n)); jy = np.zeros((n, n))
    for i, j in act:
        def flux(a, c, dirn):
            if 0 <= a < n and 0 <= c < n and pore[a, c]: return hm(sig[i, j], sig[a, c]) * (phi[i, j] - phi[a, c]) * dirn
            return 0.0
        jx[i, j] = 0.5 * (flux(i, j + 1, 1) - flux(i, j - 1, 1)) if 0 < j < n - 1 else (flux(i, j + 1, 1) if j == 0 else -flux(i, j - 1, 1))
        jy[i, j] = 0.5 * (flux(i + 1, j, 1) - flux(i - 1, j, 1))
    return phi, jx, jy, I, resid


def streamlines(pore, phi, count, seed):
    """Пути заряда по потоку: из ячейки к соседу с меньшим φ с вероятностью, пропорциональной току через грань.
    Потенциальное течение без циклов (φ строго убывает), поэтому каждый путь доходит до правой грани."""
    n = pore.shape[0]; rng = np.random.default_rng(seed)
    starts = np.array([i for i in range(n) if pore[i, 0]]); w = np.array([1.0 - phi[i, 0] for i in starts])
    lines = []
    for s in rng.choice(starts, size=count, p=w / w.sum()):
        i, j = int(s), 0; pts = [(0.0, i + 0.5), (0.5, i + 0.5)]
        for _ in range(20 * n):
            if j == n - 1: pts.append((float(n), i + 0.5)); break
            nb = [(a, c) for a, c in ((i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1))
                  if 0 <= a < n and 0 <= c < n and pore[a, c] and phi[a, c] < phi[i, j]]
            if not nb: break
            f = np.array([phi[i, j] - phi[a, c] for a, c in nb])
            i, j = nb[rng.choice(len(nb), p=f / f.sum())]; pts.append((j + 0.5, i + 0.5))
        if pts[-1][0] >= n: lines.append(pts)
    return lines


def main():
    spec = json.load(open(sys.argv[1])); sm = spec["state_model"]; par = sm["parameters"]
    n = int(par["grid"].split("×")[0]); seed = par["random_seed"]
    pore, owner = voronoi_mask(n, 40, seed, 2.0)
    assert percolates(pore), "нет перколяции: сменить seed"
    res = {}
    for rw in par["rho_w"]["values"]:
        phi, jx, jy, I, resid = solve(pore, rw)
        assert resid < 1e-9 * max(I, 1e-12) or resid < 1e-9, f"невязка {resid}"
        assert I > 0, "ток должен идти от φ=1 к φ=0"
        res[rw] = dict(I=I, R=1.0 / I, jx=jx, jy=jy, phi=phi, resid=float(resid))
    R1 = res[1]["R"]
    ratios = {rw: res[rw]["R"] / R1 for rw in res}
    for rw, r in ratios.items(): assert abs(r - rw) < 1e-6, f"R({rw})/R(1)={r}"
    # перекраска кварц→кальцит не меняет вход (σ=0 у обоих): решение то же по построению
    jmag = np.hypot(res[1]["jx"], res[1]["jy"]); jmag = jmag / np.percentile(jmag[pore], 98)
    out = dict(n=n, seed=seed, pore=pore.astype(int).tolist(), owner=owner.tolist(),
               jmag=np.clip(jmag, 0, 1).round(3).tolist(),
               lines=streamlines(pore, res[1]["phi"], 60, seed),
               R_rel={str(k): round(float(v), 6) for k, v in ratios.items()},
               porosity_cells=round(float(pore.mean()), 4),
               checks=dict(percolation=True, grain_current_zero=True, residual_max=max(r["resid"] for r in res.values()),
                           linear_R=True, quartz_calcite_same_input=True))
    json.dump(out, open(sys.argv[2], "w"), separators=(",", ":"))
    print("ok: доля пор", out["porosity_cells"], "R_rel", out["R_rel"], "линий тока", len(out["lines"]), "невязка", out["checks"]["residual_max"])


if __name__ == "__main__":
    main()
