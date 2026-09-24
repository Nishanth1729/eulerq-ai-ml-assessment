---
datasets:
- gretelai/synthetic_text_to_sql
metrics:
- exact_match
- bleu
tags:
- sql
- code
- language
- English
language:
- en
base_model:
- google-t5/t5-small
pipeline_tag: text-to-text
---

# t5-small_for_sql_generation

This repository contains a fine-tuned [`t5-small`](https://huggingface.co/t5-small) model for translating natural language queries into SQL statements.

The model was trained on synthetic and/or manually prepared data using a structured prompt format that includes both the user request and the table schema.

## Task

The model solves the task of **Natural Language to SQL** (NL2SQL) generation. Given an English query and the table structure, it produces a syntactically valid SQL query corresponding to the user’s request.

## Input Format

Each input to the model follows this format:
english_question | SQL_table_definition + some entries

### Examples

List all employees | CREATE TABLE Employees (id INT, name TEXT, surname TEXT); INSERT INTO Employees (1, Eugene, Cyborg)

Find names of employees whose ID is greater than 100 | CREATE TABLE Employees (id INT, name TEXT, surname TEXT)

Show all records from the table | CREATE TABLE Sales (sale_id INT, amount FLOAT)

### Output format

The output is a complete SQL query string:

SELECT * FROM Employees;
SELECT name FROM Employees WHERE id > 100;
SELECT * FROM Sales;

## Data Augmentation and Optimization

To improve generalization and robustness, the dataset was augmented using paraphrasing techniques. Specifically, the model [**humarin/chatgpt_paraphraser_on_T5_base**](https://huggingface.co/humarin/chatgpt_paraphraser_on_T5_base) was used to generate paraphrased versions of the same natural language query. This helped the model learn to handle diverse phrasings of the same intent.

Additionally, [**Optuna**](https://optuna.org/) was used for hyperparameter tuning. The search process included optimization of learning rate, batch size, and number of training epochs. This automated tuning process allowed the model to achieve better performance without manual trial and error.