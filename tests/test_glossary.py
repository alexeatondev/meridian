"""Info bubbles: the glossary is complete and reaches every page through the shell."""
from meridian import glossary


def test_glossary_entries_are_complete_and_labels_unique():
    g = glossary.load()
    assert len(g) >= 60
    assert glossary.check() == []
    # formulas are plain text, short enough for a bubble
    for k, e in g.items():
        assert len(e["text"]) < 520, k
        assert len(e.get("formula", "")) < 260, k


def test_key_metrics_have_a_formula():
    g = glossary.load()
    for k in ("tracking_error", "risk_budget_used", "risk_budget_by", "var95", "diversification", "off_target",
              "cum_return", "portfolio_vs_market", "sharpe", "duration"):
        assert g[k].get("formula"), k


def test_shell_injects_glossary_and_script():
    from meridian.app import shell
    shell._assets.cache_clear()
    a = shell._assets()
    assert "window.MINFO=" in a and "minfo-pop" in a and "Tracking error (active risk)" in a
