"""Unit tests for the pure business logic ported from the desktop baselines."""

from __future__ import annotations

import pytest

from aceest import services
from aceest.errors import ValidationError
from aceest.programs import PROGRAMS, get_program, list_programs


class TestProgramCatalogue:
    def test_catalogue_exposes_every_baseline_program(self):
        assert set(PROGRAMS) == {"FL3", "FL5", "MG", "BG"}
        assert len(list_programs()) == 4

    @pytest.mark.parametrize(
        ("code", "factor"),
        [("FL3", 22), ("FL5", 24), ("MG", 35), ("BG", 26)],
    )
    def test_calorie_factors_match_baseline(self, code, factor):
        assert PROGRAMS[code]["factor"] == factor

    def test_lookup_is_case_insensitive_and_trimmed(self):
        assert get_program(" mg ")["code"] == "MG"

    def test_unknown_program_returns_none(self):
        assert get_program("ZZ") is None
        assert get_program(None) is None


class TestCalorieCalculation:
    @pytest.mark.parametrize(
        ("weight", "program", "expected"),
        [
            (80, "MG", 2800),
            (70, "FL3", 1540),
            (70, "FL5", 1680),
            (60, "BG", 1560),
        ],
    )
    def test_weight_times_program_factor(self, weight, program, expected):
        assert services.calculate_calories(weight, program) == expected

    def test_result_is_truncated_to_a_whole_number(self):
        # 72.5 kg x 22 = 1595.0 -> int() must not round up
        assert services.calculate_calories(72.53, "FL3") == 1595

    def test_rejects_unknown_program(self):
        with pytest.raises(ValidationError) as excinfo:
            services.calculate_calories(80, "CROSSFIT")
        assert excinfo.value.field == "program"

    @pytest.mark.parametrize("weight", [0, -5, 24.9, 300.1, "heavy", None, True])
    def test_rejects_out_of_range_or_non_numeric_weight(self, weight):
        with pytest.raises(ValidationError):
            services.calculate_calories(weight, "MG")


class TestBmi:
    def test_bmi_formula(self):
        assert services.calculate_bmi(80, 180) == 24.7

    @pytest.mark.parametrize(
        ("bmi", "category"),
        [
            (17.0, "Underweight"),
            (18.5, "Normal"),
            (24.9, "Normal"),
            (25.0, "Overweight"),
            (29.9, "Overweight"),
            (30.0, "Obese"),
        ],
    )
    def test_classification_boundaries(self, bmi, category):
        assert services.classify_bmi(bmi)["category"] == category

    def test_report_bundles_value_category_and_risk(self):
        report = services.bmi_report(95, 170)
        assert report["bmi"] == 32.9
        assert report["category"] == "Obese"
        assert "risk" in report

    def test_rejects_impossible_height(self):
        with pytest.raises(ValidationError) as excinfo:
            services.calculate_bmi(80, 10)
        assert excinfo.value.field == "height_cm"


