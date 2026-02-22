"""
Tests for the net worth calculator V2 modules.

Covers: tax_data, living_costs, market_mapping, networth_calculator.
Run with: cd backend && python -m pytest tests/ -v
"""

import sys
from pathlib import Path

# Ensure backend directory is on path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

# ═══════════════════════════════════════════════════════════════════════════════
# TAX DATA TESTS
# ═══════════════════════════════════════════════════════════════════════════════

from tax_data import calculate_annual_tax


class TestTaxCalculation:
    """Test progressive tax bracket calculations for various countries."""

    def test_usa_california_150k(self):
        """USA (CA) at $150K should have ~31% effective tax rate."""
        after_tax = calculate_annual_tax(150, "USA", us_state="CA")
        effective_rate = 1 - after_tax / 150
        assert 0.28 <= effective_rate <= 0.35, (
            f"USA CA $150K: expected 28-35% effective, got {effective_rate:.1%}"
        )

    def test_usa_washington_no_state_tax(self):
        """Washington state has no income tax — should be lower than California."""
        after_tax_wa = calculate_annual_tax(150, "USA", us_state="WA")
        after_tax_ca = calculate_annual_tax(150, "USA", us_state="CA")
        assert after_tax_wa > after_tax_ca, (
            f"WA (no state tax) should keep more than CA: WA={after_tax_wa}, CA={after_tax_ca}"
        )

    def test_usa_effective_rate_sanity(self):
        """USA effective rate should be between 15-50% for typical incomes."""
        for salary in [50, 100, 150, 200, 300]:
            after_tax = calculate_annual_tax(salary, "USA", us_state="CA")
            effective_rate = 1 - after_tax / salary
            assert 0.15 <= effective_rate <= 0.50, (
                f"USA CA ${salary}K: effective rate {effective_rate:.1%} out of range"
            )

    def test_uk_80k(self):
        """UK at $80K should have ~25% effective tax rate."""
        after_tax = calculate_annual_tax(80, "UK")
        effective_rate = 1 - after_tax / 80
        assert 0.20 <= effective_rate <= 0.32, (
            f"UK $80K: expected 20-32% effective, got {effective_rate:.1%}"
        )

    def test_germany_75k(self):
        """Germany at $75K should have ~35-42% effective rate (incl. social)."""
        after_tax = calculate_annual_tax(75, "Germany")
        effective_rate = 1 - after_tax / 75
        assert 0.32 <= effective_rate <= 0.45, (
            f"Germany $75K: expected 32-45% effective, got {effective_rate:.1%}"
        )

    def test_switzerland_130k(self):
        """Switzerland at $130K should have ~25-32% effective rate."""
        after_tax = calculate_annual_tax(130, "Switzerland")
        effective_rate = 1 - after_tax / 130
        assert 0.22 <= effective_rate <= 0.35, (
            f"Switzerland $130K: expected 22-35% effective, got {effective_rate:.1%}"
        )

    def test_uae_zero_tax(self):
        """UAE should have 0% income tax."""
        after_tax = calculate_annual_tax(100, "UAE")
        assert after_tax == 100.0, f"UAE should be 0% tax, got after_tax={after_tax}"

    def test_pakistan_low_income(self):
        """Pakistan at baseline ~$9.5K should have low effective rate."""
        after_tax = calculate_annual_tax(9.5, "Pakistan")
        effective_rate = 1 - after_tax / 9.5
        assert 0.05 <= effective_rate <= 0.20, (
            f"Pakistan $9.5K: expected 5-20% effective, got {effective_rate:.1%}"
        )

    def test_zero_salary(self):
        """$0 salary should return $0 after tax."""
        after_tax = calculate_annual_tax(0, "USA", us_state="CA")
        assert after_tax == 0.0

    def test_progressive_nature(self):
        """Higher salary should mean higher effective tax rate."""
        rate_50 = 1 - calculate_annual_tax(50, "USA", us_state="CA") / 50
        rate_150 = 1 - calculate_annual_tax(150, "USA", us_state="CA") / 150
        rate_300 = 1 - calculate_annual_tax(300, "USA", us_state="CA") / 300
        assert rate_50 < rate_150 < rate_300, (
            f"Tax should be progressive: {rate_50:.1%} < {rate_150:.1%} < {rate_300:.1%}"
        )

    def test_after_tax_positive(self):
        """After-tax income should always be positive for positive salary."""
        for country in [
            "USA",
            "UK",
            "Germany",
            "Canada",
            "India",
            "Pakistan",
        ]:
            kwargs = {"us_state": "CA"} if country == "USA" else {}
            after_tax = calculate_annual_tax(50, country, **kwargs)
            assert after_tax > 0, (
                f"{country} $50K: after_tax should be positive, got {after_tax}"
            )

    def test_after_tax_less_than_gross(self):
        """After-tax income should be less than gross (except 0% tax countries)."""
        for country in ["USA", "UK", "Germany", "Canada", "India"]:
            kwargs = {"us_state": "CA"} if country == "USA" else {}
            after_tax = calculate_annual_tax(100, country, **kwargs)
            assert after_tax < 100, (
                f"{country} $100K: after_tax should be < gross, got {after_tax}"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# LIVING COSTS TESTS
# ═══════════════════════════════════════════════════════════════════════════════

from living_costs import (
    get_annual_living_cost,
    get_study_living_cost,
    get_pakistan_living_cost,
)


class TestLivingCosts:
    """Test living cost lookups for various cities and profiles."""

    def test_single_less_than_family(self):
        """Family living costs should be higher than single."""
        for city in ["Bay Area", "London", "Berlin"]:
            single = get_annual_living_cost(city, "single")
            family = get_annual_living_cost(city, "family")
            assert family > single, (
                f"{city}: family (${family}K) should be > single (${single}K)"
            )

    def test_student_cheapest(self):
        """Student living costs should be cheapest profile."""
        for city in ["Bay Area", "London", "Berlin"]:
            student = get_annual_living_cost(city, "student")
            single = get_annual_living_cost(city, "single")
            assert student < single, (
                f"{city}: student (${student}K) should be < single (${single}K)"
            )

    def test_sf_more_expensive_than_berlin(self):
        """High-cost US cities should be expensive."""
        sf = get_annual_living_cost("Bay Area", "single")
        assert sf >= 15, f"Bay Area should be at least $15K, got ${sf}K"

    def test_pakistan_living_cost_positive(self):
        """Pakistan living costs should be positive."""
        for household in ["single", "family"]:
            cost = get_pakistan_living_cost(household)
            assert cost > 0, f"Pakistan {household} should be positive, got {cost}"

    def test_pakistan_family_more_than_single(self):
        """Pakistan family costs should exceed single."""
        single = get_pakistan_living_cost("single")
        family = get_pakistan_living_cost("family")
        assert family > single, (
            f"Pakistan family (${family}K) should be > single (${single}K)"
        )

    def test_study_living_cost_positive(self):
        """Study living costs should be positive for valid countries."""
        for country in ["USA", "UK", "Germany", "Switzerland"]:
            cost = get_study_living_cost(country, "student")
            assert cost > 0, f"Study cost in {country} should be positive, got {cost}"

    def test_all_costs_reasonable_range(self):
        """Living costs should be in $2K-$120K range (no outliers)."""
        for city in [
            "Bay Area",
            "NYC",
            "London",
            "Berlin",
            "Toronto",
            "Zurich",
            "Singapore",
            "Mumbai",
            "Sydney",
        ]:
            for profile in ["single", "family"]:
                cost = get_annual_living_cost(city, profile)
                assert 2 <= cost <= 120, (
                    f"{city} {profile}: ${cost}K is outside reasonable range"
                )

    def test_fallback_for_unknown_city(self):
        """Unknown city with known country should fall back to country default."""
        # This tests the fallback mechanism
        cost = get_annual_living_cost("SomeUnknownCity", "single", country="Germany")
        assert cost > 0, "Should fall back to country default for unknown city"


# ═══════════════════════════════════════════════════════════════════════════════
# MARKET MAPPING TESTS
# ═══════════════════════════════════════════════════════════════════════════════

from market_mapping import get_market_info, MarketInfo


class TestMarketMapping:
    """Test primary_market string to location mapping."""

    def test_usa_bay_area(self):
        """'USA (Bay Area)' should map to USA, California."""
        info = get_market_info("USA (Bay Area)", "USA")
        assert info.work_country == "USA"
        assert info.us_state == "CA"
        assert info.work_city is not None

    def test_usa_nyc(self):
        """'USA (NYC)' should map to USA, New York state."""
        info = get_market_info("USA (NYC)", "USA")
        assert info.work_country == "USA"
        assert info.us_state == "NY"

    def test_usa_seattle(self):
        """'USA (Seattle/National)' should map to USA, Seattle, WA."""
        info = get_market_info("USA (Seattle/National)", "USA")
        assert info.work_country == "USA"
        assert info.us_state == "WA"

    def test_uk_london(self):
        """'London' should map to UK."""
        info = get_market_info("London", "UK")
        assert info.work_country == "UK"

    def test_germany(self):
        """'Berlin' should map to Germany."""
        info = get_market_info("Berlin", "Germany")
        assert info.work_country == "Germany"

    def test_india_usa_maps_to_india(self):
        """'India / USA' should map to India (salary is India-calibrated)."""
        info = get_market_info("India / USA", "India")
        assert info.work_country == "India", (
            f"'India / USA' should map to India, got {info.work_country}"
        )

    def test_canada_usa_maps_to_canada(self):
        """'Canada / USA' should map to Canada (salary is Canada-calibrated)."""
        info = get_market_info("Canada / USA", "Canada")
        assert info.work_country == "Canada", (
            f"'Canada / USA' should map to Canada, got {info.work_country}"
        )

    def test_canada_usa_reloc_maps_to_usa(self):
        """'Canada / USA (reloc)' should map to USA (explicit relocation)."""
        info = get_market_info("Canada / USA (reloc)", "Canada")
        assert info.work_country == "USA", (
            f"'Canada / USA (reloc)' should map to USA, got {info.work_country}"
        )

    def test_uae_maps_correctly(self):
        """UAE market should map to UAE."""
        info = get_market_info("Gulf States (relocated)", "UAE")
        assert info.work_country == "UAE"

    def test_return_type(self):
        """get_market_info should return a MarketInfo instance."""
        info = get_market_info("USA (Bay Area)", "USA")
        assert isinstance(info, MarketInfo)

    def test_all_fields_present(self):
        """MarketInfo should have work_country, work_city, us_state fields."""
        info = get_market_info("USA (Bay Area)", "USA")
        assert hasattr(info, "work_country")
        assert hasattr(info, "work_city")
        assert hasattr(info, "us_state")


# ═══════════════════════════════════════════════════════════════════════════════
# NET WORTH CALCULATOR TESTS
# ═══════════════════════════════════════════════════════════════════════════════

from networth_calculator import (
    interpolate_salary,
    calculate_baseline_networth,
    calculate_program_networth,
    calculate_all_programs,
    TOTAL_YEARS,
)


class TestSalaryInterpolation:
    """Test salary interpolation between Y1/Y5/Y10 data points."""

    def test_at_y1(self):
        """Work year 1 should return Y1 salary."""
        assert interpolate_salary(100, 150, 200, 1) == 100

    def test_at_y5(self):
        """Work year 5 should return Y5 salary."""
        assert interpolate_salary(100, 150, 200, 5) == 150

    def test_at_y10(self):
        """Work year 10 should return Y10 salary."""
        assert interpolate_salary(100, 150, 200, 10) == 200

    def test_midpoint_y1_y5(self):
        """Work year 3 should be midpoint of Y1-Y5 (linear)."""
        salary = interpolate_salary(100, 200, 300, 3)
        assert salary == 150, f"Expected 150, got {salary}"

    def test_beyond_y10(self):
        """Beyond year 10 should cap at Y10."""
        assert interpolate_salary(100, 150, 200, 15) == 200

    def test_before_y1(self):
        """Before year 1 should return Y1."""
        assert interpolate_salary(100, 150, 200, 0) == 100

    def test_monotonic_increase(self):
        """Salary should increase monotonically when Y1 < Y5 < Y10."""
        prev = 0
        for yr in range(1, 11):
            salary = interpolate_salary(100, 150, 200, yr)
            assert salary >= prev, f"Year {yr}: ${salary}K < prev ${prev}K"
            prev = salary


class TestBaselineNetworth:
    """Test the no-masters baseline calculation."""

    def test_returns_dict(self):
        """Baseline should return a dict with total and breakdown."""
        result = calculate_baseline_networth()
        assert "total_networth_k" in result
        assert "yearly_breakdown" in result

    def test_12_years(self):
        """Baseline should have exactly 12 yearly entries."""
        result = calculate_baseline_networth()
        assert len(result["yearly_breakdown"]) == TOTAL_YEARS

    def test_salary_grows(self):
        """Salary should grow year over year."""
        result = calculate_baseline_networth()
        years = result["yearly_breakdown"]
        for i in range(1, len(years)):
            assert years[i]["gross_salary_k"] > years[i - 1]["gross_salary_k"]

    def test_household_transition(self):
        """Years 1-4 single, years 5-12 family."""
        result = calculate_baseline_networth()
        years = result["yearly_breakdown"]
        for yr in years:
            if yr["calendar_year"] < 5:
                assert yr["household"] == "single", (
                    f"Year {yr['calendar_year']} should be single"
                )
            else:
                assert yr["household"] == "family", (
                    f"Year {yr['calendar_year']} should be family"
                )

    def test_known_result(self):
        """Baseline net worth should be approximately -$11.8K."""
        result = calculate_baseline_networth()
        assert -20 <= result["total_networth_k"] <= 0, (
            f"Baseline should be near -$11.8K, got ${result['total_networth_k']}K"
        )

    def test_override_salary(self):
        """Override baseline salary should change the result."""
        default = calculate_baseline_networth()
        higher = calculate_baseline_networth(baseline_salary=20.0)
        assert higher["total_networth_k"] > default["total_networth_k"]

    def test_override_growth(self):
        """Higher growth rate should increase net worth."""
        low_growth = calculate_baseline_networth(baseline_growth=0.03)
        high_growth = calculate_baseline_networth(baseline_growth=0.15)
        assert high_growth["total_networth_k"] > low_growth["total_networth_k"]


class TestProgramNetworth:
    """Test program-level net worth calculation."""

    @pytest.fixture
    def sample_program(self):
        """A sample program dict simulating a top US CS program."""
        return {
            "id": 999,
            "program_name": "MS CS Test",
            "university_name": "Test University",
            "field": "CS/SWE",
            "tuition_usd": 50,  # $50K total (moderate)
            "y1_salary_usd": 180,
            "y5_salary_usd": 250,
            "y10_salary_usd": 350,
            "funding_tier": "tier2_elite_us",
            "duration_years": 2,
            "primary_market": "USA (Seattle/National)",
            "country": "USA",
        }

    @pytest.fixture
    def low_salary_program(self):
        """A program with low salaries (e.g., India-based)."""
        return {
            "id": 998,
            "program_name": "MS CS Test India",
            "university_name": "Test Indian University",
            "field": "CS/SWE",
            "tuition_usd": 15,
            "y1_salary_usd": 25,
            "y5_salary_usd": 40,
            "y10_salary_usd": 55,
            "funding_tier": "tier4_asia_regional",
            "duration_years": 2,
            "primary_market": "India (Bangalore)",
            "country": "India",
        }

    def test_returns_expected_fields(self, sample_program):
        """Result should contain all expected fields."""
        result = calculate_program_networth(sample_program)
        expected_fields = [
            "program_id",
            "university",
            "program_name",
            "country",
            "field",
            "work_country",
            "work_city",
            "tuition_k",
            "total_study_cost_k",
            "masters_networth_k",
            "baseline_networth_k",
            "net_benefit_k",
            "effective_tax_rate_y1",
            "effective_tax_rate_y10",
            "y1_salary_k",
            "y5_salary_k",
            "y10_salary_k",
            "yearly_breakdown",
        ]
        for field in expected_fields:
            assert field in result, f"Missing field: {field}"

    def test_yearly_breakdown_length(self, sample_program):
        """Should have 12 yearly entries (2 study + 10 work)."""
        result = calculate_program_networth(sample_program)
        assert len(result["yearly_breakdown"]) == 12

    def test_study_phase_no_income(self, sample_program):
        """Study years should have 0 income."""
        result = calculate_program_networth(sample_program)
        study_years = [
            y for y in result["yearly_breakdown"] if y.get("phase") == "study"
        ]
        for yr in study_years:
            assert yr["gross_salary_k"] == 0
            assert yr["after_tax_k"] == 0

    def test_work_phase_has_income(self, sample_program):
        """Work years should have positive income."""
        result = calculate_program_networth(sample_program)
        work_years = [y for y in result["yearly_breakdown"] if y.get("phase") == "work"]
        for yr in work_years:
            assert yr["gross_salary_k"] > 0
            assert yr["after_tax_k"] > 0

    def test_high_salary_program_positive_benefit(self, sample_program):
        """A well-paying US program should have net worth far exceeding baseline."""
        result = calculate_program_networth(sample_program)
        # The masters net worth itself should be large and positive
        # (net_benefit may be slightly negative due to high Bay Area costs vs Pakistan baseline)
        assert result["masters_networth_k"] > 500, (
            f"$130K+ US program should build significant net worth, got ${result['masters_networth_k']}K"
        )

    def test_work_country_correct(self, sample_program):
        """Work country should be correctly mapped from primary_market."""
        result = calculate_program_networth(sample_program)
        assert result["work_country"] == "USA"

    def test_effective_tax_rates_valid(self, sample_program):
        """Effective tax rates should be between 0 and 60%."""
        result = calculate_program_networth(sample_program)
        assert 0 <= result["effective_tax_rate_y1"] <= 0.6
        assert 0 <= result["effective_tax_rate_y10"] <= 0.6

    def test_tuition_included_in_costs(self, sample_program):
        """Total study cost should include tuition."""
        result = calculate_program_networth(sample_program)
        assert result["total_study_cost_k"] >= result["tuition_k"]

    def test_cumulative_tracking(self, sample_program):
        """Cumulative net worth should be running sum of annual savings."""
        result = calculate_program_networth(sample_program)
        running = 0
        for yr in result["yearly_breakdown"]:
            running += yr["annual_savings_k"]
            assert abs(yr["cumulative_k"] - round(running, 2)) < 0.05, (
                f"Year {yr.get('calendar_year')}: cumulative mismatch"
            )


class TestCalculateAllPrograms:
    """Test the full calculation across all 265 programs."""

    @pytest.fixture(scope="class")
    def all_data(self):
        """Run calculate_all_programs once for the class."""
        return calculate_all_programs()

    def test_returns_all_programs(self, all_data):
        """Should return results for all 265 programs."""
        assert len(all_data["programs"]) == 265

    def test_baseline_included(self, all_data):
        """Result should include baseline calculation."""
        assert "baseline" in all_data
        assert "total_networth_k" in all_data["baseline"]

    def test_assumptions_included(self, all_data):
        """Result should include assumptions."""
        assert "assumptions" in all_data
        assert all_data["assumptions"]["total_years"] == 12

    def test_summary_stats(self, all_data):
        """Summary should include expected statistics."""
        summary = all_data["summary"]
        assert "total_programs" in summary
        assert "programs_with_positive_benefit" in summary
        assert "by_tier" in summary
        assert "by_field" in summary
        assert "by_work_country" in summary

    def test_majority_positive(self, all_data):
        """At least 60% of programs should have positive net benefit."""
        positive = all_data["summary"]["programs_with_positive_benefit"]
        total = all_data["summary"]["total_programs"]
        ratio = positive / total
        assert ratio >= 0.6, f"Only {ratio:.0%} positive, expected >= 60%"

    def test_sorted_by_benefit(self, all_data):
        """Programs should be sorted by net benefit descending."""
        programs = all_data["programs"]
        for i in range(len(programs) - 1):
            assert programs[i]["net_benefit_k"] >= programs[i + 1]["net_benefit_k"]

    def test_top_program_is_baruch(self, all_data):
        """Baruch MFE should be the top program."""
        top = all_data["programs"][0]
        assert "Baruch" in top["university"], (
            f"Top program should be Baruch, got {top['university']}"
        )

    def test_no_null_benefits(self, all_data):
        """No program should have None/null net benefit."""
        for p in all_data["programs"]:
            assert p["net_benefit_k"] is not None, (
                f"Program {p['program_id']} has null benefit"
            )

    def test_override_baseline_salary(self):
        """Override salary should change all results."""
        default = calculate_all_programs()
        higher = calculate_all_programs(baseline_salary=20.0)
        # Higher baseline salary = lower net benefit (opportunity cost is higher)
        assert (
            higher["programs"][0]["net_benefit_k"]
            < default["programs"][0]["net_benefit_k"]
        )


# ═══════════════════════════════════════════════════════════════════════════════
# COMFORTABLE LIFESTYLE TIER TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestComfortableLivingCosts:
    """Test that the comfortable lifestyle tier is loaded and priced correctly."""

    def test_comfortable_single_higher_than_frugal(self):
        """Comfortable single costs should exceed frugal for all tested cities."""
        for city in ["Bay Area", "London", "Berlin", "Zurich", "Singapore", "Toronto"]:
            frugal = get_annual_living_cost(city, "single", lifestyle="frugal")
            comfy = get_annual_living_cost(city, "single", lifestyle="comfortable")
            assert comfy > frugal, (
                f"{city} single: comfortable (${comfy}K) should > frugal (${frugal}K)"
            )

    def test_comfortable_family_higher_than_frugal(self):
        """Comfortable family costs should exceed frugal for all tested cities."""
        for city in ["Bay Area", "London", "Berlin", "Zurich", "Singapore", "Toronto"]:
            frugal = get_annual_living_cost(city, "family", lifestyle="frugal")
            comfy = get_annual_living_cost(city, "family", lifestyle="comfortable")
            assert comfy > frugal, (
                f"{city} family: comfortable (${comfy}K) should > frugal (${frugal}K)"
            )

    def test_comfortable_student_higher_than_frugal(self):
        """Comfortable student costs should exceed frugal."""
        for city in ["Bay Area", "London", "Berlin"]:
            frugal = get_annual_living_cost(city, "student", lifestyle="frugal")
            comfy = get_annual_living_cost(city, "student", lifestyle="comfortable")
            assert comfy > frugal, (
                f"{city} student: comfortable (${comfy}K) should > frugal (${frugal}K)"
            )

    def test_comfortable_costs_reasonable_range(self):
        """Comfortable costs should still be in $3K-$160K range."""
        for city in ["Bay Area", "NYC", "London", "Berlin", "Zurich", "Mumbai"]:
            for profile in ["single", "family"]:
                cost = get_annual_living_cost(city, profile, lifestyle="comfortable")
                assert 3 <= cost <= 160, (
                    f"{city} {profile} comfortable: ${cost}K is outside reasonable range"
                )

    def test_comfortable_premium_range(self):
        """Comfortable should be ~20-50% above frugal (not 2x or 0.5x)."""
        for city in ["Bay Area", "London", "Berlin", "Singapore"]:
            frugal = get_annual_living_cost(city, "single", lifestyle="frugal")
            comfy = get_annual_living_cost(city, "single", lifestyle="comfortable")
            premium = (comfy - frugal) / frugal
            assert 0.15 <= premium <= 0.55, (
                f"{city} single comfortable premium {premium:.0%} outside 15-55% range"
            )

    def test_pakistan_comfortable_higher_than_frugal(self):
        """Pakistan comfortable costs should exceed frugal."""
        for household in ["single", "family"]:
            frugal = get_pakistan_living_cost(household, lifestyle="frugal")
            comfy = get_pakistan_living_cost(household, lifestyle="comfortable")
            assert comfy > frugal, (
                f"Pakistan {household}: comfortable (${comfy}K) should > frugal (${frugal}K)"
            )

    def test_study_comfortable_higher_than_frugal(self):
        """Study living costs (comfortable) should exceed frugal."""
        for country in ["USA", "UK", "Germany"]:
            frugal = get_study_living_cost(country, "student", lifestyle="frugal")
            comfy = get_study_living_cost(country, "student", lifestyle="comfortable")
            assert comfy > frugal, (
                f"{country} study: comfortable (${comfy}K) should > frugal (${frugal}K)"
            )

    def test_default_lifestyle_is_frugal(self):
        """Calling without lifestyle param should return frugal values."""
        default = get_annual_living_cost("Bay Area", "single")
        frugal = get_annual_living_cost("Bay Area", "single", lifestyle="frugal")
        assert default == frugal, (
            f"Default (${default}K) should equal frugal (${frugal}K)"
        )


class TestComfortableBaseline:
    """Test baseline net worth with comfortable lifestyle."""

    def test_comfortable_baseline_lower(self):
        """Comfortable baseline net worth should be lower (more negative) than frugal."""
        frugal = calculate_baseline_networth(lifestyle="frugal")
        comfy = calculate_baseline_networth(lifestyle="comfortable")
        assert comfy["total_networth_k"] < frugal["total_networth_k"], (
            f"Comfortable baseline (${comfy['total_networth_k']:.0f}K) should be < "
            f"frugal (${frugal['total_networth_k']:.0f}K)"
        )

    def test_comfortable_baseline_12_years(self):
        """Comfortable baseline should still have 12 yearly entries."""
        result = calculate_baseline_networth(lifestyle="comfortable")
        assert len(result["yearly_breakdown"]) == TOTAL_YEARS

    def test_comfortable_baseline_higher_costs(self):
        """Living costs in comfortable baseline should be higher each year."""
        frugal = calculate_baseline_networth(lifestyle="frugal")
        comfy = calculate_baseline_networth(lifestyle="comfortable")
        for f_yr, c_yr in zip(frugal["yearly_breakdown"], comfy["yearly_breakdown"]):
            assert c_yr["living_cost_k"] >= f_yr["living_cost_k"], (
                f"Year {c_yr['calendar_year']}: comfortable cost ${c_yr['living_cost_k']}K "
                f"should >= frugal ${f_yr['living_cost_k']}K"
            )


class TestComfortableProgramNetworth:
    """Test program net worth with comfortable lifestyle."""

    @pytest.fixture
    def sample_program(self):
        """A sample US program for testing."""
        return {
            "id": 999,
            "program_name": "MS CS Test",
            "university_name": "Test University",
            "field": "CS/SWE",
            "tuition_usd": 50,
            "y1_salary_usd": 180,
            "y5_salary_usd": 250,
            "y10_salary_usd": 350,
            "funding_tier": "tier2_elite_us",
            "duration_years": 2,
            "primary_market": "USA (Seattle/National)",
            "country": "USA",
        }

    def test_comfortable_benefit_lower(self, sample_program):
        """Comfortable net benefit should be lower than frugal."""
        frugal = calculate_program_networth(sample_program, lifestyle="frugal")
        comfy = calculate_program_networth(sample_program, lifestyle="comfortable")
        assert comfy["net_benefit_k"] < frugal["net_benefit_k"], (
            f"Comfortable benefit (${comfy['net_benefit_k']:.0f}K) should be < "
            f"frugal (${frugal['net_benefit_k']:.0f}K)"
        )

    def test_comfortable_networth_lower(self, sample_program):
        """Comfortable masters networth should be lower than frugal."""
        frugal = calculate_program_networth(sample_program, lifestyle="frugal")
        comfy = calculate_program_networth(sample_program, lifestyle="comfortable")
        assert comfy["masters_networth_k"] < frugal["masters_networth_k"], (
            f"Comfortable NW (${comfy['masters_networth_k']:.0f}K) should be < "
            f"frugal (${frugal['masters_networth_k']:.0f}K)"
        )

    def test_comfortable_study_cost_higher(self, sample_program):
        """Comfortable total study cost should be higher."""
        frugal = calculate_program_networth(sample_program, lifestyle="frugal")
        comfy = calculate_program_networth(sample_program, lifestyle="comfortable")
        assert comfy["total_study_cost_k"] >= frugal["total_study_cost_k"], (
            f"Comfortable study cost (${comfy['total_study_cost_k']:.0f}K) should be >= "
            f"frugal (${frugal['total_study_cost_k']:.0f}K)"
        )

    def test_comfortable_assumptions_key(self, sample_program):
        """Comfortable should produce different (lower) networth than frugal."""
        frugal = calculate_program_networth(sample_program, lifestyle="frugal")
        comfy = calculate_program_networth(sample_program, lifestyle="comfortable")
        assert comfy["masters_networth_k"] != frugal["masters_networth_k"], (
            "Comfortable and frugal should produce different net worth values"
        )

    def test_frugal_assumptions_key(self, sample_program):
        """Default (no lifestyle arg) should match explicit frugal."""
        default = calculate_program_networth(sample_program)
        frugal = calculate_program_networth(sample_program, lifestyle="frugal")
        assert default["masters_networth_k"] == frugal["masters_networth_k"], (
            "Default should equal explicit frugal"
        )


class TestComfortableAllPrograms:
    """Test calculate_all_programs with comfortable lifestyle."""

    @pytest.fixture(scope="class")
    def comfortable_data(self):
        """Run calculate_all_programs once with comfortable lifestyle."""
        return calculate_all_programs(lifestyle="comfortable")

    @pytest.fixture(scope="class")
    def frugal_data(self):
        """Run calculate_all_programs once with frugal lifestyle."""
        return calculate_all_programs(lifestyle="frugal")

    def test_returns_all_programs(self, comfortable_data):
        """Comfortable should return results for all 265 programs."""
        assert len(comfortable_data["programs"]) == 265

    def test_fewer_positive_benefit(self, frugal_data, comfortable_data):
        """Comfortable should have fewer programs with positive benefit."""
        frugal_pos = frugal_data["summary"]["programs_with_positive_benefit"]
        comfy_pos = comfortable_data["summary"]["programs_with_positive_benefit"]
        assert comfy_pos < frugal_pos, (
            f"Comfortable ({comfy_pos} positive) should have fewer than "
            f"frugal ({frugal_pos} positive)"
        )

    def test_lower_average_benefit(self, frugal_data, comfortable_data):
        """Average net benefit should be lower with comfortable lifestyle."""
        frugal_avg = sum(p["net_benefit_k"] for p in frugal_data["programs"]) / len(
            frugal_data["programs"]
        )
        comfy_avg = sum(p["net_benefit_k"] for p in comfortable_data["programs"]) / len(
            comfortable_data["programs"]
        )
        assert comfy_avg < frugal_avg, (
            f"Comfortable avg (${comfy_avg:.0f}K) should < frugal avg (${frugal_avg:.0f}K)"
        )

    def test_lifestyle_in_assumptions(self, comfortable_data):
        """Assumptions should indicate comfortable lifestyle."""
        assert comfortable_data["assumptions"]["lifestyle"] == "comfortable"

    def test_no_null_benefits(self, comfortable_data):
        """No program should have None/null net benefit in comfortable mode."""
        for p in comfortable_data["programs"]:
            assert p["net_benefit_k"] is not None, (
                f"Program {p['program_id']} has null benefit in comfortable mode"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# FAMILY TRANSITION YEAR TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestFamilyTransitionBaseline:
    """Test family_transition_year effect on baseline net worth."""

    def test_later_marriage_higher_networth(self):
        """Later family transition should yield higher net worth (family costs > single)."""
        early = calculate_baseline_networth(family_transition_year=3)
        default = calculate_baseline_networth(family_transition_year=5)
        late = calculate_baseline_networth(family_transition_year=9)
        assert (
            early["total_networth_k"]
            < default["total_networth_k"]
            < late["total_networth_k"]
        ), (
            f"Expected early ({early['total_networth_k']:.0f}K) < default ({default['total_networth_k']:.0f}K) "
            f"< late ({late['total_networth_k']:.0f}K)"
        )

    def test_year_13_never_marry(self):
        """Year 13 = never marry, all single costs — highest baseline net worth."""
        never = calculate_baseline_networth(family_transition_year=13)
        default = calculate_baseline_networth(family_transition_year=5)
        assert never["total_networth_k"] > default["total_networth_k"], (
            f"Never marry (${never['total_networth_k']:.0f}K) should be > "
            f"default (${default['total_networth_k']:.0f}K)"
        )

    def test_year_1_all_family(self):
        """Year 1 = family from start — lowest baseline net worth."""
        year1 = calculate_baseline_networth(family_transition_year=1)
        default = calculate_baseline_networth(family_transition_year=5)
        assert year1["total_networth_k"] < default["total_networth_k"], (
            f"Year 1 (${year1['total_networth_k']:.0f}K) should be < "
            f"default (${default['total_networth_k']:.0f}K)"
        )

    def test_year_13_all_single_households(self):
        """When family_transition_year=13, all 12 years should be 'single'."""
        result = calculate_baseline_networth(family_transition_year=13)
        for yr in result["yearly_breakdown"]:
            assert yr["household"] == "single", (
                f"Year {yr['calendar_year']} should be single when never marry, "
                f"got {yr['household']}"
            )

    def test_year_1_all_family_households(self):
        """When family_transition_year=1, all 12 years should be 'family'."""
        result = calculate_baseline_networth(family_transition_year=1)
        for yr in result["yearly_breakdown"]:
            assert yr["household"] == "family", (
                f"Year {yr['calendar_year']} should be family when family_year=1, "
                f"got {yr['household']}"
            )

    def test_household_transition_at_year_7(self):
        """Years 1-6 single, years 7-12 family when family_transition_year=7."""
        result = calculate_baseline_networth(family_transition_year=7)
        for yr in result["yearly_breakdown"]:
            expected = "single" if yr["calendar_year"] < 7 else "family"
            assert yr["household"] == expected, (
                f"Year {yr['calendar_year']}: expected {expected}, got {yr['household']}"
            )

    def test_still_12_years(self):
        """Baseline should still have 12 yearly entries regardless of family_year."""
        for fy in [1, 5, 9, 13]:
            result = calculate_baseline_networth(family_transition_year=fy)
            assert len(result["yearly_breakdown"]) == TOTAL_YEARS, (
                f"family_year={fy}: expected {TOTAL_YEARS} years, got {len(result['yearly_breakdown'])}"
            )

    def test_default_matches_year_5(self):
        """Default (no family_transition_year) should match explicit year 5."""
        default = calculate_baseline_networth()
        explicit = calculate_baseline_networth(family_transition_year=5)
        assert default["total_networth_k"] == explicit["total_networth_k"], (
            f"Default (${default['total_networth_k']:.0f}K) should equal "
            f"explicit year 5 (${explicit['total_networth_k']:.0f}K)"
        )


class TestFamilyTransitionProgram:
    """Test family_transition_year effect on program net worth."""

    @pytest.fixture
    def sample_program(self):
        """A sample US program for testing."""
        return {
            "id": 999,
            "program_name": "MS CS Test",
            "university_name": "Test University",
            "field": "CS/SWE",
            "tuition_usd": 50,
            "y1_salary_usd": 180,
            "y5_salary_usd": 250,
            "y10_salary_usd": 350,
            "funding_tier": "tier2_elite_us",
            "duration_years": 2,
            "primary_market": "USA (Seattle/National)",
            "country": "USA",
        }

    def test_later_marriage_higher_masters_networth(self, sample_program):
        """Later family transition = higher masters net worth."""
        early = calculate_program_networth(sample_program, family_transition_year=3)
        late = calculate_program_networth(sample_program, family_transition_year=9)
        assert early["masters_networth_k"] < late["masters_networth_k"], (
            f"Early (${early['masters_networth_k']:.0f}K) should < "
            f"late (${late['masters_networth_k']:.0f}K)"
        )

    def test_year_13_highest_networth(self, sample_program):
        """Never marry (year 13) should give highest masters net worth."""
        never = calculate_program_networth(sample_program, family_transition_year=13)
        default = calculate_program_networth(sample_program, family_transition_year=5)
        assert never["masters_networth_k"] > default["masters_networth_k"], (
            f"Never (${never['masters_networth_k']:.0f}K) should > "
            f"default (${default['masters_networth_k']:.0f}K)"
        )

    def test_baseline_also_changes(self, sample_program):
        """Baseline networth embedded in program result should change with family_year."""
        early = calculate_program_networth(sample_program, family_transition_year=3)
        late = calculate_program_networth(sample_program, family_transition_year=9)
        assert early["baseline_networth_k"] < late["baseline_networth_k"], (
            f"Baseline in early (${early['baseline_networth_k']:.0f}K) should < "
            f"late (${late['baseline_networth_k']:.0f}K)"
        )

    def test_household_labels_match_transition(self, sample_program):
        """Yearly breakdown household labels should reflect the transition year."""
        result = calculate_program_networth(sample_program, family_transition_year=8)
        for yr in result["yearly_breakdown"]:
            if yr.get("phase") == "study":
                # Study years don't have a household key — they use student profile
                assert "household" not in yr, (
                    f"Year {yr['calendar_year']} (study): should not have household key"
                )
            else:
                expected = "single" if yr["calendar_year"] < 8 else "family"
                assert yr["household"] == expected, (
                    f"Year {yr['calendar_year']} (work): expected {expected}, got {yr['household']}"
                )

    def test_default_matches_year_5(self, sample_program):
        """Default (no family_transition_year) should match explicit year 5."""
        default = calculate_program_networth(sample_program)
        explicit = calculate_program_networth(sample_program, family_transition_year=5)
        assert default["masters_networth_k"] == explicit["masters_networth_k"]
        assert default["net_benefit_k"] == explicit["net_benefit_k"]

    def test_still_12_yearly_entries(self, sample_program):
        """Should still have 12 yearly entries for any family_year."""
        for fy in [1, 5, 13]:
            result = calculate_program_networth(
                sample_program, family_transition_year=fy
            )
            assert len(result["yearly_breakdown"]) == 12, (
                f"family_year={fy}: expected 12 entries, got {len(result['yearly_breakdown'])}"
            )


class TestFamilyTransitionAllPrograms:
    """Test family_transition_year in calculate_all_programs."""

    def test_assumptions_reflect_family_year(self):
        """Assumptions dict should contain the actual family_transition_year."""
        result = calculate_all_programs(family_transition_year=9)
        assert result["assumptions"]["family_transition_year"] == 9

    def test_assumptions_default_year_5(self):
        """Default assumptions should show family_transition_year=5."""
        result = calculate_all_programs()
        assert result["assumptions"]["family_transition_year"] == 5

    def test_year_13_more_positive_programs(self):
        """Never marry should result in more programs with positive benefit."""
        default = calculate_all_programs(family_transition_year=5)
        never = calculate_all_programs(family_transition_year=13)
        default_pos = default["summary"]["programs_with_positive_benefit"]
        never_pos = never["summary"]["programs_with_positive_benefit"]
        assert never_pos >= default_pos, (
            f"Never marry ({never_pos} positive) should have >= "
            f"default ({default_pos} positive)"
        )

    def test_returns_all_265_programs(self):
        """Should still return 265 programs regardless of family_year."""
        for fy in [1, 7, 13]:
            result = calculate_all_programs(family_transition_year=fy)
            assert len(result["programs"]) == 265, (
                f"family_year={fy}: expected 265 programs, got {len(result['programs'])}"
            )
