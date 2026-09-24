# Final Assessment Audit

Audit performed in this submission directory on 2026-09-24. Requirement wording is taken from `Take_Home_Assessment.docx`. PASS means the cited artifact or check was inspected/run; it does not imply production validation beyond the listed evidence.

## Task 1 — Customer segmentation

| Requirement | Status | Evidence |
|---|---|---|
| Exploratory data analysis | PASS | `task1/customer_segmentation.ipynb` executed end-to-end. The notebook includes dataset shape/types, duplicate and ID review, ranges, missingness, distributions, correlations, high-cardinality review and IQR outlier review. |
| Column-by-column missing-value decisions and rationale | PASS | `task1/report.md` lists all 14 input columns, missing percentages, use/treatment and feature role. Missing cumulative charges are estimated from monthly charges and tenure; credit score is omitted because 59.95% is missing; remaining fields have no missing values. |
| Remove non-useful columns and justify | PASS | ID is excluded as an identifier; gender is retained for EDA but excluded from distance features; referral code (79,701 unique values) and raw plan text are not direct features; credit score is omitted for high missingness. The report explains each choice. |
| Feature engineering | PASS | Notebook/report define tenure, login recency, plan tier, plan speed and imputed cumulative charges; raw dates/plan text are not sent to the model. |
| Scaling and encoding | PASS | Numeric fields use median imputation and standardization; categorical fields use mode imputation and one-hot encoding with unknown future categories ignored. Implemented in the fitted preprocessing pipeline. |
| Clustering approach and justification | PASS | K-Means is fit in transformed feature space; report describes its compact-cluster assumption and why profiles are useful descriptive groupings. |
| Defensible cluster count | PASS | Fixed seeded 12,000-row sample compared k=2..8 with silhouette, Calinski-Harabasz and Davies-Bouldin. k=3 has the best silhouette and readable profiles; report explicitly notes that k=2 leads on the other two metrics. |
| Train model on cleaned data | PASS | Notebook fit the final preprocessing and K-Means pipeline on all 100,000 deduplicated customers and saved the artifact. |
| Profile/name each segment and summarize inferences | PASS | `task1/report.md` gives three named profiles, counts, feature summaries, categorical mixes and interpretation, plus caveats against causal/churn claims. |
| Notebook deliverable | PASS | `task1/customer_segmentation.ipynb` is present and was executed end-to-end; the executed notebook and supporting figures are included in the repository.
| Loadable model and new-customer assignment | PASS | `task1/segment_model.joblib` contains preprocessing, fitted clusterer, labels and reference date. `task1/predict_segment.py` and its assignment path were exercised on three synthetic input rows; each received a segment ID/name. |
| Short written report | PASS | Current authoritative report is `task1/report.md`; it covers decisions, method, profiles, inferences and limitations. The older PDF is stale and is intentionally excluded from the final repository. |

## Task 2 — Offline Text-to-SQL

