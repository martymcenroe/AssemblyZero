# Assertion manifest (compiled — regenerable, never hand-edited)

| Row | Criterion | Sample point (verbatim) | Expected (literal) |
|---|---|---|---|
| S1.1 |  | classification at 3 interior points + equality of samples at (0.3 R, 0.5 R, 0.7 R) along one needle-free radial — flatness IS the assertion | 0.3 R; 0.5 R; 0.7 R |
| S2.1 |  | classification at radius 0.94 R at values 65/75/85 — deliberately offset from every tick position, because ticks render on top of the band (majors sit at multiples of 10, minors at even values; 65/75/85 carry no tick) | 0.94 R |
| S3.1 |  | stroke predicate at each tick's midpoint: channel mean ≥ 100, all 11 — the white stroke samples ~255, and the 100 threshold clears both backgrounds: the face's ~10 (values 0–50) and the band's ~70 (values 60–100, where ticks render on top of the band; #AA0F19 → mean 70.0). A missing tick fails on either background: 10 < 100 and 70 < 100. Width 2.56 px at the pinned test size is too thin for the interior rule | ≥ 100; #AA0F19; < 100; 2.56 px |
| S4.1 |  | stroke predicate at 4 sampled minors (values 2, 34, 66, 98): midpoint channel mean ≥ 100 | ≥ 100 |
| S5.1 |  | presence: ≥1 white-classified pixel within the numeral's cap-height box at each of the 11 positions. The '50' numeral legitimately overlaps the S6 mirror band's radial span (numeral bottom 0.665 R vs band centred 0.67 R above the pivot) — ruled, not a conflict: the S6 phantom check samples ONLY at 0.12 R–0.25 R off-axis and never sees the numeral, whose half-width is ~0.065 R (ruling on the #361 conflict, reaffirmed on #369). Any derived restatement of the mirror-band check (LLD row, spec test) MUST carry the off-axis sampling window with it — the window is load-bearing, not commentary | ≥1; 0.665 R; 0.67 R; 0.12 R; 0.25 R; 0.065 R |
| S6.1 |  | presence: ≥1 white-classified pixel in the wordmark band | ≥1 |
| S6.2 |  | absence of white in the mirror band above the pivot, sampled ONLY at horizontal offsets 0.12 R–0.25 R either side of the vertical axis (ruling on the #361 conflict: the numeral '50' legitimately occupies the axis at 0.665–0.775 R above the pivot, half-width ~0.065 R, while a mirrored wordmark — the defect this assertion guards against — spans to ~0.27 R; the offset window sees a phantom wordmark and never the numeral) | 0.12 R; 0.25 R; 0.775 R; 0.065 R; 0.27 R |
| S7.1 |  | the #328 predicate: ≥3 achromatic samples (max−min ≤ 14, mean 16–248) spanning the horizon, ≥1 dark (mean < 100), ≥1 bright (mean > 200) | ≥3; ≤ 14; ≥1; < 100; > 200 |
| S8.1 |  | the #326 predicate: centre pixel within ±6 per channel | 0.25 R; 0.020 R; #1A1A1C |
| S9.1 |  | sample at 1.01 R is darker (channel mean) than the chrome at 1.10 R on the same radial | 1.01 R; 1.10 R |
