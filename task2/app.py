
from pathlib import Path
import argparse, json, os, re, sqlite3, sys
os.environ["HF_HUB_OFFLINE"]="1"
os.environ["TRANSFORMERS_OFFLINE"]="1"
import pandas as pd
import numpy as np
import torch
import torch.nn as nn
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

BASE=Path(__file__).resolve().parent

def configure_tk_runtime():
    """Use PyInstaller's collected Tcl/Tk libraries in frozen builds."""
    if getattr(sys,"frozen",False) and getattr(sys,"_MEIPASS",None):
        root=Path(sys._MEIPASS)
        os.environ.setdefault("TCL_LIBRARY",str(root/"_tcl_data"))
        os.environ.setdefault("TK_LIBRARY",str(root/"_tk_data"))
    elif not os.environ.get("TCL_LIBRARY"):
        base_tcl=Path(sys.base_prefix)/"tcl"
        has_tcl=any(base_tcl.glob("tcl*/init.tcl"))
        is_minimal_runtime="codex-runtimes" in str(sys.base_prefix).lower()
        if not has_tcl or is_minimal_runtime:
            # Some embedded Python distributions ship unusable/missing Tcl
            # scripts. Use the bundled 8.6 scripts via short paths from CWD.
            tcl=BASE/"tcl-runtime"/"tcl8.6"
            tk=BASE/"tcl-runtime"/"tk8.6"
            if (tcl/"init.tcl").is_file() and (tk/"tk.tcl").is_file():
                os.environ["TCL_LIBRARY"]=os.path.relpath(tcl,Path.cwd())
                os.environ.setdefault("TK_LIBRARY",os.path.relpath(tk,Path.cwd()))

configure_tk_runtime()

def resource_root():
    """Find a complete model resource tree in source and frozen builds."""
    candidates=[]
    if getattr(sys,"frozen",False) and getattr(sys,"_MEIPASS",None):
        candidates.append(Path(sys._MEIPASS))
    candidates.extend([Path(sys.executable).resolve().parent, BASE])
    seen=set()
    for base in candidates:
        base=base.resolve()
        if base in seen:
            continue
        seen.add(base)
        root=base/"model"
        required=[root/"labels.json",root/"vocab.json",root/"tiny_slm.pt",
                  root/"text-to-sql-small"/"config.json",
                  root/"text-to-sql-small"/"model.safetensors",
                  root/"text-to-sql-small"/"spiece.model"]
        if all(p.is_file() for p in required):
            return root
    checked="; ".join(str(p/"model") for p in candidates)
    raise FileNotFoundError(f"Could not locate complete local model resources. Checked: {checked}")

MODEL_ROOT=resource_root()
MODEL_DIR=MODEL_ROOT/"text-to-sql-small"

class TinySLM(nn.Module):
    """Small local intent classifier used alongside the SQL SLM."""
    def __init__(self,vocab_size,n_classes,d_model=64,heads=4,layers=2,max_len=40):
        super().__init__()
        self.embedding=nn.Embedding(vocab_size,d_model,padding_idx=0)
        self.position=nn.Parameter(torch.zeros(1,max_len,d_model))
        layer=nn.TransformerEncoderLayer(d_model=d_model,nhead=heads,dim_feedforward=128,dropout=.1,batch_first=True,activation="gelu")
        self.encoder=nn.TransformerEncoder(layer,num_layers=layers)
        self.norm=nn.LayerNorm(d_model)
        self.classifier=nn.Linear(d_model,n_classes)
    def forward(self,x):
        pad_mask=x.eq(0)
        h=self.embedding(x)+self.position[:,:x.size(1)]
        h=self.encoder(h,src_key_padding_mask=pad_mask)
        valid=(~pad_mask).unsqueeze(-1)
        pooled=(h*valid).sum(1)/valid.sum(1).clamp_min(1)
        return self.classifier(self.norm(pooled))

INTENTS=("select_all","filter_numeric_gt","filter_numeric_lt","filter_categorical",
         "aggregate_sum_filtered","aggregate_count_filtered","groupby_sum_top1",
         "order_desc_limit","groupby_avg","order_by_date_filtered")