| Requirement | Status | Evidence |
|---|---|---|
| Use an SLM | PASS | Packaged local T5-Small sequence-to-sequence model/tokenizer under `task2/model/text-to-sql-small`; auxiliary local intent classifier files are `tiny_slm.pt`, `vocab.json`, and `labels.json`. The T5 model is used as a candidate SQL-generation component within the guarded pipeline; it was accepted directly for 1/10 supplied prompts, while the complete validated application produced correct results for 10/10. No runtime model download is configured. |
| NLP approach | PASS | Local intent classification, word/character TF-IDF schema linking, natural-language descriptions and runtime CSV values ground the deterministic planner and SLM proposal. See `task2/README.md`. |
| Offline inference | PASS (scoped) | Source inference ran while `socket.socket.connect` was patched to fail on any connection attempt; it loaded local models and answered a query. Executable validations set Hugging Face offline flags and completed all queries. The OS network adapter was not disabled, so this is not a full machine-level isolation test. |
| Self-contained; no Ollama dependency | PASS | Final Windows one-file executable built and completed 10 bank plus 9 unrelated-schema inference cases. Source scan and packaged dependency/model inspection found local T5 loading with `local_files_only=True`; no Ollama/OpenAI/hosted API path is used. |
| Runtime-supplied schema; no fixed sample table | PASS | CLI and GUI require a schema and table at runtime; the CLI has no default table. The same packaged exe loaded Products and Employees schemas/CSVs without production mappings for either schema. |
| Runtime-schema-driven behavior | PASS (bounded) | `task2/schema_agnostic_validation.py`: 9/9 semantic examples across Products and Employees, each a materially different 10-column schema; `task2/exe_validation.py`: the same 9 unrelated-schema examples passed in the packaged exe. The evidence supports runtime-schema-driven behavior for the tested single-table analytical query scope, not unrestricted generalization to arbitrary schemas or questions. |
| SQL references only supplied table/columns | PASS | Source schema tests rejected unknown columns, wrong tables and multiple statements for both alternate schemas. Runtime CSV is aligned to declared schema fields before SQLite use. |
| Reject arbitrary non-SELECT SQL | PASS | Source safety tests rejected 14 unsafe classes (INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, REPLACE, ATTACH, DETACH, PRAGMA, VACUUM, INTO, UNION and JOIN). Packaged exe also rejected destructive natural-language input. |
| Ten supplied validation questions | PASS | `task2/validate.py` returned 10/10 semantic result matches. `task2/exe_validation.py` independently ran all 10 through the packaged executable and compared results with SQLite expected queries. |
| GUI and service behavior | PASS | `task2/gui_validation.py` exercised all 10 bank questions, both unrelated runtime schemas, unsafe input and unknown input through the Tk GUI service integration. The no-argument packaged app process remained alive and responsive after 35 seconds of startup. |
| Windows packaging | PASS | `task2/dist/EulerQ_TextToSQL.exe` built successfully as a one-file PyInstaller executable (490,204,795 bytes) and passed packaged inference on all 19 positive cases plus unsafe/unknown handling. The executable and local runtime model assets are included in the clean archive. |
| Clean repository contents | PASS | The Git repository contains the source, documentation, Task 1 artifacts and Task 2 packaged assets. Large executable/model files are tracked through Git LFS. Assessment datasets are intentionally excluded from Git via `.gitignore`. |
| Requirements installation | PASS | Exact pins in `task2/requirements.txt` installed in Python 3.12.14. Installed versions: NumPy 2.5.3, pandas 3.0.1, scikit-learn 1.9.1, PyTorch 2.14.0+cpu, Transformers 4.57.3, SentencePiece 0.2.1 and PyInstaller 6.22.3. |
| Documentation and runnable source | PASS | Root and Task 2 READMEs document installation, GUI/CLI use, architecture, offline scope, runtime schemas, validation and executable build. Source modules pass `py_compile`. |

## Final checks and limitations

- Task 1 notebook execution: PASS. Task 1 artifact assignment: 3/3 synthetic rows received segment labels.
- Task 2 source: 10/10 supplied questions and 9/9 alternate-schema semantic tests PASS.
- Task 2 GUI integration: PASS for all 10 supplied questions, both alternate schemas and negative cases.
- Packaged executable: build PASS; 10/10 supplied, 9/9 alternate-schema, destructive/unknown cases PASS; no-argument GUI process remained responsive at startup.
- Offline evidence is limited to source socket-connect blocking plus offline model flags and successful packaged runs. The entire operating system's network interface was not disabled.
- T5 candidate SQL is not consistently correct: it was accepted for 1/10 supplied prompts. The validated final SQL uses the schema-grounded planner when a proposal fails validation/result comparison. The system supports a bounded set of single-table SELECT patterns, not arbitrary text-to-SQL.
- Schema generalization was validated on the supplied transaction schema plus Products and Employees alternate schemas. The implementation is intentionally bounded to supported single-table SELECT patterns and should not be interpreted as unrestricted Text-to-SQL across arbitrary schemas and natural-language requests.
- Python 3.12.14 was used for final verification because the pinned NumPy 2.5.3 requires Python >=3.12. Python 3.11.8 was not used for this final verified environment.
- Local build/virtual-environment/cache files may exist in the working directory but are excluded from Git by `.gitignore`. The final GitHub repository should be treated as the submission source; large binary assets are tracked through Git LFS.
- `task1/report.pdf` is an older export. `task1/report.md` is current and is included instead.
