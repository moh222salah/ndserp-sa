"""Pure insurance maths (no Frappe imports so it can be unit-tested anywhere)."""


def split_amounts(net_total, coverage_percent, max_coverage=0.0, deductible=0.0):
    """Return (insurer_amount, customer_amount).

    eligible = net_total - deductible; insurer pays coverage% of eligible, capped by
    max_coverage (when > 0) and never more than net_total.
    """
    net_total = float(net_total or 0)
    coverage_percent = min(max(float(coverage_percent or 0), 0.0), 100.0)
    eligible = max(net_total - float(deductible or 0), 0.0)
    insurer = eligible * coverage_percent / 100.0
    if float(max_coverage or 0) > 0:
        insurer = min(insurer, float(max_coverage))
    insurer = round(min(insurer, net_total), 2)
    return insurer, round(net_total - insurer, 2)
