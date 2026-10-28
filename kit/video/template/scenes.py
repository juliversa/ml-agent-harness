# Example scenes: copy this folder, rename it (the name becomes the mp4 name), replace the scenes.
# One @scene per idea. caps = the narrated lines, in order; c[k] = the second caption k starts.
# Animate each picture element to appear on the caption that talks about it.

@scene('title', ['How a model learns from noisy labels, in one minute.'])
def s_title(ax, t, c):
    T(ax, 8, 5.4, 'Noisy labels', fs=84, w='bold', a=A(t, 0.3, f=0.6))
    u = P(t, 0.9, 1.0)
    if u > 0.01:
        ln(ax, [8 - 3.6 * u, 8 + 3.6 * u], [4.6, 4.6], c=YELLOW, lw=3)
    T(ax, 8, 3.9, 'a one-minute example', fs=32, c=YELLOW, a=A(t, 1.3, f=0.6))


@scene('fix', ['Most labels are right, but some are wrong, shown in red.',
               ('Train on clean labels and the score rises from .80 to .86.', 0.5)])
def s_fix(ax, t, c):
    sec(ax, 'THE IDEA', t)
    toy_tag(ax, A(t, c[0]))
    rng = np.random.default_rng(0)
    xs, ys = rng.uniform(1.5, 7.5, 60), rng.uniform(2.5, 7.5, 60)
    bad = rng.random(60) < 0.15
    for x, y, b in zip(xs, ys, bad):
        dot(ax, x, y, 0.12, mix(GREEN, RED, A(t, c[0] + 0.8)) if b else GREEN, a=A(t, c[0]))
    for k, (v, col) in enumerate([(.80, GREY), (.86, BLUE)]):
        a = A(t, c[1] + 0.4 * k)
        h = (v - .7) / .2 * 4.5
        bar(ax, 10 + 2.2 * k, 2.2, 1.4, h * P(t, c[1] + 0.4 * k), col, a=a)
        T(ax, 10.7 + 2.2 * k, 2.4 + h, f'{v:.2f}'[1:], fs=26, c=col, a=a, w='bold')
        T(ax, 10.7 + 2.2 * k, 1.75, ['noisy', 'cleaned'][k], fs=20, c=GREY, a=a)
