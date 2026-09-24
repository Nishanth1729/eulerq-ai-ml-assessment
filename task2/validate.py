from pathlib import Path
import json, sqlite3, pandas as pd, numpy as np
from app import TextToSQL, load_schema
BASE=Path(__file__).resolve().parent
DATA=BASE.parent/"data"/"task2_bank_transactions_sample.csv"
QUESTIONS=['Show me all transactions where the amount is greater than 50000.', 'List all UPI transactions.', 'What is the total amount credited across all transactions?', 'How many debit transactions are there?', 'Which merchant category has the highest total transaction amount?', 'Show the top 5 highest value transactions.', 'What is the average transaction amount for each payment mode?', 'List all transactions where the balance after the transaction is below 50000.', 'How many transactions happened at branch BLR001?', 'List all transactions done through Cheque, sorted by date.']
EXPECTED=['SELECT * FROM transactions WHERE amount > 50000;', "SELECT * FROM transactions WHERE payment_mode = 'UPI';", "SELECT SUM(amount) AS total_credited FROM transactions WHERE transaction_type = 'Credit';", "SELECT COUNT(*) AS debit_count FROM transactions WHERE transaction_type = 'Debit';", 'SELECT merchant_category, SUM(amount) AS total_amount FROM transactions GROUP BY merchant_category ORDER BY total_amount DESC LIMIT 1;', 'SELECT * FROM transactions ORDER BY amount DESC LIMIT 5;', 'SELECT payment_mode, AVG(amount) AS avg_amount FROM transactions GROUP BY payment_mode;', 'SELECT * FROM transactions WHERE balance_after_transaction < 50000;', "SELECT COUNT(*) AS txn_count FROM transactions WHERE branch_code = 'BLR001';", "SELECT * FROM transactions WHERE payment_mode = 'Cheque' ORDER BY transaction_date;"]
data=pd.read_csv(DATA)
bot=TextToSQL(load_schema(BASE/"schema.json"),data,"transactions")
con=sqlite3.connect(":memory:")
data.to_sql("transactions",con,index=False,if_exists="replace")
rows=[]
for i,(q,exp) in enumerate(zip(QUESTIONS,EXPECTED),1):
    r=bot.generate(q)
    a=pd.read_sql_query(r["sql"],con); b=pd.read_sql_query(exp,con)
    # Compare result shape and values positionally. SQL aliases are allowed to
    # differ because the assessment requires semantic equivalence, not identical
    # SQL text or identical output column labels.
    if a.shape != b.shape:
        same = False
    else:
        aa = a.reset_index(drop=True)
        bb = b.reset_index(drop=True)
        same = True
        for j in range(a.shape[1]):
            if pd.api.types.is_numeric_dtype(aa.iloc[:,j]) and pd.api.types.is_numeric_dtype(bb.iloc[:,j]):
                if not np.allclose(aa.iloc[:,j].to_numpy(), bb.iloc[:,j].to_numpy(), equal_nan=True):
                    same = False
                    break
            elif not aa.iloc[:,j].astype(str).equals(bb.iloc[:,j].astype(str)):
                same = False
                break
    actual_json=json.dumps(a.to_dict(orient="records"),ensure_ascii=False,default=str)
    expected_json=json.dumps(b.to_dict(orient="records"),ensure_ascii=False,default=str)
    rows.append([i,q,r["intent"],round(r["intent_confidence"],4),r["slm_candidate"],
                 r["slm_candidate_accepted"],r["sql_source"],r["sql"],exp,
                 len(a),len(b),actual_json,expected_json,bool(same)])
out=pd.DataFrame(rows,columns=["question_no","question","intent","intent_confidence","slm_candidate",
    "slm_candidate_accepted","sql_source","generated_sql","expected_sql","generated_rows",
    "expected_rows","execution_result_generated","execution_result_expected","semantic_match"])
out.to_csv(BASE/"validation_results.csv",index=False)
print(out[["question_no","intent","slm_candidate_accepted","semantic_match","generated_sql"]].to_string(index=False))
print(f"\nPassed: {int(out.semantic_match.sum())}/{len(out)}")
lines=["# Task 2 Validation Transcript", "", "Both generated and expected SQL were executed against the supplied 50-row CSV loaded into in-memory SQLite. Semantic matching compares result shapes and all positional cell values; SQL text and aliases need not match.", ""]
for row in rows:
    no,q,intent,conf,candidate,accepted,source,sql,expected,na,nb,actual_json,expected_json,passed=row
    actual_preview=json.dumps(json.loads(actual_json)[:5],ensure_ascii=False)
    expected_preview=json.dumps(json.loads(expected_json)[:5],ensure_ascii=False)
    lines.extend([f"## Question {no}", "", q, "", f"Intent: `{intent}` (auxiliary classifier score {conf:.4f})",
        f"Local SLM proposal accepted: **{accepted}**", "", "Generated SQL:", "```sql", sql, "```", "",
        "Expected SQL:", "```sql", expected, "```", "", f"Execution: generated rows={na}; expected rows={nb}; semantic match: **{'PASS' if passed else 'FAIL'}**.",
        f"Generated result (first 5 rows): `{actual_preview}`", f"Expected result (first 5 rows): `{expected_preview}`", ""])
lines.append(f"Overall: **{int(out.semantic_match.sum())}/{len(out)} PASS**")
(BASE/"validation_transcript.md").write_text("\n".join(lines),encoding="utf-8")
