"""Simulations behind the PLAYBOOK law-4 numbers (seeded, numpy only).

  python3 kit/sim_bar.py [--draws 20000]

(a) Power of the adoption bar (kit/compare.py): 5 folds, corrected t >= 2, no fold negative, pooled >= 0
    (approximated as mean >= 0); per-fold Δ ~ N(gain, 1), gain in fold-SD units.
(b) False-alarm rate of the ruler (kit/watcher.sh) on a trusted CV: n subs evenly spaced over a CV range of
    3 x LB noise, public = CV (slope 1) + N(0, resid SD); alert if slope < 0.5 (range >= 3 x LB noise holds)
    or residual SD (ddof 2) > 1.5 x LB noise.
(c) Fold bar vs the group-bootstrap read (kit/compare.py --bootstrap) when fold Δs are correlated: k folds of m groups;
    group Δ = gain + N(0, 1) + u_f, u_f = per-fold training noise (SD tau, equicorrelated rho across folds, as
    overlapping training sets make it); gain in fold-SD units. Bootstrap read: pooled Δ >= 2 x sqrt(boot SE^2 +
    tau^2 (1/k + 1/(k-1))) and worst fold >= -2 tau; boot SE by the normal approximation (SD of group Δ / sqrt(km)).
    'boot alone' drops the tau term: it ignores training noise. The worst-fold check costs power (at tau .05, gain 1:
    .49 vs .68 for boot alone); it is kept so one bad fold, a stratum the change breaks, cannot pass."""
import argparse

import numpy as np


def power(gain, draws, k=5, seed=0):
    d = np.random.default_rng(seed).normal(gain, 1.0, (draws, k))
    se = d.std(1, ddof=1) * np.sqrt(1 / k + 1 / (k - 1))
    m = d.mean(1)
    return float(np.mean((m / se >= 2) & (d.min(1) >= 0) & (m >= 0)))


def ruler_alarm(n, resid, draws, lbn=1.0, seed=0):
    x = np.linspace(0, 3 * lbn, n)                    # the narrowest range the slope check reads
    y = x + np.random.default_rng(seed).normal(0, resid, (draws, n))
    xc = x - x.mean()
    slope = (y - y.mean(1, keepdims=True)) @ xc / (xc @ xc)
    r = y - y.mean(1, keepdims=True) - slope[:, None] * xc
    sd = np.sqrt((r ** 2).sum(1) / (n - 2))
    return float(np.mean((slope < 0.5) | (sd > 1.5 * lbn)))


def fold_vs_bootstrap(gain, tau, rho, draws, k=5, m=100, seed=0):
    """Pass rates {fold bar, bootstrap read, boot alone} under correlated per-fold training noise."""
    rng = np.random.default_rng(seed)
    fold_sd = np.sqrt(1 / m + tau ** 2)
    noise = rng.multivariate_normal(np.zeros(k), tau ** 2 * ((1 - rho) * np.eye(k) + rho), draws) if tau else np.zeros((draws, k))
    groups = gain * fold_sd + rng.normal(0, 1, (draws, k, m)) + noise[:, :, None]
    d, flat = groups.mean(2), groups.reshape(draws, -1)
    pooled, boot_se = flat.mean(1), flat.std(1, ddof=1) / np.sqrt(k * m)
    se = d.std(1, ddof=1) * np.sqrt(1 / k + 1 / (k - 1))
    fold_bar = (d.mean(1) / se >= 2) & (d.min(1) >= 0) & (pooled >= 0)
    boot_read = (pooled >= 2 * np.sqrt(boot_se ** 2 + tau ** 2 * (1 / k + 1 / (k - 1)))) & (d.min(1) >= -2 * tau)
    return {"fold bar": float(fold_bar.mean()), "bootstrap read": float(boot_read.mean()), "boot alone": float((pooled >= 2 * boot_se).mean())}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--draws", type=int, default=20000)
    a = ap.parse_args()
    print("(a) power of the 5-fold bar\n gain (fold-SD)  pass rate")
    for g in (0.5, 1, 1.5, 2):
        print(f" {g:>14}  {power(g, a.draws):.3f}")
    print("(b) ruler false alarms on a trusted CV (CV range 3 x LB noise, slope 1)\n n subs  resid SD        rate   1 in")
    for n in (5, 6, 8):
        for name, s in (("LB noise", 1.0), ("LB noise/√2", 2 ** -.5)):
            r = ruler_alarm(n, s, a.draws)
            print(f" {n:>6}  {name:<12} {r:.3f}  {1 / r:5.1f}")
    print("(c) fold bar vs bootstrap read, 5 folds x 100 groups (pass rate at gain 0 = false pass; at gain 1 = power)\n"
          " tau   rho   gain  fold bar  bootstrap read  boot alone")
    for tau in (0.05, 0.1):
        for rho in (0, 0.25, 0.5):
            for g in (0, 1):
                r = fold_vs_bootstrap(g, tau, rho, a.draws // 5)
                print(f" {tau:<5} {rho:<5} {g:<5} {r['fold bar']:8.3f}  {r['bootstrap read']:14.3f}  {r['boot alone']:10.3f}")


if __name__ == "__main__":
    main()
