# EulerQ AI/ML Take-Home Assessment

This submission contains the two requested assessment deliverables: customer segmentation (Task 1) and an offline, runtime-schema Text-to-SQL desktop tool (Task 2). The assessment document is [Take_Home_Assessment.docx](Take_Home_Assessment.docx); test evidence and limitations are in [FINAL_AUDIT.md](FINAL_AUDIT.md).

## Project structure

```text
data/                       Assessment datasets (not committed to Git)
                            (intentionally excluded from Git)

task1/                      EDA notebook, report, model artifact and
                            assignment helper

task2/                      Offline SQL service, GUI, local models,
                            validators and build specification

README.md                   Setup and run instructions

FINAL_AUDIT.md              Test-by-test evidence and limitations
```

## Task 1 — Customer segmentation

The notebook performs data-quality exploration, missingness and duplicate review, feature engineering, preprocessing, clustering, cluster-count comparison, and segment profiling. It removes 200 exact duplicate records, excludes the customer identifier and high-cardinality referral/raw plan text, derives tenure, login recency, plan tier and speed, and estimates missing cumulative charges from monthly charges and tenure.

Numeric fields are median-imputed/scaled; categorical fields are mode-imputed/one-hot encoded. K-Means is selected as a practical unsupervised method; k=3 has the strongest silhouette among k=2..8, while k=2 leads on the other two reported indices. The report describes three behavioral/value profiles and the trade-off.

Deliverables include:

* `task1/customer_segmentation.ipynb`
* `task1/segment_model.joblib`
* `task1/segmentation.py`
* `task1/predict_segment.py`
* `task1/report.md`
* supporting figures

The artifact includes preprocessing and the fitted cluster model, and the assignment helper accepts new rows in the original input schema.

## Task 2 — Offline Text-to-SQL

Task 2 is a **bounded, runtime-schema-driven single-table Text-to-SQL assistant**. It combines:

* a bundled T5-Small SQL sequence-to-sequence model
* a local Transformer intent classifier
* TF-IDF word/character schema linking
* a deterministic schema-grounded query planner
* a SELECT-only SQL validator
* SQLite execution and result validation

The T5 model is used as a **candidate SQL-generation component**. The application does not rely on the T5 proposal alone: generated SQL is checked against the supplied runtime schema and compared with the deterministic plan/result before being accepted. When the candidate does not satisfy the validation checks, the guarded deterministic planner provides the supported query path.

In the supplied ten-question validation set, the T5 proposal was accepted directly for 1/10 prompts; the complete guarded application produced the expected results for all 10/10 prompts. This behavior is documented explicitly rather than treating the end-to-end result as T5-only Text-to-SQL accuracy.

### Model attribution

