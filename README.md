# EulerQ AI/ML Take-Home Assessment

This submission contains the two requested assessment deliverables: customer segmentation (Task 1) and an offline, runtime-schema Text-to-SQL desktop tool (Task 2). The assessment document is [Take_Home_Assessment.docx](Take_Home_Assessment.docx); test evidence and limitations are in [FINAL_AUDIT.md](FINAL_AUDIT.md).

## Project structure

```text
data/                       Supplied customer and bank transaction CSVs
task1/                      EDA notebook, report, model artifact and assignment helper
task2/                      Offline SQL service, GUI, local model, validators and build spec
README.md                   Setup and run instructions
FINAL_AUDIT.md              Test-by-test evidence and limitations
```

## Task 1 — Customer segmentation

The notebook performs data-quality exploration, missingness and duplicate review, feature engineering, preprocessing, clustering, cluster-count comparison, and segment profiling. It removes 200 exact duplicate records, excludes the customer identifier and high-cardinality referral/raw plan text, derives tenure, login recency, plan tier and speed, and estimates missing cumulative charges from monthly charges and tenure. Numeric fields are median-imputed/scaled; categorical fields are mode-imputed/one-hot encoded. K-Means is selected as a practical unsupervised method; k=3 has the strongest silhouette among k=2..8, while k=2 leads on the other two reported indices. The report describes three behavioral/value profiles and the trade-off.

Deliverables include `task1/customer_segmentation.ipynb`, `task1/segment_model.joblib`, `task1/segmentation.py`, `task1/predict_segment.py`, `task1/report.md`, and the figures. The artifact includes preprocessing and the fitted cluster model, and the assignment helper accepts new rows in the original input schema.

## Task 2 — Offline Text-to-SQL

Task 2 combines a bundled T5-Small SQL sequence-to-sequence model, a local Transformer intent classifier, TF-IDF word/character schema linking, a deterministic schema-grounded planner, a SELECT-only SQL validator, and SQLite execution. T5 proposes SQL; the application validates its syntax/schema and accepts it only if its results agree with the deterministic plan on supplied local data. Otherwise it returns the guarded plan. In the supplied ten-question set the local proposal was accepted on 1/10 prompts; guarded planning matched all ten expected results. This is a bounded single-table query assistant, not unrestricted text-to-SQL.

The schema JSON and table name are supplied at runtime. Descriptions support natural-language linking; optional CSV values supply runtime categorical literals. The schema controls the columns exposed to execution, even if the CSV has extra columns. Products and Employees examples demonstrate behavior on unrelated schemas. SQL is restricted to a single read-only `SELECT` on the supplied table, and SQLite `EXPLAIN` checks syntax/column validity before execution.

The model/tokenizer and auxiliary model assets are bundled in `task2/model`. Transformers/Hugging Face offline flags are enabled, T5 loads with `local_files_only=True`, and no Ollama, API key, hosted model, or network fallback is used. A source-mode test blocked all socket connection attempts while loading both models and generating the Cheque/date query. See the audit for the precise offline test scope.

### Installation

Tested on Python 3.12.14 (64-bit Windows), using the pinned packages in `task2/requirements.txt`. From the repository root:

```powershell
py -3.12 -m venv C:\venvs\eulerq312
C:\venvs\eulerq312\Scripts\python.exe -m pip install -r task2\requirements.txt
```

For the notebook and Task 1 dependencies, also run:

```powershell
C:\venvs\eulerq312\Scripts\python.exe -m pip install -r task1\requirements.txt
```

The tested Task 2 versions are NumPy 2.5.3, pandas 3.0.1, scikit-learn 1.9.1, PyTorch 2.14.0+cpu, Transformers 4.57.3, SentencePiece 0.2.1, and PyInstaller 6.22.3.

The bundled Codex Python runtime has the Tkinter module but omits its Tcl/Tk script library. The source app detects this and points Tkinter to its bundled Tcl/Tk script assets; a standard full Windows Python 3.12 installation uses its own Tcl/Tk installation. The Windows executable bundles the Tcl/Tk runtime collected by PyInstaller.

### Run the GUI

From the repository root:

```powershell
C:\venvs\eulerq312\Scripts\python.exe task2\app.py
```

Choose a schema JSON and table name, optionally choose a CSV, and click **Load schema and data**. The GUI is Tkinter-based and uses the same `TextToSQL` backend as the CLI. Examples are built from the loaded schema/data.

### Run the CLI

From the repository root:

```powershell
C:\venvs\eulerq312\Scripts\python.exe task2\app.py --schema task2\schema.json --csv data\task2_bank_transactions_sample.csv --table transactions --question "List all transactions done through Cheque, sorted by date."
```

For another dataset, supply its own schema JSON, CSV, and table name. The CSV can be omitted if useful categorical values are present in descriptions. Omitting command-line options opens the GUI; CLI mode requires both `--schema` and `--table`.

### Validation

Run these from the repository root:

```powershell
C:\venvs\eulerq312\Scripts\python.exe task2\validate.py
C:\venvs\eulerq312\Scripts\python.exe task2\schema_agnostic_validation.py
C:\venvs\eulerq312\Scripts\python.exe task2\gui_validation.py
C:\venvs\eulerq312\Scripts\python.exe task2\exe_validation.py
```

The source results are 10/10 assessment cases and 9/9 semantic examples over full Products and Employees schemas. The schema script also rejects 14 unsafe SQL classes, unknown columns/tables, and multiple statements. GUI and executable integration scripts exercise the same questions through the local interface/backend. `exe_validation.py` requires the executable to be built first. `FINAL_AUDIT.md` records actual results.

### Build the Windows executable

From `task2` with the tested environment installed:

```powershell
C:\venvs\eulerq312\Scripts\python.exe -m PyInstaller --noconfirm --clean EulerQ_TextToSQL.spec --workpath build_final --distpath dist
```

Or run `build_windows.bat`, which uses `C:\venvs\eulerq312`. The executable is `task2/dist/EulerQ_TextToSQL.exe`. It is a one-file executable containing the GUI, Python runtime dependencies, both local inference models, tokenizer files, and auxiliary classifier assets. Run the executable with no arguments for the GUI, or pass `--schema`, `--table`, optional `--csv`, and optional `--question` for CLI mode.

## Known limitations

- The planner supports a bounded set of single-table SELECT patterns. Unsupported requests fail instead of being translated to arbitrary SQL.
- T5 proposals are not consistently semantically correct; the deterministic planner and result-equivalence check are the guarded path.
- Without a local CSV, runtime categorical values must be described by the schema.
- One-file packaging is large because PyTorch and the local T5 weights are included. Windows machines may need the relevant Microsoft Visual C++ runtime.
- The offline source test denied socket connections in the Python process. It establishes the tested path needed no network; the executable was not tested while the entire OS network interface was disabled.
- Customer segmentation is descriptive, not a churn prediction model; charge imputation and K-Means geometry have the limitations described in `task1/report.md`.
