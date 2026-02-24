"""
Parameter Validation Module
===========================
Declarative validators for Flask request parameters.

Usage:
    from validators import validate_params, LIFESTYLE, FAMILY_YEAR, AID_SCENARIO

    # In endpoint:
    params, error = validate_params(request.args, [LIFESTYLE, FAMILY_YEAR])
    if error:
        return error
    lifestyle = params["lifestyle"]
    family_year = params["family_year"]
"""

from dataclasses import dataclass
from typing import Optional, Union, Set, Tuple, Any
from flask import jsonify


@dataclass
class ParamValidator:
    """
    Declarative validator for a single request parameter.

    Attributes:
        name: Parameter name in request.args
        param_type: Expected type (str, int, float)
        default: Default value if not provided (None means required)
        valid_values: Set of valid string values (for str type only)
        min_val: Minimum value (for int/float)
        max_val: Maximum value (for int/float)
        error_msg: Custom error message format
    """
    name: str
    param_type: type
    default: Any = None
    valid_values: Optional[Set[str]] = None
    min_val: Optional[Union[int, float]] = None
    max_val: Optional[Union[int, float]] = None
    error_msg: Optional[str] = None

    def validate(self, args: dict) -> Tuple[Optional[Any], Optional[Tuple]]:
        """
        Validate a parameter from request args.

        Args:
            args: Request args dict (request.args)

        Returns:
            (value, None) on success
            (None, (jsonify_response, 400)) on error
        """
        raw = args.get(self.name)

        # Handle missing/empty values
        if raw is None or raw == "":
            if self.default is not None:
                return self.default, None
            # Parameter is optional if default is None
            return None, None

        # Type conversion
        try:
            if self.param_type == str:
                value = str(raw)
            elif self.param_type == int:
                value = int(raw)
            elif self.param_type == float:
                value = float(raw)
            else:
                value = raw
        except (ValueError, TypeError):
            msg = self.error_msg or f"'{self.name}' must be a valid {self.param_type.__name__}"
            return None, (jsonify({"error": msg}), 400)

        # Validate against allowed values
        if self.valid_values and value not in self.valid_values:
            options = ", ".join(f"'{v}'" for v in sorted(self.valid_values))
            msg = self.error_msg or f"{self.name} must be one of: {options}"
            return None, (jsonify({"error": msg}), 400)

        # Validate numeric range
        if self.min_val is not None and value < self.min_val:
            msg = self.error_msg or f"{self.name} must be >= {self.min_val}"
            return None, (jsonify({"error": msg}), 400)

        if self.max_val is not None and value > self.max_val:
            msg = self.error_msg or f"{self.name} must be <= {self.max_val}"
            return None, (jsonify({"error": msg}), 400)

        return value, None


def validate_params(
    args: dict,
    validators: list[ParamValidator]
) -> Tuple[dict, Optional[Tuple]]:
    """
    Validate multiple parameters at once.

    Args:
        args: Request args dict (request.args)
        validators: List of ParamValidator instances

    Returns:
        (params_dict, None) on success - dict maps param name to validated value
        ({}, error_tuple) on first validation error
    """
    result = {}
    for v in validators:
        value, error = v.validate(args)
        if error:
            return {}, error
        result[v.name] = value
    return result, None


# ═══════════════════════════════════════════════════════════════════════════════
# PREDEFINED VALIDATORS
# Common parameters used across multiple endpoints
# ═══════════════════════════════════════════════════════════════════════════════

LIFESTYLE = ParamValidator(
    name="lifestyle",
    param_type=str,
    default="frugal",
    valid_values={"frugal", "comfortable"},
    error_msg="lifestyle must be 'frugal' or 'comfortable'",
)

AID_SCENARIO = ParamValidator(
    name="aid_scenario",
    param_type=str,
    default="no_aid",
    valid_values={"no_aid", "expected", "best_case"},
    error_msg="aid_scenario must be 'no_aid', 'expected', or 'best_case'",
)

# Factory function for family_year with configurable max
def family_year_validator(max_year: int = 13) -> ParamValidator:
    """Create a family_year validator with configurable max year."""
    return ParamValidator(
        name="family_year",
        param_type=int,
        default=None,  # Optional - uses calculator default
        min_val=1,
        max_val=max_year,
        error_msg=f"family_year must be between 1 and {max_year} ({max_year} = never)",
    )

# Default family_year validators for common use cases
FAMILY_YEAR_MASTERS = family_year_validator(max_year=13)  # For masters (12yr + never)
FAMILY_YEAR_CAREER = family_year_validator(max_year=11)   # For career paths (10yr + never)

# Node type for career paths
NODE_TYPE = ParamValidator(
    name="node_type",
    param_type=str,
    default=None,
    valid_values={"career", "trading", "startup", "freelance"},
    error_msg="node_type must be 'career', 'trading', 'startup', or 'freelance'",
)

# Compact mode flag
COMPACT = ParamValidator(
    name="compact",
    param_type=str,
    default="false",
    valid_values={"true", "false"},
)

# Sort options
NETWORTH_SORT = ParamValidator(
    name="sort_by",
    param_type=str,
    default="net_benefit",
    valid_values={"net_benefit", "cost", "y1", "y10", "networth", "initial_capital"},
)

CAREER_SORT = ParamValidator(
    name="sort_by",
    param_type=str,
    default="net_benefit",
    valid_values={"net_benefit", "y1", "y10", "networth"},
)


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS FOR OPTIONAL PARAMS
# ═══════════════════════════════════════════════════════════════════════════════

def validate_optional_int(args: dict, name: str) -> Tuple[Optional[int], Optional[Tuple]]:
    """Validate an optional integer parameter."""
    validator = ParamValidator(name=name, param_type=int, default=None)
    return validator.validate(args)


def validate_optional_float(args: dict, name: str) -> Tuple[Optional[float], Optional[Tuple]]:
    """Validate an optional float parameter."""
    validator = ParamValidator(name=name, param_type=float, default=None)
    return validator.validate(args)
