"""Exercise TextToSQL with unrelated runtime schemas and in-memory data."""
from pathlib import Path
import sqlite3
import sys

import pandas as pd

from app import TextToSQL


CASES = [
    {
        "table": "products",
        "schema": [
            {"name": "product_id", "description": "Unique product identifier."},
            {"name": "product_name", "description": "Name of the product."},
            {"name": "category", "description": "Product category, such as Electronics or Furniture."},
            {"name": "price", "description": "Price of one product in currency units."},
            {"name": "stock_quantity", "description": "Number of units in stock."},
            {"name": "supplier", "description": "Supplier company for the product."},
            {"name": "rating", "description": "Customer rating score for the product."},
            {"name": "created_date", "description": "Date the product was created."},
            {"name": "warehouse", "description": "Warehouse location storing the product."},
            {"name": "status", "description": "Current product status, such as Active or Inactive."},
        ],
        "data": pd.DataFrame([
            (1, "Radio", "Electronics", 70.0, 8, "Acme", 4.1, "2024-01-10", "West", "Active"),
            (2, "Chair", "Furniture", 45.0, 20, "FurniCo", 4.4, "2024-02-14", "East", "Active"),
            (3, "Camera", "Electronics", 220.0, 3, "Acme", 4.8, "2024-03-18", "West", "Active"),
            (4, "Lamp", "Furniture", 30.0, 6, "Luma", 3.8, "2024-04-22", "Central", "Inactive"),
            (5, "Tablet", "Electronics", 150.0, 12, "TechWorks", 4.6, "2024-05-26", "East", "Active"),
        ], columns=["product_id", "product_name", "category", "price", "stock_quantity", "supplier", "rating", "created_date", "warehouse", "status"]),
        "questions": [
            ("Show all products in the Electronics category.", "SELECT * FROM products WHERE category = 'Electronics'"),
            ("What are the top 5 most expensive products?", "SELECT * FROM products ORDER BY price DESC LIMIT 5"),
            ("Show products where stock quantity is below 10.", "SELECT * FROM products WHERE stock_quantity < 10"),
            ("What is the average price for each category?", "SELECT category, AVG(price) FROM products GROUP BY category"),
            ("List all active products.", "SELECT * FROM products WHERE status = 'Active'"),
        ],
    },
    {
        "table": "employees",
        "schema": [
            {"name": "employee_id", "description": "Unique employee identifier."},
            {"name": "employee_name", "description": "Name of the employee."},
            {"name": "department", "description": "Organizational department, for example Engineering or Finance."},
            {"name": "salary", "description": "Annual salary in currency units."},
            {"name": "joining_date", "description": "Date the employee joined."},
            {"name": "location", "description": "City where the employee is based, such as Hyderabad or Chennai."},
            {"name": "experience_years", "description": "Number of years of professional experience."},
            {"name": "employment_type", "description": "Employment type, for example Permanent or Contract."},
            {"name": "performance_score", "description": "Annual performance score."},
            {"name": "status", "description": "Current employment status, such as Active or OnLeave."},
        ],
        "data": pd.DataFrame([
            (1, "Asha", "Engineering", 90000, "2021-01-02", "Hyderabad", 7, "Permanent", 4.5, "Active"),
            (2, "Dev", "Finance", 70000, "2022-03-04", "Chennai", 4, "Contract", 3.9, "Active"),
            (3, "Mira", "Engineering", 120000, "2020-05-06", "Hyderabad", 9, "Permanent", 4.8, "Active"),
            (4, "Ravi", "Sales", 80000, "2023-07-08", "Hyderabad", 3, "Permanent", 4.0, "OnLeave"),
            (5, "Lea", "Engineering", 100000, "2019-09-10", "Chennai", 10, "Contract", 4.7, "Active"),
        ], columns=["employee_id", "employee_name", "department", "salary", "joining_date", "location", "experience_years", "employment_type", "performance_score", "status"]),
        "questions": [
            ("List employees in Engineering.", "SELECT * FROM employees WHERE department = 'Engineering'"),
            ("Show the top 5 highest salaries.", "SELECT * FROM employees ORDER BY salary DESC LIMIT 5"),
            ("How many employees are in Hyderabad?", "SELECT COUNT(*) FROM employees WHERE location = 'Hyderabad'"),
            ("Show the average salary for each department.", "SELECT department, AVG(salary) FROM employees GROUP BY department"),
        ],
    },
]


