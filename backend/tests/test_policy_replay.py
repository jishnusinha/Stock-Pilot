from app.services.policy_replay import replay_policies_for_product


def test_policy_replay_identical_path_metrics():
    result = replay_policies_for_product(
        stock=20,
        daily_demand=5.0,
        lead_days=5,
        pack=10,
        reorder_point=30,
        unit_cost=100,
        budget=50_000,
        multi_agent_qty=20,
    )
    assert result["label"] == "SIMULATED_POLICY_REPLAY"
    assert len(result["rows"]) == 3
    names = {r["strategy"] for r in result["rows"]}
    assert names == {"fixed_rule", "demand_only", "multi_agent"}
    for r in result["rows"]:
        assert "total_defined_cost_paise" in r
        assert "purchasing_cash_paise" in r
        assert "unmet_demand_units" in r