def tokenize(text): return re.findall(r"[A-Za-z0-9_]+|[><=]",text.lower())

class SchemaLinker:
    def __init__(self,schema):
        self.schema=schema
        docs=[f"{x['name']} {x['description']}" for x in schema]
        self.word=TfidfVectorizer(ngram_range=(1,2),analyzer="word")
        self.char=TfidfVectorizer(analyzer="char_wb",ngram_range=(3,5))
        self.word_matrix=self.word.fit_transform(docs)
        self.char_matrix=self.char.fit_transform(docs)
    def match(self,text):
        sw=cosine_similarity(self.word.transform([text]),self.word_matrix)[0]
        sc=cosine_similarity(self.char.transform([text]),self.char_matrix)[0]
        scores=.4*sw+.6*sc
        return sorted([(float(s),self.schema[i]["name"]) for i,s in enumerate(scores)],reverse=True)

def qid(s): return '"' + s.replace('"','""') + '"'
def qlit(s): return "'" + str(s).replace("'","''") + "'"
class TextToSQL:
    def __init__(self,schema,data=None,table=None):
        if not table or not str(table).strip():
            raise ValueError("A runtime table name is required")
        self.schema=schema; self.data=data; self.table=table
        self.linker=SchemaLinker(schema)
        self.columns=[x["name"] for x in schema]
        self.desc={x["name"]:x["description"] for x in schema}
        if len(set(self.columns)) != len(self.columns):
            raise ValueError("Runtime schema contains duplicate column names")
        if self.data is not None:
            missing=[name for name in self.columns if name not in self.data.columns]
            if missing:
                raise ValueError("Runtime CSV is missing schema columns: " + ", ".join(missing))
            # Keep query execution aligned with the caller-supplied schema.
            self.data=self.data.loc[:,self.columns].copy()
        if not MODEL_DIR.is_dir():
            raise FileNotFoundError(f"Local SLM weights are missing: {MODEL_DIR}")
        self.tokenizer=AutoTokenizer.from_pretrained(MODEL_DIR,local_files_only=True,use_fast=False)
        self.model=AutoModelForSeq2SeqLM.from_pretrained(
            MODEL_DIR,local_files_only=True,use_safetensors=True
        )
        self.model.eval()
        self.labels=json.loads((MODEL_ROOT/"labels.json").read_text())
        self.vocab=json.loads((MODEL_ROOT/"vocab.json").read_text())
        self.intent_model=TinySLM(len(self.vocab),len(self.labels))
        self.intent_model.load_state_dict(torch.load(MODEL_ROOT/"tiny_slm.pt",map_location="cpu",weights_only=True))
        self.intent_model.eval()
        self._slm_sql_candidate=""

    def predict_intent(self,q):
        ids=[self.vocab.get(t,1) for t in tokenize(q)][:40]
        ids += [0]*(40-len(ids))
        with torch.no_grad():
            p=torch.softmax(self.intent_model(torch.tensor([ids])),dim=-1)[0]
        i=int(p.argmax())
        intent=self.labels[i]
        if re.search(r"\btop\s+\d+\b",q,re.I) and not re.search(r"\b(?:total|sum|average|mean)\b",q,re.I):
            intent="order_desc_limit"
        return intent,float(p[i])

    def propose_sql(self,q):
        """Run the bundled 60.5M-parameter text-to-SQL SLM locally."""
        columns=[]
        for item in self.schema:
            name=item["name"]
            desc=(name+" "+item["description"]).lower()
            if self.data is not None and name in self.data and pd.api.types.is_numeric_dtype(self.data[name]):
                sql_type="REAL"
            elif re.search(r"\b(date|time|timestamp)\b",desc):
                sql_type="DATE"
            elif re.search(r"\b(amount|price|cost|balance|salary|score|quantity|count|age|charge|speed|number)\b",desc):
                sql_type="REAL"
            else:
                sql_type="TEXT"
            columns.append(qid(name)+" "+sql_type)
        ddl=f"CREATE TABLE {qid(self.table)} ("+", ".join(columns)+")"
        # This is the input format documented by the model author. Runtime
        # descriptions remain available to the separate schema linker.
        prompt=f"{q} | {ddl}"
        encoded=self.tokenizer(prompt,return_tensors="pt",truncation=True,max_length=512)
        with torch.no_grad():
            tokens=self.model.generate(**encoded,max_new_tokens=128,num_beams=1,do_sample=False)
        return self.tokenizer.decode(tokens[0],skip_special_tokens=True).strip()

    def numeric_parts(self,q):
        for pattern,op in [
            (r"\b(?:greater than|more than|above|over|exceeds|higher than)\s+\$?([\d,]+(?:\.\d+)?)",">"),
            (r"\b(?:less than|below|under|lower than)\s+\$?([\d,]+(?:\.\d+)?)","<")
        ]:
            m=re.search(pattern,q,re.I)
            if m:
                n=float(m.group(1).replace(",",""))
                return op,n
        return None,None

    def extract_value(self,q):
        """
        Extract a literal value and infer its runtime schema column.
        Handles exact runtime values, codes, schema-enumerated values,
        and semantic variants such as credited -> Credit.
        """

        ql = q.lower()

        # ----------------------------------------------------
        # 1. Exact values observed in runtime data
        # ----------------------------------------------------
        exact = []

        if self.data is not None:
            for c in self.data.columns:
                for v in self.data[c].dropna().astype(str).unique():
                    if len(v) >= 2 and v.lower() in ql:
                        exact.append((len(v), c, v))

        if exact:
            _, c, v = max(exact)
            return c, v

        # ----------------------------------------------------
        # 2. Code-like values such as BLR001
        # ----------------------------------------------------
        codes = re.findall(
            r"\b[A-Z]{2,8}\d{2,8}\b",
            q
        )

        if codes:
            code = codes[0]
            context = re.sub(
                re.escape(code),
                "",
                q,
                flags=re.I
            )

            matches = self.linker.match(context)

            if matches:
                return matches[0][1], code

            context_tokens = set(
                re.findall(
                    r"[A-Za-z0-9_]+",
                    context.lower()
                )
            )

            for item in self.schema:
                col = item["name"]
                desc = item["description"].lower()

                if any(
                    tok in desc
                    for tok in context_tokens
                    if len(tok) >= 3
                ):
                    return col, code

        # ----------------------------------------------------
        # 3. IMPORTANT:
        #    Resolve semantic variants from schema descriptions.
        #
        #    credited -> Credit
        #    credits  -> Credit
        #    credit   -> Credit
        #    debited  -> Debit
        #    debits   -> Debit
        # ----------------------------------------------------

        semantic_variants = {
            "credit": {
                "credit",
                "credited",
                "credits"
            },
            "debit": {
                "debit",
                "debited",
                "debits"
            }
        }
        generic_type_words={"date","time","timestamp","day","month","year","identifier","id","number","numeric","text","string","boolean","currency"}

        for item in self.schema:

            col = item["name"]
            desc = item["description"]

            # Find explicitly enumerated/capitalized values
            # in the schema description.
            desc_values = re.findall(
                r"\b[A-Z][A-Za-z0-9_-]*\b",
                desc
            )

            for schema_value in desc_values:

                key = schema_value.lower()
                # Capitalization at the start of a sentence does not make a
                # datatype/field-description word a categorical runtime value.
                if key in generic_type_words:
                    continue

                variants = semantic_variants.get(
                    key,
                    {key}
                )

                for variant in variants:

                    if re.search(
                        r"\b" + re.escape(variant) + r"\b",
                        ql,
                        re.I
                    ):
                        return col, schema_value

        # ----------------------------------------------------
        # 4. Direct semantic fallback.
        #
        # This specifically handles schemas whose descriptions
        # contain Credit/Debit even if capitalization or wording
        # differs.
        # ----------------------------------------------------

        if re.search(
            r"\b(?:credit|credited|credits)\b",
            ql,
            re.I
        ):

            for item in self.schema:

                desc = item["description"].lower()

                if "credit" in desc:
                    return item["name"], "Credit"

        if re.search(
            r"\b(?:debit|debited|debits)\b",
            ql,
            re.I
        ):

            for item in self.schema:

                desc = item["description"].lower()

                if "debit" in desc:
                    return item["name"], "Debit"

        # ----------------------------------------------------
        # 5. Description-token matching
        # ----------------------------------------------------

        stop = {
            "show",
            "list",
            "all",
            "records",
            "record",
            "rows",
            "row",
            "where",
            "what",
            "which",
            "how",
            "many",
            "are",
            "is",
            "the",
            "for",
            "each",
            "with",
            "through",
            "using",
            "at",
            "by",
            "of",
            "from",
            "done",
            "happened",
            "there",
            "highest",
            "lowest",
            "total",
            "amount",
            "average",
            "avg",
            "sum",
            "count",
            "top",
            "value",
            "values",
            "below",
            "above",
            "greater",
            "less",
            "than",
            "sorted",
            "sort",
            "date",
            "and",
            "or",
            "to",
            "has",
            "have",
            "did"
        }

        q_tokens = set(
            re.findall(
                r"[A-Za-z0-9_]+",
                ql
            )
        )

        candidates = []

        for item in self.schema:

            col = item["name"]
            desc = item["description"]

            desc_tokens = set(
                re.findall(
                    r"[A-Za-z0-9_]+",
                    desc.lower()
                )
            )

            for tok in q_tokens - stop:

                if len(tok) < 2:
                    continue

                if (
                    tok in desc_tokens
                    and tok not in set(
                        re.findall(
                            r"[A-Za-z0-9_]+",
                            col.lower()
                        )
                    )
                ):
                    candidates.append(
                        (tok, col)
                    )

        if candidates:

            tok, col = max(
                candidates,
                key=lambda x: len(x[0])
            )

            original = re.search(
                r"\b" + re.escape(tok) + r"\b",
                q,
                re.I
            )

            return (
                col,
                original.group(0)
                if original
                else tok
            )

        # ----------------------------------------------------
        # 6. Quoted literals
        # ----------------------------------------------------

        quoted = re.findall(
            r"['\"]([^'\"]+)['\"]",
            q
        )

        if quoted:

            value = quoted[0]
            matches = self.linker.match(q)

            if matches:
                return matches[0][1], value

        return None, None

    def numeric_column(self,q):
        """Choose the most likely numeric metric using runtime schema text."""
        ql=q.lower()
        numeric_terms={"amount","price","cost","value","balance","total","score","quantity","revenue","salary","rate","age","count","days","years","speed","mbps","stock","charge","number","population","percent","percentage","distance"}
        ranked=[]
        for score,col in self.linker.match(q):
            text=(col+" "+self.desc[col]).lower()
            # Avoid identifiers/codes/categories even when their descriptions
            # contain generic words like "number" or "transaction".
            if re.search(r"(^|_)(id|number|code)$", col.lower()):
                continue
            semantic=sum(1 for term in numeric_terms if term in text)
            observed_numeric=(self.data is not None and col in self.data.columns
                              and pd.api.types.is_numeric_dtype(self.data[col]))
            if semantic==0 and not observed_numeric:
                continue
            direct=sum(1 for term in numeric_terms if re.search(r"\b"+re.escape(term)+r"\b",ql) and re.search(r"\b"+re.escape(term)+r"\b",text))
            synonym_bonus=0
            # "value" is a common natural-language synonym for a monetary
            # measure even when the schema calls it amount/price/cost.
            if re.search(r"\bvalue\b",ql) and re.search(r"\b(amount|price|cost)\b",text):
                synonym_bonus=2
            synonym_pairs={
                "expensive":("price","cost","amount","salary"),
                "cheapest":("price","cost","amount"),
                "cheap":("price","cost","amount"),
                "highest":("amount","price","cost","salary","balance","score","quantity"),
                "lowest":("amount","price","cost","salary","balance","score","quantity"),
            }
            synonym_score=sum(1.0 for phrase,terms in synonym_pairs.items()
                              if re.search(r"\b"+phrase+r"\b",ql)
                              and any(re.search(r"\b"+term+r"\b",text) for term in terms))
            model_hint=1.5 if re.search(r"\b"+re.escape(col)+r"\b",self._slm_sql_candidate,re.I) else 0.0
            ranked.append((score + .2*semantic + .6*direct + .8*synonym_bonus + synonym_score + model_hint,col))
        if ranked:
            return max(ranked,key=lambda x:x[0])[1]
        return self.linker.match(q)[0][1]

    def categorical_column(self,q):
        categorical_terms={
            "category","type","status","mode","method","name","code",
            "class","group","region","city","country","department","plan"
        }
        ranked=[]
        for score,col in self.linker.match(q):
            text=(col+" "+self.desc[col]).lower()
            bonus=sum(1 for term in categorical_terms if term in text)
            ranked.append((score+0.15*bonus,col))
        return max(ranked,key=lambda x:x[0])[1]

    def render(self,q,intent):
        if intent=="select_all":
            c,v=self.extract_value(q)
            if c and v:
                return f"SELECT * FROM {qid(self.table)} WHERE {qid(c)} = {qlit(v)};"
            return f"SELECT * FROM {qid(self.table)};"

        if intent in ("filter_numeric_gt","filter_numeric_lt"):
            op,num=self.numeric_parts(q)
            if op is None:
                raise ValueError("Could not identify the numeric comparison")
            m=re.search(r"\b(?:greater than|more than|above|over|exceeds|higher than|less than|below|under|lower than)\b",q,re.I)
            phrase=q[:m.start()] if m else q
            col=self.numeric_column(phrase)
            val=int(num) if float(num).is_integer() else num
            return f"SELECT * FROM {qid(self.table)} WHERE {qid(col)} {op} {val};"

        if intent=="filter_categorical":
            col,val=self.extract_value(q)
            if col is None:
                col=self.categorical_column(q)
                # A generic fallback: take a quoted literal if available.
                quoted=re.findall(r"['\"]([^'\"]+)['\"]",q)
                if not quoted:
                    raise ValueError("Could not identify a categorical value")
                val=quoted[0]
            return f"SELECT * FROM {qid(self.table)} WHERE {qid(col)} = {qlit(val)};"

        if intent=="aggregate_sum_filtered":
            metric=self.numeric_column(q)
            fcol,val=self.extract_value(q)
            if fcol is None:
                raise ValueError("Could not identify the filter value/column")
            return f"SELECT SUM({qid(metric)}) AS total_sum FROM {qid(self.table)} WHERE {qid(fcol)} = {qlit(val)};"

        if intent=="aggregate_count_filtered":
            fcol,val=self.extract_value(q)
            if fcol is None:
                # Try a context phrase around common value markers.
                fcol=self.categorical_column(q)
                quoted=re.findall(r"['\"]([^'\"]+)['\"]",q)
                if not quoted:
                    raise ValueError("Could not identify the filter value/column")
                val=quoted[0]
            return f"SELECT COUNT(*) AS count FROM {qid(self.table)} WHERE {qid(fcol)} = {qlit(val)};"

        if intent=="groupby_sum_top1":
            m=re.search(r"(?:which|what)\s+(.+?)\s+has\s+(?:the\s+)?(?:highest|largest|most)",q,re.I)
            group_text=m.group(1) if m else q
            group=self.categorical_column(group_text)
            metric=self.numeric_column(q)
            return f"SELECT {qid(group)}, SUM({qid(metric)}) AS total_sum FROM {qid(self.table)} GROUP BY {qid(group)} ORDER BY total_sum DESC LIMIT 1;"

        if intent=="order_desc_limit":
            m=re.search(r"\btop\s+(\d+)",q,re.I)
            n=int(m.group(1)) if m else 5
            metric=self.numeric_column(q)
            return f"SELECT * FROM {qid(self.table)} ORDER BY {qid(metric)} DESC LIMIT {n};"

        if intent=="groupby_avg":
            m=re.search(r"(?:for each|by|grouped by)\s+(.+?)(?:$|\.)",q,re.I)
            group=self.categorical_column(m.group(1).strip() if m else q)
            metric=self.numeric_column(q)
            return f"SELECT {qid(group)}, AVG({qid(metric)}) AS avg_value FROM {qid(self.table)} GROUP BY {qid(group)};"

        if intent=="order_by_date_filtered":
            fcol,val=self.extract_value(q)
            if fcol is None:
                raise ValueError("Could not identify the filter value/column")
            date_candidates=[(s,c) for s,c in self.linker.match("date time when occurred")
                             if re.search(r"\b(date|time|timestamp)\b",(c+" "+self.desc[c]).lower())]
            if not date_candidates:
                raise ValueError("No date/time column is present in the supplied schema")
            date=date_candidates[0][1]
            return f"SELECT * FROM {qid(self.table)} WHERE {qid(fcol)} = {qlit(val)} ORDER BY {qid(date)};"

        raise ValueError("Unsupported intent: "+intent)

    def generate(self,q):
        if re.search(r"\b(delete|drop|update|insert|create|alter|truncate|replace|join|union)\b",q,re.I):
            raise ValueError("Destructive or unsupported operation requested; only supported read-only single-table queries are allowed")
        generic_all=bool(re.search(r"\b(?:all|everything|entire)\b",q,re.I)
                         and re.search(r"\b(?:rows|records|data|table)\b",q,re.I))
        stop_words={"what","which","how","many","show","list","me","all","the","is","are","was","were",
                    "for","each","in","on","to","from","with","where","by","and","or","of","through",
                    "using","made","done","happened","sorted","sort","top","highest","lowest","value",
                    "average","mean","sum","total","count","rows","records","data","table","please"}
        def stem(word):
            if len(word)>5 and word.endswith("ies"): return word[:-3]+"y"
            if len(word)>4 and word.endswith("s"): return word[:-1]
            return word
        q_terms={stem(t) for t in re.findall(r"[A-Za-z0-9_]+",q.lower()) if t not in stop_words}
        schema_terms={stem(t) for item in self.schema
                      for t in re.findall(r"[A-Za-z0-9_]+",(item["name"]+" "+item["description"]).lower())}
        if not (q_terms & schema_terms) and not generic_all:
            raise ValueError("This question does not appear to refer to the supplied schema. Ask about one of its columns or values.")
        proposal=self.propose_sql(q)
        self._slm_sql_candidate=proposal
        intent,confidence=self.predict_intent(q)
        planned_sql=self.render(q,intent)
        self.validate_sql(planned_sql)
        sql=planned_sql
        accepted=False
        # Accept generated SQL only when it passes the same allowlist/parser
        # checks and produces the same result as the schema-linked plan on the
        # optional local CSV. Without data to compare, return the guarded plan.
        candidate=self.quote_known_identifiers(proposal)
        if self.data is not None:
            try:
                self.validate_sql(candidate)
                accepted=self.same_results(candidate,planned_sql)
                if accepted:
                    sql=candidate
            except (ValueError,sqlite3.Error):
                accepted=False
        return {"intent":intent,"intent_confidence":confidence,"slm_candidate":proposal,
                "slm_candidate_accepted":accepted,"sql_source":"local SLM" if accepted else "guarded schema-linked plan",
                "sql":sql}

    def quote_known_identifiers(self,sql):
        """Quote runtime schema identifiers in a model proposal before parsing."""
        result=sql
        for identifier in sorted(set(self.columns+[self.table]),key=len,reverse=True):
            pattern=r"(?<![\w\"'])"+re.escape(identifier)+r"(?![\w\"'])"
            result=re.sub(pattern,lambda _m:qid(identifier),result,flags=re.I)
        return result

    def same_results(self,first,second):
        con=sqlite3.connect(":memory:")
        try:
            self.data.to_sql(self.table,con,index=False,if_exists="replace")
            a=pd.read_sql_query(first,con)
            b=pd.read_sql_query(second,con)
        finally:
            con.close()
        if a.shape!=b.shape:
            return False
        for col in range(a.shape[1]):
            av,bv=a.iloc[:,col],b.iloc[:,col]
            if pd.api.types.is_numeric_dtype(av) and pd.api.types.is_numeric_dtype(bv):
                if not np.allclose(av.to_numpy(),bv.to_numpy(),equal_nan=True):
                    return False
            elif not av.astype(str).reset_index(drop=True).equals(bv.astype(str).reset_index(drop=True)):
                return False
        return True

    def validate_sql(self, sql):
        """Reject non-SELECT or out-of-schema SQL before returning a query."""
        if not isinstance(sql, str) or not sql.strip():
            raise ValueError("Generated SQL is empty")
        statement=sql.strip().rstrip(";").strip()
        if ";" in statement or not re.match(r"(?is)^SELECT\b", statement):
            raise ValueError("Only one SELECT statement is supported")
        if re.search(r"(?i)\b(insert|update|delete|drop|alter|create|replace|attach|detach|pragma|vacuum|into|union|join)\b", statement):
            raise ValueError("Unsupported or destructive SQL operation")
        if len(re.findall(r"(?i)\bSELECT\b",statement))!=1 or len(re.findall(r"(?i)\bFROM\b",statement))!=1:
            raise ValueError("Only a single-table SELECT is supported")
        quoted=re.findall(r'"((?:[^"]|"")+)"', statement)
        allowed=set(self.columns)|{self.table}
        unknown=[x.replace('""','"') for x in quoted if x.replace('""','"') not in allowed]
        if unknown:
            raise ValueError("SQL references identifiers outside the supplied schema: "+", ".join(unknown))
        if ("FROM "+qid(self.table)).casefold() not in statement.casefold():
            # The generator always quotes the table; this also rejects a query
            # that silently switches to a different source.
            raise ValueError("SQL must reference the supplied table")
        # Parse syntax using SQLite without executing against user data.
        con=sqlite3.connect(":memory:")
        try:
            defs=", ".join(qid(c)+" TEXT" for c in self.columns)
            con.execute("CREATE TABLE "+qid(self.table)+" ("+defs+")")
            con.execute("EXPLAIN "+statement)
        except sqlite3.Error as exc:
            raise ValueError("Generated SQL failed validation: "+str(exc)) from exc
        finally:
            con.close()

