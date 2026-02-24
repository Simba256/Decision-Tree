"""
Query Builder Module
====================
DRY query construction for Flask endpoints with dynamic filtering.

Usage:
    qb = QueryBuilder("SELECT * FROM programs p JOIN universities u ON p.university_id = u.id")
    qb.add_filter("p.field = ?", request.args.get("field"))
    qb.add_filter("u.country = ?", request.args.get("country"))
    qb.add_filter("p.tuition_usd <= ?", max_tuition)
    qb.order_by("p.y10_salary_usd DESC")
    query, params = qb.build()
    cursor.execute(query, params)
"""

from typing import Any, List, Optional, Tuple


class QueryBuilder:
    """
    Fluent query builder for SELECT statements with dynamic WHERE clauses.

    Automatically handles:
    - Skipping None/empty filter values
    - Proper WHERE 1=1 pattern for conditional appending
    - Parameter collection for safe SQL execution
    """

    def __init__(self, base_query: str):
        """
        Initialize with base SELECT query (without WHERE clause).

        Args:
            base_query: The SELECT ... FROM ... JOIN portion of the query.
        """
        self.base_query = base_query.rstrip()
        self.filters: List[Tuple[str, Any]] = []
        self._order_clause: Optional[str] = None
        self._limit: Optional[int] = None

    def add_filter(
        self,
        condition: str,
        value: Any,
        skip_none: bool = True,
        skip_empty: bool = True,
    ) -> "QueryBuilder":
        """
        Add a WHERE condition if value is present.

        Args:
            condition: SQL condition with ? placeholder (e.g., "p.field = ?")
            value: The parameter value. If None or empty string, filter is skipped.
            skip_none: Skip filter if value is None (default: True)
            skip_empty: Skip filter if value is empty string (default: True)

        Returns:
            self for method chaining
        """
        if skip_none and value is None:
            return self
        if skip_empty and value == "":
            return self
        self.filters.append((condition, value))
        return self

    def add_in_filter(
        self,
        column: str,
        values: Optional[List[Any]],
    ) -> "QueryBuilder":
        """
        Add an IN clause filter.

        Args:
            column: Column name (e.g., "p.id")
            values: List of values. If None or empty, filter is skipped.

        Returns:
            self for method chaining
        """
        if not values:
            return self
        placeholders = ", ".join("?" for _ in values)
        condition = f"{column} IN ({placeholders})"
        # Store as tuple with list of values for unpacking
        self.filters.append((condition, tuple(values)))
        return self

    def order_by(self, clause: str) -> "QueryBuilder":
        """
        Set ORDER BY clause.

        Args:
            clause: ORDER BY clause without the 'ORDER BY' keyword
                    (e.g., "p.y10_salary_usd DESC, p.name ASC")

        Returns:
            self for method chaining
        """
        self._order_clause = clause
        return self

    def limit(self, n: Optional[int]) -> "QueryBuilder":
        """
        Set LIMIT clause.

        Args:
            n: Number of rows to limit, or None for no limit.

        Returns:
            self for method chaining
        """
        self._limit = n
        return self

    def build(self) -> Tuple[str, List[Any]]:
        """
        Build the final query string and parameter list.

        Returns:
            (query_string, params_list) ready for cursor.execute()
        """
        parts = [self.base_query]
        params: List[Any] = []

        if self.filters:
            parts.append("WHERE 1=1")
            for condition, value in self.filters:
                parts.append(f"AND {condition}")
                # Handle IN clause with tuple of values
                if isinstance(value, tuple):
                    params.extend(value)
                else:
                    params.append(value)

        if self._order_clause:
            parts.append(f"ORDER BY {self._order_clause}")

        if self._limit is not None:
            parts.append(f"LIMIT {self._limit}")

        return " ".join(parts), params