class TestValidators:
    def test_name_is_normalised(self):
        assert services.validate_name("  Ravi   Kumar ") == "Ravi Kumar"

    @pytest.mark.parametrize("name", ["", "A", "1Ravi", "<script>x</script>", 42])
    def test_invalid_names_are_rejected(self, name):
        with pytest.raises(ValidationError):
            services.validate_name(name)

    @pytest.mark.parametrize("age", [9, 101, 30.5, "thirty"])
    def test_invalid_ages_are_rejected(self, age):
        with pytest.raises(ValidationError):
            services.validate_age(age)

    @pytest.mark.parametrize(("raw", "expected"), [("W1", "W1"), ("7", "W7"), (12, "W12")])
    def test_week_normalisation(self, raw, expected):
        assert services.validate_week(raw) == expected

    @pytest.mark.parametrize("week", ["week one", "W0", "W999", None])
    def test_invalid_weeks_are_rejected(self, week):
        with pytest.raises(ValidationError):
            services.validate_week(week)

    @pytest.mark.parametrize("adherence", [-1, 101, "high"])
    def test_invalid_adherence_is_rejected(self, adherence):
        with pytest.raises(ValidationError):
            services.validate_adherence(adherence)

    def test_workout_type_is_case_insensitive(self):
        assert services.validate_workout_type("cardio") == "Cardio"

    def test_unknown_workout_type_is_rejected(self):
        with pytest.raises(ValidationError):
            services.validate_workout_type("yoga")

    def test_blank_date_defaults_to_today(self):
        from datetime import date

        assert services.validate_iso_date(None) == date.today().isoformat()

    @pytest.mark.parametrize("value", ["2026-13-01", "01-01-2026", 20260101])
    def test_invalid_dates_are_rejected(self, value):
        with pytest.raises(ValidationError):
            services.validate_iso_date(value)

    @pytest.mark.parametrize("duration", [0, 481, "sixty"])
    def test_invalid_durations_are_rejected(self, duration):
        with pytest.raises(ValidationError):
            services.validate_duration(duration)


class TestAdherenceSummary:
    def test_empty_history(self):
        summary = services.summarise_adherence([])
        assert summary["weeks_logged"] == 0
        assert summary["trend"] == "no-data"
        assert summary["latest_adherence"] is None

    def test_single_week_is_steady(self):
        summary = services.summarise_adherence([{"adherence": 70}])
        assert summary["trend"] == "steady"
        assert summary["average_adherence"] == 70.0

    @pytest.mark.parametrize(
        ("values", "trend"),
        [([60, 80], "improving"), ([80, 60], "declining"), ([70, 70], "steady")],
    )
    def test_trend_detection(self, values, trend):
        entries = [{"adherence": value} for value in values]
        assert services.summarise_adherence(entries)["trend"] == trend

    @pytest.mark.parametrize(
        ("values", "status"),
        [
            ([95, 92], "Elite consistency"),
            ([80, 78], "On track"),
            ([60, 55], "Needs attention"),
            ([30, 20], "At risk"),
        ],
    )
    def test_status_bands(self, values, status):
        entries = [{"adherence": value} for value in values]
        assert services.summarise_adherence(entries)["status"] == status

    def test_best_and_latest(self):
        entries = [{"adherence": v} for v in (50, 95, 70)]
        summary = services.summarise_adherence(entries)
        assert summary["best_week"] == 95
        assert summary["latest_adherence"] == 70
        assert summary["weeks_logged"] == 3


class TestTargetWeight:
    def test_positive_delta_means_weight_to_lose(self):
        assert services.target_weight_delta(90, 80) == 10.0

    def test_negative_delta_means_weight_to_gain(self):
        assert services.target_weight_delta(60, 70) == -10.0


class TestClientProfile:
    def test_derives_calories_bmi_and_defaults(self, sample_client_payload):
        profile = services.build_client_profile(sample_client_payload)
        assert profile["calories"] == 2800
        assert profile["bmi"] == 26.1
        assert profile["bmi_category"] == "Overweight"
        assert profile["program"] == "MG"
        assert profile["program_name"] == "Muscle Gain (MG) - PPL"

    def test_target_adherence_defaults_to_80(self, sample_client_payload):
        sample_client_payload.pop("target_adherence")
        assert services.build_client_profile(sample_client_payload)["target_adherence"] == 80

    @pytest.mark.parametrize(
        "field", ["name", "age", "height_cm", "weight_kg", "program"]
    )
    def test_missing_required_fields_are_reported(self, sample_client_payload, field):
        sample_client_payload.pop(field)
        with pytest.raises(ValidationError) as excinfo:
            services.build_client_profile(sample_client_payload)
        assert excinfo.value.field == field

    def test_body_must_be_a_mapping(self):
        with pytest.raises(ValidationError):
            services.build_client_profile(["not", "a", "dict"])
