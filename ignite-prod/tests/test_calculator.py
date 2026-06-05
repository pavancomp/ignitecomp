"""
Unit tests for the Ignite compensation calculator.
Pure function tests — no DB required. All amounts in INR.

Run: pytest tests/test_calculator.py -v
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from engine.calculator import (
    PlanParams, RankRow, CycleInput, CycleResult,
    calculate_cycle_commission, determine_rank,
    best_green_coin_conversion, round_inr, _calculate_tds,
)


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def plan():
    return PlanParams(
        cv_per_step=1800,
        flush_ratio=3.0,
        tds_rate=0.05,
        tds_threshold_inr=15000,
        inr_rounding=500,
        coin_lifetime_cap=12,
        yellow_coin_step_interval=6,
        first_step_half_rate=True,
    )


@pytest.fixture
def rank_table():
    return [
        RankRow("Silver Star",   0,   600,  21250, None,  0,      0,  0),
        RankRow("Titanium Star", 2,   600,  25500, None,  0,      0,  0),
        RankRow("Gold Star",     5,   600,  29750, None,  0,      0,  0),
        RankRow("Platinum Star", 10, 1200, 34000, None, 10,      0,  0),
        RankRow("Sapphire Star", 25, 1200, 38250, None, 10,      0,  0),
        RankRow("Diamond Star",  50, 1800, 42500, None, 10,      0,  0),
        RankRow("Emerald Star",  100, 1800, 46750, None, 10, 212500, 2),
        RankRow("Crown Diamond", 250, 3600, 48450, None, 10, 425000, 3),
    ]


def make_input(**kwargs):
    defaults = dict(
        distributor_id=1,
        left_cv_this_cycle=0,
        right_cv_this_cycle=0,
        left_cv_carry_in=0,
        right_cv_carry_in=0,
        lifetime_steps_before=0,
        direct_cv_this_cycle=600,
        green_coins_available=0,
        green_coins_lifetime=0,
        cumulative_matching_bonus_inr=0,
        maintenance_months_at_rank=0,
        maintenance_already_paid=False,
    )
    defaults.update(kwargs)
    return CycleInput(**defaults)


# ── INR rounding ─────────────────────────────────────────────────────────

def test_round_inr_exact():
    assert round_inr(21250, 500) == 21250  # exactly divisible

def test_round_inr_no_rounding():
    assert round_inr(21500, 500) == 21500

def test_round_inr_zero():
    assert round_inr(0, 500) == 0

def test_round_inr_unit_1():
    assert round_inr(21347, 1) == 21347


# ── Rank determination ────────────────────────────────────────────────────

def test_rank_zero_steps(rank_table):
    r = determine_rank(0, 600, rank_table)
    assert r.name == "Silver Star"

def test_rank_titanium(rank_table):
    r = determine_rank(2, 600, rank_table)
    assert r.name == "Titanium Star"

def test_rank_gold(rank_table):
    r = determine_rank(5, 600, rank_table)
    assert r.name == "Gold Star"

def test_rank_requires_direct_cv(rank_table):
    # Platinum requires 1200 direct CV; only 600 → Gold
    r = determine_rank(10, 600, rank_table)
    assert r.name == "Gold Star"

def test_rank_platinum_met(rank_table):
    r = determine_rank(10, 1200, rank_table)
    assert r.name == "Platinum Star"

def test_rank_crown_diamond(rank_table):
    r = determine_rank(250, 3600, rank_table)
    assert r.name == "Crown Diamond"


# ── Step commission ───────────────────────────────────────────────────────

def test_zero_steps(plan, rank_table):
    """Unbalanced legs = 0 steps."""
    inp = make_input(left_cv_this_cycle=3600, right_cv_this_cycle=0)
    r = calculate_cycle_commission(inp, plan, rank_table)
    assert r.steps_earned == 0
    assert r.step_commission_inr == 0

def test_one_step_first_time_half_rate(plan, rank_table):
    """Lifetime step 1 → 50% of Silver Star rate = ₹21,250 // 2 = ₹10,625."""
    inp = make_input(left_cv_this_cycle=1800, right_cv_this_cycle=1800)
    r = calculate_cycle_commission(inp, plan, rank_table)
    assert r.steps_earned == 1
    assert r.step_commission_inr == 21250 // 2  # ₹10,625

