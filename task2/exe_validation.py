"""Run the actual packaged executable through bank and unrelated-schema queries."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import tempfile

import pandas as pd

from schema_agnostic_validation import CASES, result_equal

ROOT = Path(__file__).resolve().parents[1]
TASK2 = Path(__file__).resolve().parent
EXE = TASK2 / "dist" / "EulerQ_TextToSQL.exe"


def run_cli(table: str, schema_path: Path, csv_path: Path, questions: list[str]) -> tuple[list[str], list[str]]:
    env = os.environ.copy()
    env["HF_HUB_OFFLINE"] = "1"
    env["TRANSFORMERS_OFFLINE"] = "1"
    # File-backed redirection is reliable for PyInstaller Windows console apps;
    # PIPE capture can leave their interactive input/output streams disconnected.
    with tempfile.TemporaryDirectory(prefix="eulerq-cli-", dir=r"C:\venvs") as folder:
        folder = Path(folder)
        stdin_path, stdout_path, stderr_path = folder / "stdin.txt", folder / "stdout.txt", folder / "stderr.txt"
        stdin_path.write_text("\n".join([*questions, "exit", ""]), encoding="utf-8")
        with stdin_path.open("r", encoding="utf-8") as stdin, stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open("w", encoding="utf-8") as stderr:
            proc = subprocess.run(
                [str(EXE), "--schema", str(schema_path), "--csv", str(csv_path), "--table", table],
                stdin=stdin, stdout=stdout, stderr=stderr, timeout=1200, env=env, cwd=ROOT,
            )
        output, errput = stdout_path.read_text(encoding="utf-8", errors="replace"), stderr_path.read_text(encoding="utf-8", errors="replace")
    if proc.returncode:
        raise RuntimeError(f"EXE returned {proc.returncode}: {errput}\n{output}")
    sql = re.findall(r"(?m)(?:^You:\s*)?SQL:\s*(.+)$", output)
    errors = re.findall(r"(?m)(?:^You:\s*)?Error:\s*(.+)$", output)
    return sql, errors


def run_semantics(table: str, data: pd.DataFrame, questions: list[str], expected: list[str], files_dir: Path) -> None:
    schema = next(case["schema"] for case in CASES if case["table"] == table)
    schema_path, csv_path = files_dir / f"{table}.json", files_dir / f"{table}.csv"
    schema_path.write_text(json.dumps(schema, ensure_ascii=False), encoding="utf-8")
    data.to_csv(csv_path, index=False)
    generated, errors = run_cli(table, schema_path, csv_path, questions)
    assert not errors, f"{table} EXE errors: {errors}"
    assert len(generated) == len(expected), f"{table}: expected {len(expected)} SQL lines, got {len(generated)}"
    con = sqlite3.connect(":memory:")
    try:
        data.to_sql(table, con, index=False, if_exists="replace")
        for question, actual_sql, expected_sql in zip(questions, generated, expected):
            actual, want = pd.read_sql_query(actual_sql, con), pd.read_sql_query(expected_sql, con)
            assert result_equal(actual, want), f"{table}: wrong result for {question}: {actual_sql}"
            print(f"PASS EXE [{table}] {question}\n  {actual_sql}")
    finally:
        con.close()


def main() -> int:
    if not EXE.is_file():
        raise FileNotFoundError(f"Build the one-file executable first: {EXE}")
    rows = pd.read_csv(TASK2 / "validation_results.csv")
    bank_schema = TASK2 / "schema.json"
    bank_csv = ROOT / "data" / "task2_bank_transactions_sample.csv"
    generated, errors = run_cli("transactions", bank_schema, bank_csv, rows.question.tolist())
    assert not errors and len(generated) == len(rows), f"Bank EXE output mismatch: {errors}"
    data = pd.read_csv(bank_csv)
    con = sqlite3.connect(":memory:")
    try:
        data.to_sql("transactions", con, index=False, if_exists="replace")
        for row, sql in zip(rows.itertuples(index=False), generated):
            assert result_equal(pd.read_sql_query(sql, con), pd.read_sql_query(row.expected_sql, con)), sql
            print(f"PASS EXE [transactions] {row.question}\n  {sql}")
    finally:
        con.close()

    with tempfile.TemporaryDirectory(prefix="eulerq-exe-", dir=r"C:\venvs") as folder:
        files_dir = Path(folder)
        for case in CASES:
            questions = [q for q, _ in case["questions"]]
            expected = [sql for _, sql in case["questions"]]
            run_semantics(case["table"], case["data"], questions, expected, files_dir)

    bad_qs = ["Delete all rows from transactions", "What is the meaning of life?"]
    bad_sql, bad_errors = run_cli("transactions", bank_schema, bank_csv, bad_qs)
    assert not bad_sql and len(bad_errors) == 2, f"Unsafe/unknown prompts were not blocked: {bad_sql} {bad_errors}"
    assert "destructive" in bad_errors[0].lower() or "unsupported" in bad_errors[0].lower()
    assert "schema" in bad_errors[1].lower()
    print("PASS EXE unsafe and unknown question handling")
    print("Packaged executable validation: PASS (10 bank, 9 unrelated-schema, unsafe and unknown)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
