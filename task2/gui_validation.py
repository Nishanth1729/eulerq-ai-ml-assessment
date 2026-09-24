"""Programmatic integration check for GUI widgets, shared service and result display."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pandas as pd

from app import configure_tk_runtime
configure_tk_runtime()
import tkinter as tk
from gui import EulerQApp, messagebox
from schema_agnostic_validation import CASES

ROOT = Path(__file__).resolve().parents[1]
TASK2 = Path(__file__).resolve().parent


def run_query(ui: EulerQApp, root: tk.Tk, question: str) -> int:
    ui._set_question(question)
    ui._run_question(question)
    root.update()
    assert ui.sql_text.get("1.0", "end").strip(), "UI did not display generated SQL"
    ui.service.validate_sql(ui.sql_text.get("1.0", "end").strip())
    assert ui.status.get().startswith("Success"), ui.status.get()
    return len(ui.result.get_children())


def main() -> int:
    root = tk.Tk()
    root.withdraw()
    ui = EulerQApp(root)
    try:
        ui.schema_path.set(str(TASK2 / "schema.json"))
        ui.csv_path.set(str(ROOT / "data" / "task2_bank_transactions_sample.csv"))
        ui.table_name.set("transactions")
        ui.load_runtime()
        assert ui.service is not None and len(ui.columns.get_children()) == 10
        expected = pd.read_csv(TASK2 / "validation_results.csv")
        for row in expected.itertuples(index=False):
            shown = run_query(ui, root, row.question)
            assert shown == int(row.expected_rows), f"Result row count mismatch for: {row.question}"
            print(f"PASS GUI bank: {row.question} ({shown} rows)")

        # Same visible UI/result surface, newly loaded dynamic schemas/data.
        with tempfile.TemporaryDirectory(prefix="eulerq_gui_schema_") as folder:
            temp = Path(folder)
            for case in CASES:
                schema_file = temp / f"{case['table']}.json"
                csv_file = temp / f"{case['table']}.csv"
                schema_file.write_text(json.dumps(case["schema"], ensure_ascii=False), encoding="utf-8")
                case["data"].to_csv(csv_file, index=False)
                ui.schema_path.set(str(schema_file)); ui.csv_path.set(str(csv_file)); ui.table_name.set(case["table"])
                ui.load_runtime()
                assert ui.service is not None and len(ui.columns.get_children()) == len(case["schema"])
                question, _expected_sql = case["questions"][0]
                shown = run_query(ui, root, question)
                print(f"PASS GUI runtime schema: {case['table']} ({shown} rows)")

        # A clean, user-facing warning must replace a traceback/modal during an unsafe request.
        messagebox.showwarning = lambda *_args, **_kwargs: None
        ui._run_question("Delete all rows from the table")
        root.update()
        assert "Unsafe SQL blocked" in ui.status.get(), ui.status.get()
        print("PASS GUI unsafe request message")

        ui._run_question("What is the meaning of life?")
        root.update()
        assert "does not appear to refer" in ui.status.get(), ui.status.get()
        print("PASS GUI unknown question message")
        print("GUI integration: PASS (10 assessment queries, 2 unrelated schemas, unsafe and unknown input)")
        return 0
    finally:
        root.destroy()


if __name__ == "__main__":
    raise SystemExit(main())