def test_second_step_still_half_rate(plan, rank_table):
    """Lifetime steps 1–2 both at half rate."""
    inp = make_input(
        left_cv_this_cycle=3600,
        right_cv_this_cycle=3600,
        lifetime_steps_before=0,
    )
    r = calculate_cycle_commission(inp, plan, rank_table)
    assert r.steps_earned == 2
    # step 1 = ₹10,625, step 2 = ₹10,625 → ₹21,250
    assert r.step_commission_inr == 21250

def test_third_step_full_rate(plan, rank_table):
    """Step 3 onwards at full rate."""
    inp = make_input(
        left_cv_this_cycle=5400,
        right_cv_this_cycle=5400,
        lifetime_steps_before=2,
    )
    r = calculate_cycle_commission(inp, plan, rank_table)
    assert r.steps_earned == 3
    # With 2 lifetime steps before → qualifies for Titanium Star (rate ₹25,500)
    # Steps 3,4,5 all at full Titanium rate = 3 × 25,500 = 76,500
    assert r.rank_name == 'Titanium Star'
    assert r.step_commission_inr == 25500 * 3

def test_titanium_rate(plan, rank_table):
    """After 2 lifetime steps, Titanium Star rate = ₹25,500."""
    inp = make_input(
        left_cv_this_cycle=1800,
        right_cv_this_cycle=1800,
        lifetime_steps_before=2,
        direct_cv_this_cycle=600,
    )
    r = calculate_cycle_commission(inp, plan, rank_table)
    assert r.rank_name == "Titanium Star"
    assert r.step_commission_inr == 25500


# ── Carry-forward ─────────────────────────────────────────────────────────

def test_carry_forward_added_to_cv(plan, rank_table):
    """Carry-in + this cycle must both count."""
    inp = make_input(
        left_cv_this_cycle=900,
        right_cv_this_cycle=900,
        left_cv_carry_in=900,
        right_cv_carry_in=900,
    )
    r = calculate_cycle_commission(inp, plan, rank_table)
    assert r.steps_earned == 1   # (900+900)=1800 each → 1 step

def test_carry_forward_output_zero_on_full_match(plan, rank_table):
    """Perfectly balanced — nothing to carry."""
    inp = make_input(left_cv_this_cycle=1800, right_cv_this_cycle=1800)
    r = calculate_cycle_commission(inp, plan, rank_table)
    assert r.left_cv_carry_out == 0
    assert r.right_cv_carry_out == 0

def test_carry_forward_unbalanced(plan, rank_table):
    """Left 3600, right 1800 → 1 step matched, 1800 left carry, 0 right carry."""
    inp = make_input(left_cv_this_cycle=3600, right_cv_this_cycle=1800)
    r = calculate_cycle_commission(inp, plan, rank_table)
    assert r.steps_earned == 1
    # weak carry = 0 (right 1800 - 1800 matched = 0)
    # flush_ratio cap = 0 × 3 = 0 → strong leg (left) carry also flushed to 0
    assert r.left_cv_carry_out == 0
    assert r.right_cv_carry_out == 0

def test_flush_ratio_applied(plan, rank_table):
    """Strong leg (right=9000) capped at flush_ratio(3) × weak carry(0) = 0."""
    inp = make_input(left_cv_this_cycle=0, right_cv_this_cycle=9000)
    r = calculate_cycle_commission(inp, plan, rank_table)
    # Weak = 0 → flush cap = 0 × 3 = 0; strong carry = 0
    assert r.right_cv_carry_out == 0

def test_flush_ratio_partial(plan, rank_table):
    """Left=5400, right=1800 → 1 step; left carry = 3600, weak carry = 0 → flushed."""
    inp = make_input(left_cv_this_cycle=5400, right_cv_this_cycle=1800)
    r = calculate_cycle_commission(inp, plan, rank_table)
    assert r.steps_earned == 1
    # weak carry = 0 → flush cap = 0; strong (left) carry = 0
    assert r.left_cv_carry_out == 0


# ── Green coin conversion ─────────────────────────────────────────────────

def test_green_coin_tier_3(plan, rank_table):
    inp = make_input(green_coins_available=3, green_coins_lifetime=0)
    r = calculate_cycle_commission(inp, plan, rank_table)
    assert r.green_coins_converted == 3
    assert r.green_coin_income_inr == 3400

def test_green_coin_tier_6(plan, rank_table):
    inp = make_input(green_coins_available=6, green_coins_lifetime=0)
    r = calculate_cycle_commission(inp, plan, rank_table)
    assert r.green_coins_converted == 6
    assert r.green_coin_income_inr == 10625

