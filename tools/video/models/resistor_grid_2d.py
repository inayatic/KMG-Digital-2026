#!/usr/bin/env python3
"""Модель состояния resistor_grid_2d: стационарное растекание тока в плоской породе (div(σ grad φ)=0).
Сетка n×n, зёрна по диаграмме Вороного (seed), границы между зёрнами — поровые каналы. σ зёрен = 0 (допущение книги, вход модели),
σ пор = 1/ρв. Левая грань φ=1, правая φ=0, верх и низ — нулевой поток. Решение: метод конечных объёмов, плотная линейная система (numpy).
Использование: resistor_grid_2d.py <out.json> [--n 64] [--seeds 40] [--seed 13] [--rho 1,2,3]
Пишет: сетку (id зерна, 0 = пора), φ и |j| для ρв=1, сопротивление R для каждого ρв (абсолютное и отн. к первому). Никакой интерполяции кадров."""
import json, sys
import numpy as np


def build(n, nseeds, seed, width):
    rng = np.random.default_rng(seed)
    pts = rng.uniform(0, n, size=(nseeds, 2))
    yy, xx = np.mgrid[0:n, 0:n]
    cx, cy = xx + 0.5, yy + 0.5
    d = np.sqrt((cx[..., None] - pts[:, 0]) ** 2 + (cy[..., None] - pts[:, 1]) ** 2)
    order = np.argsort(d, axis=2)
    d1 = np.take_along_axis(d, order[..., :1], 2)[..., 0]
    d2 = np.take_along_axis(d, order[..., 1:2], 2)[..., 0]
    grain = order[..., 0] + 1
    pore = (d2 - d1) < width
    gid = np.where(pore, 0, grain)
    return gid


def components(mask):
    n = mask.shape[0]
    lab = -np.ones(mask.shape, int); c = 0
    for y in range(n):
        for x in range(n):
            if mask[y, x] and lab[y, x] < 0:
                st = [(y, x)]; lab[y, x] = c
                while st:
                    a, b = st.pop()
                    for da, db in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        p, q = a + da, b + db
                        if 0 <= p < n and 0 <= q < n and mask[p, q] and lab[p, q] < 0:
                            lab[p, q] = c; st.append((p, q))
                c += 1
    return lab, c


def solve(sigma):
    n = sigma.shape[0]
    mask = sigma > 0
    lab, c = components(mask)
    keep = np.zeros_like(mask)
    for k in range(c):
        m = lab == k
        if m[:, 0].any() and m[:, -1].any(): keep |= m
    idx = -np.ones((n, n), int); idx[keep] = np.arange(keep.sum()); N = keep.sum()
    A = np.zeros((N, N)); b = np.zeros(N)
    def g(a, bb): return 2 * a * bb / (a + bb) if a + bb > 0 else 0.0
    for y in range(n):
        for x in range(n):
            if not keep[y, x]: continue
            i = idx[y, x]
            if x == 0: A[i, i] = 1; b[i] = 1; continue
            if x == n - 1: A[i, i] = 1; b[i] = 0; continue
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                p, q = y + dy, x + dx
                if 0 <= p < n and 0 <= q < n and keep[p, q]:
                    w = g(sigma[y, x], sigma[p, q]); A[i, i] += w; A[i, idx[p, q]] -= w
    phi_v = np.linalg.solve(A, b)
    phi = np.full((n, n), np.nan); phi[keep] = phi_v
    I = 0.0
    for y in range(n):
        if keep[y, 0] and keep[y, 1]: I += g(sigma[y, 0], sigma[y, 1]) * (phi[y, 0] - phi[y, 1])
    jx = np.zeros((n, n)); jy = np.zeros((n, n))
    for y in range(n):
        for x in range(n):
            if not keep[y, x]: continue
            s = sigma[y, x]
            xm, xp = max(x - 1, 0), min(x + 1, n - 1); ym, yp = max(y - 1, 0), min(y + 1, n - 1)
            def v(p, q, d): return phi[p, q] if keep[p, q] else phi[y, x]
            jx[y, x] = -s * (v(y, xp, 0) - v(y, xm, 0)) / max(1, xp - xm)
            jy[y, x] = -s * (v(yp, x, 0) - v(ym, x, 0)) / max(1, yp - ym)
    return phi, jx, jy, keep, I


def main():
    out = sys.argv[1]
    def arg(k, d): return type(d)(sys.argv[sys.argv.index(k) + 1]) if k in sys.argv else d
    n, ns, seed = arg("--n", 64), arg("--seeds", 40), arg("--seed", 13)
    rhos = [float(x) for x in (sys.argv[sys.argv.index("--rho") + 1] if "--rho" in sys.argv else "1,2,3").split(",")]
    width = 1.0
    for _ in range(12):  # расширяем каналы, пока нет сквозного пути; ширина канала ≈ 2 ячейки
        gid = build(n, ns, seed, width)
        lab, c = components(gid == 0)
        if any((lab == k)[:, 0].any() and (lab == k)[:, -1].any() for k in range(c)): break
        width += 0.3
    R = []
    for rho in rhos:
        sig = np.where(gid == 0, 1.0 / rho, 0.0)
        phi, jx, jy, keep, I = solve(sig)
        R.append(float(1.0 / I))
        if rho == rhos[0]: phi1, jx1, jy1, keep1 = phi, jx, jy, keep
    jm = np.sqrt(jx1 ** 2 + jy1 ** 2); jm = jm / jm.max()
    res = {"n": n, "seed": seed, "seeds": ns, "channel_width": round(width, 2), "grain": gid.tolist(),
           "connected": keep1.astype(int).tolist(), "phi": np.nan_to_num(phi1, nan=0).round(4).tolist(),
           "j": jm.round(4).tolist(), "rho_w": rhos, "R_abs": [round(r, 6) for r in R], "R_rel": [round(r / R[0], 4) for r in R],
           "pore_fraction": round(float((gid == 0).mean()), 3)}
    json.dump(res, open(out, "w")); print("R_rel", res["R_rel"], "pore_fraction", res["pore_fraction"], "channel", res["channel_width"])


if __name__ == "__main__":
    main()
