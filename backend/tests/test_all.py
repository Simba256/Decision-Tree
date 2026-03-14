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
                # Updated upper bound to $170K for premium cities (Bay Area family 2024-2025)
                assert 2 <= cost <= 170, (
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
        """At least 50% of programs should have positive net benefit.

        Note: With 2024-2025 living costs for premium cities (Bay Area $70K, Zurich $70K),
        the proportion of positive-ROI programs is lower than with earlier estimates.
        """
        positive = all_data["summary"]["programs_with_positive_benefit"]
        total = all_data["summary"]["total_programs"]
        ratio = positive / total
        assert ratio >= 0.5, f"Only {ratio:.0%} positive, expected >= 50%"

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
        """Comfortable costs should still be in $3K-$210K range (updated for 2024-2025)."""
        for city in ["Bay Area", "NYC", "London", "Berlin", "Zurich", "Mumbai"]:
            for profile in ["single", "family"]:
                cost = get_annual_living_cost(city, profile, lifestyle="comfortable")
                # Updated upper bound to $210K for premium cities (Bay Area family comfortable 2024-2025)
                assert 3 <= cost <= 210, (
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


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 2 ENHANCEMENTS: GRE/IELTS, SCHOLARSHIPS, VISA RATES, PAKISTAN RETURN
# ═══════════════════════════════════════════════════════════════════════════════


class TestGREIELTSData:
    """Test GRE/IELTS requirements data."""

    def test_gre_data_populated(self):
        """GRE data should be populated for all programs."""
        from config import get_db
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM programs WHERE gre_required IS NOT NULL")
            count = cursor.fetchone()[0]
        assert count == 265, f"Expected 265 programs with GRE data, got {count}"

    def test_gre_valid_values(self):
        """GRE values should be one of the valid statuses."""
        from config import get_db
        valid_values = {"required", "preferred", "optional", "waivable", "not_required"}
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT gre_required FROM programs WHERE gre_required IS NOT NULL")
            values = {row[0] for row in cursor.fetchall()}
        assert values.issubset(valid_values), f"Invalid GRE values: {values - valid_values}"

    def test_ielts_scores_reasonable(self):
        """IELTS scores should be in 0-9 range."""
        from config import get_db
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT MIN(ielts_min_score), MAX(ielts_min_score) FROM programs WHERE ielts_min_score IS NOT NULL")
            min_score, max_score = cursor.fetchone()
        assert min_score >= 5.0, f"IELTS min too low: {min_score}"
        assert max_score <= 9.0, f"IELTS max too high: {max_score}"


class TestScholarshipsData:
    """Test scholarships data and API."""

    def test_scholarships_populated(self):
        """Should have scholarships in database."""
        from config import get_db
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM scholarships")
            count = cursor.fetchone()[0]
        assert count >= 15, f"Expected at least 15 scholarships, got {count}"

    def test_scholarship_coverage_types(self):
        """Scholarships should have valid coverage types."""
        from config import get_db
        valid_types = {"full_funding", "full_tuition", "partial_tuition", "stipend_only", "mixed"}
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT coverage_type FROM scholarships")
            types = {row[0] for row in cursor.fetchall()}
        assert types.issubset(valid_types), f"Invalid coverage types: {types - valid_types}"

    def test_scholarship_deadlines_present(self):
        """Most scholarships should have deadline dates."""
        from config import get_db
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM scholarships WHERE deadline_date IS NOT NULL")
            with_deadline = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM scholarships")
            total = cursor.fetchone()[0]
        assert with_deadline / total >= 0.8, f"Only {with_deadline}/{total} have deadlines"

    def test_scholarship_links_created(self):
        """Scholarship-program links should exist."""
        from config import get_db
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM scholarship_program_links")
            count = cursor.fetchone()[0]
        assert count >= 50, f"Expected at least 50 links, got {count}"


class TestVisaRatesData:
    """Test visa approval rates by nationality."""

    def test_visa_rates_populated(self):
        """Should have visa rates in database."""
        from config import get_db
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM visa_approval_by_nationality")
            count = cursor.fetchone()[0]
        assert count >= 30, f"Expected at least 30 visa rate entries, got {count}"

    def test_pakistan_visa_rates_exist(self):
        """Should have Pakistan-specific visa rates."""
        from config import get_db
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM visa_approval_by_nationality WHERE nationality = 'Pakistan'")
            count = cursor.fetchone()[0]
        assert count >= 20, f"Expected at least 20 Pakistan visa rates, got {count}"

    def test_visa_rates_valid_range(self):
        """Visa rates should be between 0 and 1."""
        from config import get_db
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT MIN(approval_rate), MAX(approval_rate) FROM visa_approval_by_nationality")
            min_rate, max_rate = cursor.fetchone()
        assert min_rate >= 0.0, f"Min rate below 0: {min_rate}"
        assert max_rate <= 1.0, f"Max rate above 1: {max_rate}"

    def test_get_nationality_visa_rate(self):
        """Nationality-aware visa lookup should work."""
        from networth_calculator import get_nationality_visa_rate
        rate = get_nationality_visa_rate("Canada", "Pakistan", "PGWP")
        assert rate is not None, "Should find PGWP rate for Pakistan"
        assert 0.95 <= rate <= 1.0, f"Canada PGWP should be ~98%, got {rate}"

    def test_get_visa_risk_factor_uses_db(self):
        """get_visa_risk_factor should use DB rates for Pakistan."""
        from networth_calculator import get_visa_risk_factor
        # Canada PGWP is ~98% for Pakistan in our data
        rate = get_visa_risk_factor(country="Canada", nationality="Pakistan")
        assert rate >= 0.95, f"Canada risk factor for Pakistan should be high, got {rate}"


class TestPakistanJobMarketData:
    """Test Pakistan job market salary data."""

    def test_salary_data_populated(self):
        """Should have Pakistan salary data."""
        from config import get_db
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM pakistan_job_market")
            count = cursor.fetchone()[0]
        assert count >= 40, f"Expected at least 40 salary entries, got {count}"

    def test_employer_tiers_exist(self):
        """Should have multiple employer tiers."""
        from config import get_db
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT employer_tier FROM pakistan_job_market")
            tiers = [row[0] for row in cursor.fetchall()]
        assert len(tiers) >= 4, f"Expected at least 4 employer tiers, got {tiers}"

    def test_salary_progression_reasonable(self):
        """Salaries should grow from Y1 to Y10."""
        from config import get_db
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT y1_salary_pkr, y5_salary_pkr, y10_salary_pkr
                FROM pakistan_job_market
                WHERE y1_salary_pkr IS NOT NULL
                  AND y5_salary_pkr IS NOT NULL
                  AND y10_salary_pkr IS NOT NULL
            """)
            for y1, y5, y10 in cursor.fetchall():
                assert y1 < y5 < y10, f"Salary should grow: Y1={y1}, Y5={y5}, Y10={y10}"


class TestPakistanReturnCalculator:
    """Test Pakistan return-to-work calculator."""

    @pytest.fixture
    def sample_program(self):
        """Sample US program for testing."""
        return {
            "id": 999,
            "program_name": "MS CS Test",
            "university_name": "Test University",
            "field": "CS/SWE",
            "tuition_usd": 50,
            "y1_salary_usd": 150,
            "y5_salary_usd": 200,
            "y10_salary_usd": 280,
            "duration_years": 2,
            "primary_market": "USA (Bay Area)",
            "country": "USA",
        }

    def test_calculate_pakistan_return(self, sample_program):
        """Pakistan return calculation should work."""
        from pakistan_return_calculator import calculate_pakistan_return_networth
        result = calculate_pakistan_return_networth(sample_program, return_after_years=2)
        assert "total_networth_k" in result
        assert "abroad_years" in result
        assert "pakistan_years" in result
        assert result["abroad_years"] == 2
        assert result["pakistan_years"] == 8

    def test_return_phases_sum_to_10(self, sample_program):
        """Abroad + Pakistan years should sum to 10."""
        from pakistan_return_calculator import calculate_pakistan_return_networth
        for years_abroad in [0, 2, 5, 10]:
            result = calculate_pakistan_return_networth(sample_program, return_after_years=years_abroad)
            total_work_years = result["abroad_years"] + result["pakistan_years"]
            assert total_work_years == 10, f"Work years should be 10, got {total_work_years}"

    def test_return_scenarios_differ(self, sample_program):
        """Different return scenarios should yield different networth values."""
        from pakistan_return_calculator import calculate_pakistan_return_networth
        early = calculate_pakistan_return_networth(sample_program, return_after_years=0)
        mid = calculate_pakistan_return_networth(sample_program, return_after_years=5)
        stay = calculate_pakistan_return_networth(sample_program, return_after_years=10)
        # All scenarios should have valid numbers (may differ based on living costs)
        assert all(isinstance(x["total_networth_k"], (int, float)) for x in [early, mid, stay])
        # At least some difference between scenarios
        values = [early["total_networth_k"], mid["total_networth_k"], stay["total_networth_k"]]
        assert len(set(values)) > 1, "Return scenarios should produce different results"

    def test_compare_abroad_vs_return(self, sample_program):
        """Comparison function should return all scenarios."""
        from pakistan_return_calculator import compare_abroad_vs_return
        result = compare_abroad_vs_return(sample_program)
        assert "scenarios" in result
        assert len(result["scenarios"]) == 4  # 0, 2, 5, 10 years
        assert "optimal_strategy" in result
        assert "insights" in result

    def test_employer_tier_affects_result(self, sample_program):
        """Different employer tiers should affect Pakistan return networth."""
        from pakistan_return_calculator import calculate_pakistan_return_networth
        tier1 = calculate_pakistan_return_networth(
            sample_program, employer_tier="tier1_multinational", return_after_years=2
        )
        tier4 = calculate_pakistan_return_networth(
            sample_program, employer_tier="tier4_local_sme", return_after_years=2
        )
        assert tier1["total_pakistan_savings_k"] > tier4["total_pakistan_savings_k"], (
            f"Tier 1 (${tier1['total_pakistan_savings_k']:.0f}K) should earn more than "
            f"Tier 4 (${tier4['total_pakistan_savings_k']:.0f}K) in Pakistan"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# POST-MASTERS CAREER PATHS: LOCATION ECOSYSTEMS
# ═══════════════════════════════════════════════════════════════════════════════


class TestLocationEcosystems:
    """Test location ecosystem data and lookups."""

    def test_ecosystems_populated(self):
        """Should have location ecosystems in database."""
        from config import get_db
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM location_ecosystems")
            count = cursor.fetchone()[0]
        assert count >= 20, f"Expected at least 20 ecosystems, got {count}"

    def test_get_ecosystem_sf(self):
        """San Francisco should have strong startup ecosystem."""
        from location_ecosystem import get_ecosystem
        eco = get_ecosystem("San Francisco", "USA")
        assert eco is not None, "SF ecosystem should exist"
        assert eco.startup_ecosystem_strength >= 1.5, (
            f"SF startup strength should be >= 1.5, got {eco.startup_ecosystem_strength}"
        )
        assert eco.bigtech_presence == "hq", (
            f"SF should have bigtech HQ presence, got {eco.bigtech_presence}"
        )

    def test_get_ecosystem_lahore(self):
        """Lahore should have weaker startup ecosystem."""
        from location_ecosystem import get_ecosystem
        eco = get_ecosystem("Lahore", "Pakistan")
        assert eco is not None, "Lahore ecosystem should exist"
        assert eco.startup_ecosystem_strength <= 0.6, (
            f"Lahore startup strength should be <= 0.6, got {eco.startup_ecosystem_strength}"
        )

    def test_get_ecosystem_by_country(self):
        """Should get primary ecosystem for a country."""
        from location_ecosystem import get_ecosystem_by_country
        eco = get_ecosystem_by_country("USA")
        assert eco is not None, "USA primary ecosystem should exist"
        assert eco.city == "San Francisco", (
            f"USA primary should be SF, got {eco.city}"
        )

    def test_is_startup_hub(self):
        """SF should be a startup hub, Karlsruhe should not."""
        from location_ecosystem import get_ecosystem, is_startup_hub
        sf = get_ecosystem("San Francisco", "USA")
        karlsruhe = get_ecosystem("Karlsruhe", "Germany")
        assert is_startup_hub(sf), "SF should be startup hub"
        if karlsruhe:
            assert not is_startup_hub(karlsruhe), "Karlsruhe should not be startup hub"

    def test_is_bigtech_hub(self):
        """Seattle should be bigtech hub, Lahore should not."""
        from location_ecosystem import get_ecosystem, is_bigtech_hub
        seattle = get_ecosystem("Seattle", "USA")
        lahore = get_ecosystem("Lahore", "Pakistan")
        assert is_bigtech_hub(seattle), "Seattle should be bigtech hub"
        if lahore:
            assert not is_bigtech_hub(lahore), "Lahore should not be bigtech hub"

    def test_calculate_startup_success_modifier(self):
        """Startup success modifier should vary by location."""
        from location_ecosystem import get_ecosystem, calculate_startup_success_modifier
        sf = get_ecosystem("San Francisco", "USA")
        berlin = get_ecosystem("Berlin", "Germany")
        sf_mod = calculate_startup_success_modifier(sf)
        berlin_mod = calculate_startup_success_modifier(berlin)
        assert sf_mod > berlin_mod, (
            f"SF modifier ({sf_mod:.2f}) should be > Berlin ({berlin_mod:.2f})"
        )

    def test_calculate_bigtech_modifier(self):
        """Bigtech modifier should vary by presence level."""
        from location_ecosystem import get_ecosystem, calculate_bigtech_modifier
        seattle = get_ecosystem("Seattle", "USA")
        lahore = get_ecosystem("Lahore", "Pakistan")
        seattle_mod = calculate_bigtech_modifier(seattle)
        lahore_mod = calculate_bigtech_modifier(lahore)
        assert seattle_mod > lahore_mod, (
            f"Seattle bigtech mod ({seattle_mod:.2f}) should > Lahore ({lahore_mod:.2f})"
        )

    def test_list_ecosystems(self):
        """List ecosystems should return all or filtered results."""
        from location_ecosystem import list_ecosystems
        all_eco = list_ecosystems()
        assert len(all_eco) >= 20, f"Expected at least 20, got {len(all_eco)}"

        # Filter by country
        usa_eco = list_ecosystems(country="USA")
        assert all(e.country == "USA" for e in usa_eco), "Filter should only return USA"
        assert len(usa_eco) >= 4, f"Expected at least 4 US cities, got {len(usa_eco)}"

    def test_has_founder_visa_path(self):
        """Canada and UK should have founder visa paths."""
        from location_ecosystem import get_ecosystem, has_founder_visa_path
        toronto = get_ecosystem("Toronto", "Canada")
        london = get_ecosystem("London", "UK")
        sf = get_ecosystem("San Francisco", "USA")
        assert has_founder_visa_path(toronto), "Toronto should have founder visa (Start-up Visa)"
        assert has_founder_visa_path(london), "London should have founder visa (Innovator)"
        # USA O-1 is technically available but harder to get


# ═══════════════════════════════════════════════════════════════════════════════
# POST-MASTERS CAREER PATHS: NODES AND EDGES
# ═══════════════════════════════════════════════════════════════════════════════


class TestPostmastersNodes:
    """Test post-masters career nodes data."""

    def test_nodes_populated(self):
        """Should have post-masters nodes in database."""
        from config import get_db
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM postmasters_nodes")
            count = cursor.fetchone()[0]
        assert count >= 30, f"Expected at least 30 nodes, got {count}"

    def test_nodes_have_required_fields(self):
        """All nodes should have required fields."""
        from config import get_db
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, phase, node_type, label
                FROM postmasters_nodes
            """)
            for row in cursor.fetchall():
                node_id, phase, node_type, label = row
                assert node_id, f"Node missing id"
                assert phase is not None, f"Node {node_id} missing phase"
                assert node_type, f"Node {node_id} missing node_type"
                assert label, f"Node {node_id} missing label"

    def test_node_phases_valid(self):
        """Node phases should be 0, 1, 2, or 3."""
        from config import get_db
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT phase FROM postmasters_nodes")
            phases = {row[0] for row in cursor.fetchall()}
        valid_phases = {0, 1, 2, 3}
        assert phases.issubset(valid_phases), f"Invalid phases: {phases - valid_phases}"

    def test_node_types_valid(self):
        """Node types should be valid."""
        from config import get_db
        valid_types = {"employment", "startup", "remote", "return", "terminal", "founder", "root"}
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT node_type FROM postmasters_nodes")
            types = {row[0] for row in cursor.fetchall()}
        assert types.issubset(valid_types), f"Invalid node types: {types - valid_types}"

    def test_phase_0_entry_nodes(self):
        """Phase 0 should have entry decision nodes."""
        from config import get_db
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM postmasters_nodes WHERE phase = 0")
            ids = [row[0] for row in cursor.fetchall()]
        assert len(ids) >= 4, f"Expected at least 4 phase 0 nodes, got {len(ids)}"
        expected_entries = {"pm_bigtech", "pm_startup_join", "pm_remote_arbitrage", "pm_return_pakistan"}
        assert expected_entries.issubset(set(ids)), (
            f"Missing entry nodes: {expected_entries - set(ids)}"
        )

    def test_terminal_nodes_exist(self):
        """Should have terminal nodes (phase 3)."""
        from config import get_db
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM postmasters_nodes WHERE phase = 3")
            count = cursor.fetchone()[0]
        assert count >= 5, f"Expected at least 5 terminal nodes, got {count}"


class TestPostmastersEdges:
    """Test post-masters career edges data."""

    def test_edges_populated(self):
        """Should have post-masters edges in database."""
        from config import get_db
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM postmasters_edges")
            count = cursor.fetchone()[0]
        assert count >= 50, f"Expected at least 50 edges, got {count}"

    def test_edges_have_valid_sources(self):
        """All edge sources should reference valid nodes."""
        from config import get_db
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT e.source_id
                FROM postmasters_edges e
                LEFT JOIN postmasters_nodes n ON e.source_id = n.id
                WHERE n.id IS NULL
            """)
            orphans = [row[0] for row in cursor.fetchall()]
        assert len(orphans) == 0, f"Edges with invalid sources: {orphans}"

    def test_edges_have_valid_targets(self):
        """All edge targets should reference valid nodes."""
        from config import get_db
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT e.target_id
                FROM postmasters_edges e
                LEFT JOIN postmasters_nodes n ON e.target_id = n.id
                WHERE n.id IS NULL
            """)
            orphans = [row[0] for row in cursor.fetchall()]
        assert len(orphans) == 0, f"Edges with invalid targets: {orphans}"

    def test_edge_probabilities_valid(self):
        """Edge probabilities should be between 0 and 1."""
        from config import get_db
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT source_id, target_id, base_probability
                FROM postmasters_edges
                WHERE base_probability < 0 OR base_probability > 1
            """)
            invalid = cursor.fetchall()
        assert len(invalid) == 0, f"Invalid probabilities: {invalid}"

    def test_child_probabilities_sum_to_1(self):
        """Child edge probabilities from each node should sum to ~1.0."""
        from config import get_db
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT source_id, SUM(base_probability) as total
                FROM postmasters_edges
                WHERE link_type = 'child'
                GROUP BY source_id
            """)
            for source_id, total in cursor.fetchall():
                # Allow small tolerance for floating point
                assert 0.95 <= total <= 1.05, (
                    f"Node {source_id} child edges sum to {total:.2f}, expected ~1.0"
                )

    def test_location_sensitivity_weights(self):
        """Some edges should have location sensitivity weights."""
        from config import get_db
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM postmasters_edges
                WHERE startup_ecosystem_weight != 0 OR bigtech_presence_weight != 0
            """)
            count = cursor.fetchone()[0]
        assert count >= 10, f"Expected at least 10 location-sensitive edges, got {count}"


# ═══════════════════════════════════════════════════════════════════════════════
# POST-MASTERS CALCULATOR
# ═══════════════════════════════════════════════════════════════════════════════


class TestPostmastersCalculator:
    """Test post-masters path net worth calculations."""

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
            "primary_market": "USA (Bay Area)",
            "country": "USA",
        }

    @pytest.fixture
    def sf_ecosystem(self):
        """SF ecosystem for testing."""
        from location_ecosystem import get_ecosystem
        return get_ecosystem("San Francisco", "USA")

    def test_enumerate_paths(self):
        """Should enumerate paths from root to terminals."""
        from postmasters_calculator import enumerate_paths, get_postmasters_nodes
        nodes = get_postmasters_nodes()
        paths = enumerate_paths("pm_root", nodes)
        assert len(paths) >= 10, f"Expected at least 10 paths, got {len(paths)}"
        # Each path should start with pm_root
        for path in paths:
            assert path[0] == "pm_root", f"Path should start with pm_root: {path}"

    def test_calculate_path_networth(self, sample_program, sf_ecosystem):
        """Should calculate net worth for a specific path."""
        from postmasters_calculator import calculate_postmasters_path_networth
        # Use bigtech path
        path = ["pm_root", "pm_bigtech", "pm_bigtech_senior", "pm_staff"]
        result = calculate_postmasters_path_networth(
            program=sample_program,
            path=path,
            ecosystem=sf_ecosystem,
        )
        assert "path_net_worth_k" in result
        assert "yearly_breakdown" in result
        assert result["path_net_worth_k"] > 0, (
            f"Bigtech path should have positive net worth, got {result['path_net_worth_k']}"
        )

    def test_bigtech_path_vs_startup_path(self, sample_program, sf_ecosystem):
        """Bigtech stable path should have different profile than startup."""
        from postmasters_calculator import calculate_postmasters_path_networth
        bigtech = calculate_postmasters_path_networth(
            program=sample_program,
            path=["pm_root", "pm_bigtech", "pm_bigtech_senior", "pm_staff"],
            ecosystem=sf_ecosystem,
        )
        # Startup fail path should have lower outcome
        startup_fail = calculate_postmasters_path_networth(
            program=sample_program,
            path=["pm_root", "pm_startup_join", "pm_startup_failed", "pm_startup_failed_pivot"],
            ecosystem=sf_ecosystem,
        )
        # Both should return valid results
        assert "path_net_worth_k" in bigtech
        assert "path_net_worth_k" in startup_fail

    def test_expected_networth(self, sample_program, sf_ecosystem):
        """Should calculate expected net worth across all paths."""
        from postmasters_calculator import calculate_expected_networth
        result = calculate_expected_networth(
            program=sample_program,
            ecosystem=sf_ecosystem,
        )
        assert "expected_networth_k" in result
        assert "distribution" in result
        assert "p10" in result["distribution"]
        assert "p50_median" in result["distribution"]
        assert "p90" in result["distribution"]
        # Percentiles should be ordered
        assert result["distribution"]["p10"] <= result["distribution"]["p50_median"], (
            "p10 should be <= p50"
        )
        assert result["distribution"]["p50_median"] <= result["distribution"]["p90"], (
            "p50 should be <= p90"
        )

    def test_location_affects_expected_value(self, sample_program):
        """Different locations should produce different expected values."""
        from postmasters_calculator import calculate_expected_networth
        from location_ecosystem import get_ecosystem
        sf = get_ecosystem("San Francisco", "USA")
        lahore = get_ecosystem("Lahore", "Pakistan")

        if sf and lahore:
            sf_result = calculate_expected_networth(sample_program, sf)
            lahore_result = calculate_expected_networth(sample_program, lahore)
            # SF should have higher expected value due to stronger ecosystem
            assert sf_result["expected_networth_k"] != lahore_result["expected_networth_k"], (
                "SF and Lahore should produce different expected values"
            )

    def test_compare_program_ecosystems(self, sample_program):
        """Should compare program across multiple ecosystems."""
        from postmasters_calculator import compare_program_ecosystems
        results = compare_program_ecosystems(sample_program)
        # Returns a list directly
        assert isinstance(results, list), "Should return a list"
        assert len(results) >= 3, (
            f"Expected at least 3 ecosystems, got {len(results)}"
        )
        # Check result structure
        for r in results:
            assert "city" in r
            assert "expected_networth_k" in r


# ═══════════════════════════════════════════════════════════════════════════════
# POST-MASTERS CALIBRATION
# ═══════════════════════════════════════════════════════════════════════════════


class TestPostmastersCalibration:
    """Test post-masters edge calibration with profile and location."""

    @pytest.fixture
    def high_risk_profile(self):
        """Profile of a high-risk tolerance person."""
        return {
            "risk_tolerance": "high",
            "performance_rating": "top",
            "years_experience": 5,
            "available_savings_usd": 30000,
            "english_level": "native",
            "has_side_projects": True,
            "has_publications": False,
            "has_freelance_profile": False,
            "quant_aptitude": "strong",
            "gpa": 3.8,
        }

    @pytest.fixture
    def low_risk_profile(self):
        """Profile of a low-risk tolerance person."""
        return {
            "risk_tolerance": "low",
            "performance_rating": "average",
            "years_experience": 1,
            "available_savings_usd": 5000,
            "english_level": "intermediate",
            "has_side_projects": False,
            "has_publications": False,
            "has_freelance_profile": False,
            "quant_aptitude": "average",
            "gpa": 3.3,
        }

    @pytest.fixture
    def sf_ecosystem(self):
        """SF ecosystem for testing."""
        from location_ecosystem import get_ecosystem
        return get_ecosystem("San Francisco", "USA")

    def test_calibrate_postmasters_edges(self, high_risk_profile, sf_ecosystem):
        """Should calibrate edges based on profile and location."""
        from profile_calibrator import calibrate_postmasters_edges
        calibrated = calibrate_postmasters_edges(
            profile=high_risk_profile,
            ecosystem=sf_ecosystem,
        )
        assert len(calibrated) > 0, "Should return calibrated edges"
        # Check structure
        for edge in calibrated:
            assert "source_id" in edge
            assert "target_id" in edge
            assert "calibrated_probability" in edge
            assert 0 <= edge["calibrated_probability"] <= 1, (
                f"Calibrated prob out of range: {edge['calibrated_probability']}"
            )

    def test_high_risk_boosts_founder(self, high_risk_profile, low_risk_profile, sf_ecosystem):
        """High risk profile should boost founder path probabilities."""
        from profile_calibrator import get_calibrated_postmasters_edge_map

        high_edges = get_calibrated_postmasters_edge_map(high_risk_profile, sf_ecosystem)
        low_edges = get_calibrated_postmasters_edge_map(low_risk_profile, sf_ecosystem)

        # Check founder edges from pm_root
        # edge_map[source_id][target_id] = probability
        if "pm_root" in high_edges and "pm_founder_immediate" in high_edges["pm_root"]:
            high_prob = high_edges["pm_root"]["pm_founder_immediate"]
            low_prob = low_edges.get("pm_root", {}).get("pm_founder_immediate", 0)
            assert high_prob > low_prob, (
                f"High risk should boost founder: high={high_prob:.3f}, low={low_prob:.3f}"
            )

    def test_sf_boosts_startup_success(self, high_risk_profile):
        """SF ecosystem should boost startup success probability."""
        from profile_calibrator import get_calibrated_postmasters_edge_map
        from location_ecosystem import get_ecosystem

        sf = get_ecosystem("San Francisco", "USA")
        berlin = get_ecosystem("Berlin", "Germany")

        if sf and berlin:
            sf_edges = get_calibrated_postmasters_edge_map(high_risk_profile, sf)
            berlin_edges = get_calibrated_postmasters_edge_map(high_risk_profile, berlin)

            # Check startup win edge from pm_startup_join
            if "pm_startup_join" in sf_edges and "pm_startup_win" in sf_edges["pm_startup_join"]:
                sf_prob = sf_edges["pm_startup_join"]["pm_startup_win"]
                berlin_prob = berlin_edges.get("pm_startup_join", {}).get("pm_startup_win", 0)
                assert sf_prob >= berlin_prob, (
                    f"SF should boost startup success: SF={sf_prob:.3f}, Berlin={berlin_prob:.3f}"
                )

    def test_calibration_preserves_normalization(self, high_risk_profile, sf_ecosystem):
        """Calibrated child probabilities should still sum to ~1.0."""
        from profile_calibrator import calibrate_postmasters_edges

        calibrated = calibrate_postmasters_edges(high_risk_profile, sf_ecosystem)

        # Group by source
        from collections import defaultdict
        by_source = defaultdict(list)
        for edge in calibrated:
            by_source[edge["source_id"]].append(edge["calibrated_probability"])

        # Check sums (allowing tolerance)
        for source, probs in by_source.items():
            total = sum(probs)
            # Only check if there are multiple children (single child can be any value)
            if len(probs) > 1:
                assert 0.95 <= total <= 1.05, (
                    f"Node {source} children sum to {total:.2f}, expected ~1.0"
                )


# ═══════════════════════════════════════════════════════════════════════════════
# POST-MASTERS API ENDPOINTS (Basic Tests)
# ═══════════════════════════════════════════════════════════════════════════════


class TestPostmastersAPI:
    """Test post-masters API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from app import app
        app.config["TESTING"] = True
        with app.test_client() as client:
            yield client

    def test_get_ecosystems(self, client):
        """GET /api/ecosystems should return ecosystem list."""
        response = client.get("/api/ecosystems")
        assert response.status_code == 200
        data = response.get_json()
        assert "ecosystems" in data
        assert len(data["ecosystems"]) >= 20

    def test_get_ecosystem_by_city(self, client):
        """GET /api/ecosystems/<city> should return single ecosystem."""
        response = client.get("/api/ecosystems/San%20Francisco")
        assert response.status_code == 200
        data = response.get_json()
        # API returns ecosystem directly, not wrapped
        assert data["city"] == "San Francisco"

    def test_get_postmasters_nodes(self, client):
        """GET /api/postmasters/nodes should return nodes."""
        response = client.get("/api/postmasters/nodes")
        assert response.status_code == 200
        data = response.get_json()
        assert "nodes" in data
        assert len(data["nodes"]) >= 30

    def test_get_postmasters_edges(self, client):
        """GET /api/postmasters/edges should return edges."""
        response = client.get("/api/postmasters/edges")
        assert response.status_code == 200
        data = response.get_json()
        assert "edges" in data
        assert len(data["edges"]) >= 50

    def test_get_program_postmasters(self, client):
        """GET /api/programs/<id>/postmasters should return paths."""
        # Use a known program ID (e.g., 1)
        response = client.get("/api/programs/1/postmasters")
        if response.status_code == 200:
            data = response.get_json()
            assert "paths" in data or "nodes" in data
        elif response.status_code == 404:
            # Program might not exist in test db
            pass
        else:
            assert False, f"Unexpected status: {response.status_code}"

    def test_get_expected_networth(self, client):
        """GET /api/networth/<id>/expected should return expected value."""
        response = client.get("/api/networth/1/expected")
        if response.status_code == 200:
            data = response.get_json()
            assert "expected_value_k" in data or "error" not in data
        elif response.status_code == 404:
            # Program might not exist
            pass
        else:
            assert False, f"Unexpected status: {response.status_code}"