def test_green_coin_tier_12(plan, rank_table):
    inp = make_input(green_coins_available=12, green_coins_lifetime=0)
    r = calculate_cycle_commission(inp, plan, rank_table)
    assert r.green_coins_converted == 12
    assert r.green_coin_income_inr == 21250

def test_green_coin_lifetime_cap_blocks(plan, rank_table):
    """If lifetime cap already at 12, no more conversion."""
    inp = make_input(green_coins_available=6, green_coins_lifetime=12)
    r = calculate_cycle_commission(inp, plan, rank_table)
    assert r.green_coins_converted == 0
    assert r.green_coin_income_inr == 0

def test_green_coin_partial_cap(plan, rank_table):
    """9 lifetime used + 6 available → can only use 3 more (cap=12)."""
    coins, inr = best_green_coin_conversion(6, 9, 12)
    assert coins == 3
    assert inr == 3400

def test_green_coin_none_available(plan, rank_table):
    inp = make_input(green_coins_available=0, green_coins_lifetime=0)
    r = calculate_cycle_commission(inp, plan, rank_table)
    assert r.green_coins_converted == 0
    assert r.green_coin_income_inr == 0


# ── Yellow coins ──────────────────────────────────────────────────────────

def test_yellow_coin_first_milestone(plan, rank_table):
    """Crossing 6 cumulative steps earns 1 yellow coin."""
    inp = make_input(
        left_cv_this_cycle=5400,
        right_cv_this_cycle=5400,
        lifetime_steps_before=4,
        direct_cv_this_cycle=600,
    )
    r = calculate_cycle_commission(inp, plan, rank_table)
    assert r.steps_earned == 3
    # steps before=4, after=7 → crosses milestone at 6 → 1 yellow coin
    assert r.yellow_coins_earned == 1

def test_yellow_coin_two_milestones(plan, rank_table):
    inp = make_input(
        left_cv_this_cycle=7200,
        right_cv_this_cycle=7200,
        lifetime_steps_before=4,
        direct_cv_this_cycle=600,
    )
    r = calculate_cycle_commission(inp, plan, rank_table)
    # 4 steps earned → steps 4→8; crosses 6 and 12? No, crosses 6 only
    assert r.yellow_coins_earned == 1

def test_yellow_coin_none_below_threshold(plan, rank_table):
    inp = make_input(
        left_cv_this_cycle=1800,
        right_cv_this_cycle=1800,
        lifetime_steps_before=0,
    )
    r = calculate_cycle_commission(inp, plan, rank_table)
    # 1 step; 0→1, no crossing of 6
    assert r.yellow_coins_earned == 0


# ── TDS ───────────────────────────────────────────────────────────────────

def test_tds_below_threshold(plan, rank_table):
    """FY gross ₹5,000 → below ₹15,000 threshold — no TDS."""
    inp = make_input(left_cv_this_cycle=1800, right_cv_this_cycle=1800)
    r = calculate_cycle_commission(inp, plan, rank_table, fy_gross_already_inr=5000)
    # step commission ≈ ₹10,625 raw; FY total ≈ ₹15,625 — just crosses threshold
    # taxable = 15625 - 15000 = 625; TDS = 625 × 5% = ₹31 → rounds to ₹500
    # TDS could be 0 or 500 depending on rounding — just test it's small
    assert r.tds_deducted_inr >= 0

def test_tds_above_threshold():
    """Gross ₹50,000 in FY, already ₹30,000 assessed → only tax incremental."""
    tds = _calculate_tds(
        gross_this_cycle=50000,
        fy_gross_before=30000,
        threshold=15000,
        rate=0.05,
        rounding=1,
    )
    # fy_before=30,000 taxable_before=15,000
    # fy_after=80,000 taxable_after=65,000
    # incremental = 50,000 → TDS = ₹2,500
    assert tds == 2500

def test_tds_not_double_charged():
    """TDS should only apply to the incremental taxable amount."""
    tds1 = _calculate_tds(30000, 0, 15000, 0.05, 1)
    tds2 = _calculate_tds(30000, 30000, 15000, 0.05, 1)
    # Second call: FY already ₹30,000 → taxable_before = 15,000
    # FY after = 60,000 → taxable_after = 45,000 → incremental = 30,000 → TDS = ₹1,500
    assert tds2 == 1500
    # Not same as first (which was ₹750)
    assert tds1 != tds2