The bundled `t5-small_for_sql_generation` model is based on
[`google-t5/t5-small`](https://huggingface.co/google-t5/t5-small) and is
described by the bundled model metadata as a fine-tuned T5-Small model for
natural-language-to-SQL generation.

The model metadata identifies `gretelai/synthetic_text_to_sql` as a training
dataset and credits `humarin/chatgpt_paraphraser_on_T5_base` for paraphrase
augmentation. Optuna was used for hyperparameter tuning according to the
bundled model documentation.

The original model metadata is retained in
`task2/model/text-to-sql-small/README.md`.

The application is intentionally bounded to supported single-table analytical SELECT patterns. Unsupported requests fail safely instead of being translated into arbitrary SQL.

The schema JSON and table name are supplied at runtime. Descriptions support natural-language schema linking; optional CSV values supply runtime categorical literals. The schema controls the columns exposed to execution, even if the CSV contains additional columns.

Products and Employees examples demonstrate the same runtime-schema workflow on unrelated schemas. SQL is restricted to a single read-only `SELECT` on the supplied table, and SQLite `EXPLAIN` checks syntax and column validity before execution.

### Offline operation

The model/tokenizer and auxiliary model assets are bundled in `task2/model`.

Transformers/Hugging Face offline flags are enabled and the T5 model is loaded with `local_files_only=True`. No Ollama, API key, hosted model, or network fallback is required.

A source-mode test blocked socket connection attempts while loading both models and generating the Cheque/date query. See `FINAL_AUDIT.md` for the precise offline test scope.

The bundled T5 configuration contains a historical local `_name_or_path` value from the environment in which the model was originally saved; this path is metadata only and is not used as an external model dependency. The application loads the bundled local model files.

## Installation

Tested on Python 3.12.14 (64-bit Windows), using the pinned packages in `task2/requirements.txt`.

From the repository root:

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

## Run the GUI

From the repository root:

```powershell
C:\venvs\eulerq312\Scripts\python.exe task2\app.py
```

Choose a schema JSON and table name, optionally choose a CSV, and click **Load schema and data**. The GUI is Tkinter-based and uses the same `TextToSQL` backend as the CLI. Examples are built from the loaded schema/data.

## Run the CLI

From the repository root:

The assessment datasets are intentionally excluded from this repository, so the following command assumes the supplied assessment CSV has been placed in the local `data/` directory.

```powershell
C:\venvs\eulerq312\Scripts\python.exe task2\app.py --schema task2\schema.json --csv data\task2_bank_transactions_sample.csv --table transactions --question "List all transactions done through Cheque, sorted by date."
```

The example above assumes the supplied assessment CSV is available locally. The assessment datasets are intentionally excluded from this Git repository.

For another dataset, supply its own schema JSON, CSV, and table name. The CSV can be omitted if useful categorical values are present in descriptions.

Omitting command-line options opens the GUI; CLI mode requires both `--schema` and `--table`.

## Validation

Run these from the repository root:

```powershell
C:\venvs\eulerq312\Scripts\python.exe task2\validate.py

C:\venvs\eulerq312\Scripts\python.exe task2\schema_agnostic_validation.py

C:\venvs\eulerq312\Scripts\python.exe task2\gui_validation.py

C:\venvs\eulerq312\Scripts\python.exe task2\exe_validation.py
```

The recorded source results are 10/10 assessment cases and 9/9 semantic examples over full Products and Employees schemas.

The schema validation also rejects unsafe SQL classes, unknown columns/tables, and multiple statements. GUI and executable integration scripts exercise the same questions through the local interface/backend.

`exe_validation.py` requires the executable to be built first. `FINAL_AUDIT.md` records the actual validation results and their scope.

These results demonstrate the tested behavior of the complete application; they should not be interpreted as a claim of unrestricted Text-to-SQL capability across arbitrary schemas and question types.

## Build the Windows executable

From `task2` with the tested environment installed:

```powershell
C:\venvs\eulerq312\Scripts\python.exe -m PyInstaller --noconfirm --clean EulerQ_TextToSQL.spec --workpath build_final --distpath dist
```

Or run `build_windows.bat`, which uses `C:\venvs\eulerq312`.

The executable is:

```text
task2/dist/EulerQ_TextToSQL.exe
```

It is a one-file executable containing the GUI, Python runtime dependencies, both local inference models, tokenizer files, and auxiliary classifier assets.

Run the executable with no arguments for the GUI, or pass `--schema`, `--table`, optional `--csv`, and optional `--question` for CLI mode.

## Git LFS

The repository uses **Git LFS** for large binary assets, including the Windows executable and the bundled T5 model weights.

A normal GitHub ZIP download may contain LFS pointer files rather than the large binary contents unless Git LFS is installed and the LFS objects are fetched.

Clone the repository with Git LFS installed:

```powershell
git lfs install
git clone https://github.com/Nishanth1729/eulerq-ai-ml-assessment.git
```

Then verify/fetch LFS objects if required:

```powershell
git lfs pull
```

## Known limitations

* The planner supports a bounded set of single-table SELECT patterns. Unsupported requests fail instead of being translated to arbitrary SQL.

* T5 proposals are not consistently semantically correct. The deterministic planner and result-equivalence check provide the guarded execution path.

* The complete application achieved 10/10 on the supplied assessment questions, but this should not be interpreted as unrestricted Text-to-SQL accuracy of the T5 model itself.

* Without a local CSV, runtime categorical values must be described by the schema.

* The current validation set demonstrates runtime-schema behavior on the supplied transaction schema and the Products and Employees examples. It does not establish unrestricted generalization to arbitrary schemas or arbitrary natural-language questions.

* One-file packaging is large because PyTorch and the local T5 weights are included. Windows machines may need the relevant Microsoft Visual C++ runtime.

* The offline source test denied socket connections in the Python process. It establishes that the tested source inference path required no network; the executable was not tested while the entire OS network interface was disabled.

* Customer segmentation is descriptive, not a churn prediction model; charge imputation and K-Means geometry have the limitations described in `task1/report.md`.

* The assessment datasets are intentionally not committed to the Git repository. They must be supplied separately when reproducing the Task 1 notebook or the supplied-data Task 2 CLI example.