def load_schema(path):
    return json.loads(Path(path).read_text())

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--schema",default=None)
    p.add_argument("--csv",default=None)
    p.add_argument("--table",default=None)
    p.add_argument("--question",default=None)
    a=p.parse_args()
    if not a.schema and not a.table and not a.csv and not a.question:
        if getattr(sys,"frozen",False) and sys.platform=="win32":
            try:
                import ctypes
                console=ctypes.windll.kernel32.GetConsoleWindow()
                attached=(ctypes.c_ulong*16)()
                count=ctypes.windll.kernel32.GetConsoleProcessList(attached,16)
                # Do not hide a PowerShell/CMD console shared with the caller.
                if console and count<=1:
                    ctypes.windll.user32.ShowWindow(console,0)
            except Exception:
                pass
        from gui import launch_gui
        launch_gui()
        return
    if not a.schema or not a.table:
        p.error("CLI mode requires --schema and --table; omit all options to open the desktop interface")
    schema=load_schema(a.schema)
    data=pd.read_csv(a.csv) if a.csv else None
    bot=TextToSQL(schema,data,a.table)
    if a.question:
        r=bot.generate(a.question)
        print(r["sql"])
        print(f"intent={r['intent']} classifier_confidence={r['intent_confidence']:.3f}")
        print(f"local_t5_candidate={r['slm_candidate']}")
        return
    print("Offline Text-to-SQL chatbot. Type exit to quit.")
    while True:
        q=input("\nYou: ").strip()
        if q.lower() in {"exit","quit"}: break
        try:
            r=bot.generate(q)
            print("SQL:",r["sql"])
            print(f"Intent: {r['intent']} | Local T5 candidate: {r['slm_candidate']}")
        except Exception as e:
            print("Error:",e)

if __name__=="__main__":
    main()