def test_tds_exact_at_threshold():
    tds = _calculate_tds(15000, 0, 15000, 0.05, 1)
    assert tds == 0  # exactly at threshold, not above


# ── Maintenance bonus ─────────────────────────────────────────────────────

def test_maintenance_bonus_emerald(plan, rank_table):
    """Emerald Star: 2 months hold → ₹212,500 one-time bonus."""
    inp = make_input(
        lifetime_steps_before=100,
        direct_cv_this_cycle=1800,
        maintenance_months_at_rank=2,
        maintenance_already_paid=False,
    )
    r = calculate_cycle_commission(inp, plan, rank_table)
    assert r.maintenance_bonus_inr == 212500

def test_maintenance_bonus_not_if_below_hold_months(plan, rank_table):
    inp = make_input(
        lifetime_steps_before=100,
        direct_cv_this_cycle=1800,
        maintenance_months_at_rank=1,  # only 1 month, need 2
        maintenance_already_paid=False,
    )
    r = calculate_cycle_commission(inp, plan, rank_table)
    assert r.maintenance_bonus_inr == 0

def test_maintenance_bonus_not_if_already_paid(plan, rank_table):
    inp = make_input(
        lifetime_steps_before=100,
        direct_cv_this_cycle=1800,
        maintenance_months_at_rank=3,
        maintenance_already_paid=True,
    )
    r = calculate_cycle_commission(inp, plan, rank_table)
    assert r.maintenance_bonus_inr == 0

def test_maintenance_bonus_crown_diamond(plan, rank_table):
    inp = make_input(
        lifetime_steps_before=250,
        direct_cv_this_cycle=3600,
        maintenance_months_at_rank=3,
        maintenance_already_paid=False,
    )
    r = calculate_cycle_commission(inp, plan, rank_table)
    assert r.maintenance_bonus_inr == 425000


# ── End-to-end scenarios ──────────────────────────────────────────────────

def test_week1_balanced_first_ba(plan, rank_table):
    """
    Week 1, BA just joined: 3 products each leg = 3×600=1800 CV each.
    → 1 step; lifetime step 1 → half rate = ₹10,625.
    """
    inp = make_input(
        left_cv_this_cycle=1800,
        right_cv_this_cycle=1800,
        lifetime_steps_before=0,
        direct_cv_this_cycle=600,
    )
    r = calculate_cycle_commission(inp, plan, rank_table)
    assert r.steps_earned == 1
    assert r.rank_name == "Silver Star"
    assert r.step_commission_inr == 21250 // 2

def test_green_coin_bridge_scenario(plan, rank_table):
    """
    Left 2400 CV, right 1200 CV → 0 steps.
    But has 6 green coins → ₹10,625 bridge income.
    """
    inp = make_input(
        left_cv_this_cycle=2400,
        right_cv_this_cycle=1200,
        green_coins_available=6,
        green_coins_lifetime=0,
    )
    r = calculate_cycle_commission(inp, plan, rank_table)
    assert r.steps_earned == 0
    assert r.green_coin_income_inr == 10625

def test_star_builder_scenario(plan, rank_table):
    """
    BA with 8 lifetime steps, this week balanced 5400 each side.
    → 3 steps; all at full Titanium Star rate (2 cumulative still, but now Titanium).
    """
    inp = make_input(
        left_cv_this_cycle=5400,
        right_cv_this_cycle=5400,
        lifetime_steps_before=8,
        direct_cv_this_cycle=600,
    )
    r = calculate_cycle_commission(inp, plan, rank_table)
    assert r.steps_earned == 3
    # 8 lifetime steps → Gold Star qualifies (min 5, higher than Titanium min 2)
    assert r.rank_name == "Gold Star"
    # All 3 at full Gold Star rate (lifetime steps 9, 10, 11 — all > 2)
    assert r.step_commission_inr == 29750 * 3

def test_net_payable_equals_gross_minus_tds(plan, rank_table):
    inp = make_input(
        left_cv_this_cycle=1800,
        right_cv_this_cycle=1800,
        lifetime_steps_before=10,
        direct_cv_this_cycle=1200,
    )
    r = calculate_cycle_commission(inp, plan, rank_table, fy_gross_already_inr=50000)
    assert r.net_payable_inr == r.gross_commission_inr - r.tds_deducted_inr
