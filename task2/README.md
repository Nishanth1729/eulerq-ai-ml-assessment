# Task 2 — Offline Text-to-SQL

## Run

From the project root, `python task2/app.py` opens the local Tkinter dashboard. From `task2`, `python app.py` also opens it. In the interface, choose a schema JSON, table name and optional CSV, then load the runtime data. The GUI asks the same `TextToSQL` service as CLI mode, validates the generated SQL, and executes it against an in-memory SQLite copy of the schema-aligned CSV.

CLI mode remains available:

```powershell
python task2/app.py --schema task2/schema.json --csv data/task2_bank_transactions_sample.csv --table transactions --question "List all transactions done through Cheque, sorted by date."
```

CLI mode requires `--schema` and `--table`; the table name is never defaulted to the assessment sample. `--csv` is optional. The schema is a JSON list containing `name` and plain-English `description` for each column. Extra CSV columns are ignored; each declared schema column must exist in the CSV.

## Architecture and safety

- T5-Small SQL SLM and SentencePiece tokenizer are loaded only from `model/text-to-sql-small`; `local_files_only=True`, `HF_HUB_OFFLINE=1`, and `TRANSFORMERS_OFFLINE=1` prevent model downloads.
- `model/tiny_slm.pt`, `model/vocab.json`, and `model/labels.json` provide the auxiliary local intent classifier.
- Word/character TF-IDF links question language to the current schema. Runtime schema descriptions and optional CSV category values provide literal/column grounding.
- A deterministic planner creates a schema-grounded plan. A local T5 proposal is accepted only when syntax/schema validation succeeds and, with local data, SQLite results match the plan. The plan is the safe fallback.
- SQL is limited to a single SELECT from the supplied table. Dangerous/unsupported operations and unknown columns are rejected; SQLite `EXPLAIN` checks the statement before execution.

No Ollama, API key, hosted inference endpoint or network fallback is used. The source test replaced socket connection attempts with a hard failure, then loaded the local models and answered the Cheque/date question successfully. This verifies that tested source inference did not attempt a network connection; it is not a test with the entire operating system network interface disabled.

## Install and validate

Tested on Python 3.12.14 with the exact pins in `requirements.txt` (NumPy 2.5.3, pandas 3.0.1, scikit-learn 1.9.1, PyTorch 2.14.0+cpu, Transformers 4.57.3, SentencePiece 0.2.1, PyInstaller 6.22.3). From the project root:

```powershell
py -3.12 -m venv C:\venvs\eulerq312
C:\venvs\eulerq312\Scripts\python.exe -m pip install -r task2\requirements.txt
C:\venvs\eulerq312\Scripts\python.exe task2\validate.py
C:\venvs\eulerq312\Scripts\python.exe task2\schema_agnostic_validation.py
C:\venvs\eulerq312\Scripts\python.exe task2\gui_validation.py
C:\venvs\eulerq312\Scripts\python.exe task2\exe_validation.py
```

`exe_validation.py` requires the executable to have been built first. Latest source validation: 10/10 assessment questions and 9/9 semantic cases on complete Products/Employees schemas pass. Each synthetic schema also checks unknown-column/table and multi-statement rejection, generic date-value handling, and 14 classes of unsafe SQL statements. See `../FINAL_AUDIT.md` for exact output and limitations.

## Build

From this directory, with the tested environment installed:

```powershell
C:\venvs\eulerq312\Scripts\python.exe -m PyInstaller --noconfirm --clean EulerQ_TextToSQL.spec --workpath build_final --distpath dist
```

The resulting one-file app is `dist/EulerQ_TextToSQL.exe`; it starts the GUI without arguments and retains CLI mode with arguments. The spec places individual classifier files under `model/` and the full T5/tokenizer directory under `model/text-to-sql-small`; runtime resource discovery checks the PyInstaller extraction root, executable directory and source directory.

The minimal Python 3.12 runtime used for this build omits Tcl/Tk script files even though it includes `_tkinter`. The application and spec detect that case and point to the bundled Tcl/Tk scripts; full CPython Windows installs normally provide their own. The frozen executable includes PyInstaller's collected Tcl/Tk resources.

## Limits

The query planner supports a bounded set of common single-table SELECT patterns, not unrestricted SQL. T5 candidates are proposals and can be inaccurate; guarded plan fallbacks are expected. Without a CSV, values must be present in schema descriptions. The executable is large because the local model and PyTorch runtime are bundled.