def result_equal(a: pd.DataFrame, b: pd.DataFrame) -> bool:
    if a.shape != b.shape:
        return False
    # Sort rows and disregard output aliases, which are not semantically relevant.
    a, b = a.reset_index(drop=True), b.reset_index(drop=True)
    for col in range(a.shape[1]):
        if pd.api.types.is_numeric_dtype(a.iloc[:, col]) and pd.api.types.is_numeric_dtype(b.iloc[:, col]):
            if not (a.iloc[:, col].fillna(0).to_numpy() == b.iloc[:, col].fillna(0).to_numpy()).all():
                try:
                    import numpy as np
                    if not np.allclose(a.iloc[:, col], b.iloc[:, col], equal_nan=True):
                        return False
                except (TypeError, ValueError):
                    return False
        elif not a.iloc[:, col].astype(str).equals(b.iloc[:, col].astype(str)):
            return False
    return True


def main() -> int:
    results = []
    for case in CASES:
        bot = TextToSQL(case["schema"], data=None, table=case["table"])
        con = sqlite3.connect(":memory:")
        case["data"].to_sql(case["table"], con, index=False)
        for question, expected_sql in case["questions"]:
            generated = bot.generate(question)["sql"]
            actual = pd.read_sql_query(generated, con)
            expected = pd.read_sql_query(expected_sql, con)
            passed = result_equal(actual, expected)
            results.append((case["table"], question, generated, passed))
            print(f"{'PASS' if passed else 'FAIL'} [{case['table']}] {question}\n  {generated}")
        try:
            bot.validate_sql(f'SELECT "not_a_schema_column" FROM "{case["table"]}";')
            raise AssertionError("Unknown column was not rejected")
        except ValueError:
            print(f"PASS [{case['table']}] unknown SQL column rejected")
        for unsafe_reference in [
            f'SELECT * FROM "not_{case["table"]}"',
            f'SELECT * FROM "{case["table"]}"; DELETE FROM "{case["table"]}"',
        ]:
            try:
                bot.validate_sql(unsafe_reference)
                raise AssertionError(f"Out-of-table or multi-statement SQL was accepted: {unsafe_reference}")
            except ValueError:
                pass
        assert bot.extract_value("Show all rows sorted by date") == (None, None), "Generic date term became a literal filter value"
        print(f"PASS [{case['table']}] supplied-table, single-statement and generic-date safeguards")
        unsafe = [
            "INSERT INTO \"{}\" VALUES (1)", "UPDATE \"{}\" SET \"{}\"=1",
            "DELETE FROM \"{}\"", "DROP TABLE \"{}\"", "ALTER TABLE \"{}\" ADD x TEXT",
            "CREATE TABLE x (a)", "REPLACE INTO \"{}\" VALUES (1)",
            "ATTACH DATABASE 'x' AS y", "DETACH DATABASE y", "PRAGMA table_info(x)",
            "VACUUM", "SELECT * FROM \"{}\" INTO x", "SELECT * FROM \"{}\" UNION SELECT * FROM \"{}\"",
            "SELECT * FROM \"{}\" JOIN \"{}\" ON 1=1",
        ]
        for template in unsafe:
            sql = template.format(case["table"], *(case["table"] for _ in range(template.count("{}") - 1)))
            try:
                bot.validate_sql(sql)
                raise AssertionError(f"Unsafe SQL was accepted: {sql}")
            except ValueError:
                pass
        print(f"PASS [{case['table']}] 14 unsafe SQL classes rejected")
        con.close()
    passed = sum(r[3] for r in results)
    print(f"Schema-agnostic semantic matches: {passed}/{len(results)}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
