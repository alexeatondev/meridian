# Skill: macro-regime

Four regimes defined on four scores (each clipped to [-2, 2]):
- **growth** = (real GDP yoy − 2.0)/1.5 + (PMI − 50)/5 − (6m change in unemployment)/0.5
- **inflation** = (core CPI yoy − 2.0)/1.0
- **monetary policy** = −(6m change in policy rate)/0.5 (positive = easing)
- **financial conditions** = −(HY spread − 400bp)/150 (positive = loose)

Rules: recession if growth < −1 and financial conditions < 0; late-cycle if growth < 0 and (inflation > 0.5 or easing);
recovery if growth ≥ 0 with easing and inflation ≤ 0.5; otherwise expansion.
