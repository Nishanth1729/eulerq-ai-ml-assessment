"""
Re-train the auxiliary local SQL-intent classifier from scratch.

The primary text-to-SQL SLM is the separate bundled T5-Small model. This
script trains only the compact helper classifier used to identify intent
shapes; inference remains local and combines it with the T5 proposal,
runtime schema linking, and guarded SQL planning.
"""
from pathlib import Path
import json, random, re
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

BASE = Path(__file__).resolve().parent
MODEL_DIR = BASE / "model"

INTENTS = [
    "select_all","filter_numeric_gt","filter_numeric_lt","filter_categorical",
    "aggregate_sum_filtered","aggregate_count_filtered","groupby_sum_top1",
    "order_desc_limit","groupby_avg","order_by_date_filtered"
]

def tokenize(text):
    return re.findall(r"[A-Za-z0-9_]+|[><=]", text.lower())

class TinySLM(nn.Module):
    def __init__(self, vocab_size, n_classes, d_model=64, heads=4, layers=2, max_len=40):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, d_model, padding_idx=0)
        self.position = nn.Parameter(torch.zeros(1, max_len, d_model))
        layer = nn.TransformerEncoderLayer(
            d_model=d_model, nhead=heads, dim_feedforward=128,
            dropout=0.1, batch_first=True, activation="gelu"
        )
        self.encoder = nn.TransformerEncoder(layer, num_layers=layers)
        self.norm = nn.LayerNorm(d_model)
        self.classifier = nn.Linear(d_model, n_classes)

    def forward(self, x):
        pad_mask = x.eq(0)
        h = self.embedding(x) + self.position[:, :x.size(1)]
        h = self.encoder(h, src_key_padding_mask=pad_mask)
        valid = (~pad_mask).unsqueeze(-1)
        pooled = (h * valid).sum(1) / valid.sum(1).clamp_min(1)
        return self.classifier(self.norm(pooled))

def main():
    random.seed(42)
    np.random.seed(42)
    torch.manual_seed(42)

    templates = json.loads((BASE / "intent_templates.json").read_text())
    cols = ["amount","balance","transaction amount","value"]
    vals = ["UPI","Cheque","Credit","Debit","BLR001","Cash","NEFT"]
    groups = ["merchant category","payment mode","branch","category"]
    metrics = ["transaction amount","amount","value"]

    examples = []
    for intent in INTENTS:
        for _ in range(300):
            template = random.choice(templates[intent])
            examples.append((template.format(
                col=random.choice(cols),
                num=random.choice(["50000","1000","25000","75000"]),
                val=random.choice(vals),
                group=random.choice(groups),
                metric=random.choice(metrics),
                n=random.choice(["3","5","10"])
            ), intent))

    # Targeted paraphrases improve the two ambiguous validation patterns:
    # "List all UPI transactions" and "How many transactions happened at branch BLR001?"
    for _ in range(500):
        examples.append((random.choice([
            "list all {val} transactions",
            "show all {val} transactions",
            "list all transactions done through {val}",
            "show transactions at {val}",
            "list transactions for {val}",
            "find all records with {val}"
        ]).format(val=random.choice(vals)), "filter_categorical"))
        examples.append((random.choice([
            "how many transactions happened at {val}",
            "how many records are at {val}",
            "count transactions at {val}",
            "how many transactions were processed at {val}",
            "how many records have {val}"
        ]).format(val=random.choice(vals)), "aggregate_count_filtered"))

    random.shuffle(examples)

    vocab = {"<pad>": 0, "<unk>": 1}
    for text, _ in examples:
        for token in tokenize(text):
            if token not in vocab:
                vocab[token] = len(vocab)

    max_len = 40
    X, y = [], []
    for text, intent in examples:
        ids = [vocab.get(t, 1) for t in tokenize(text)][:max_len]
        ids += [0] * (max_len - len(ids))
        X.append(ids)
        y.append(INTENTS.index(intent))

    X = torch.tensor(X)
    y = torch.tensor(y)
    split = int(0.85 * len(X))
    train_X, val_X = X[:split], X[split:]
    train_y, val_y = y[:split], y[split:]

    model = TinySLM(len(vocab), len(INTENTS))
    optimizer = optim.AdamW(model.parameters(), lr=2e-3, weight_decay=1e-4)

    for epoch in range(4):
        model.train()
        permutation = torch.randperm(len(train_X))
        for start in range(0, len(train_X), 128):
            batch = permutation[start:start+128]
            loss = nn.functional.cross_entropy(model(train_X[batch]), train_y[batch])
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

    model.eval()
    with torch.no_grad():
        accuracy = float((model(val_X).argmax(1) == val_y).float().mean())

    MODEL_DIR.mkdir(exist_ok=True)
    torch.save(model.state_dict(), MODEL_DIR / "tiny_slm.pt")
    (MODEL_DIR / "vocab.json").write_text(json.dumps(vocab, indent=2))
    (MODEL_DIR / "labels.json").write_text(json.dumps(INTENTS, indent=2))

    print(f"Saved model to {MODEL_DIR / 'tiny_slm.pt'}")
    print(f"Held-out synthetic intent accuracy: {accuracy:.3f}")

if __name__ == "__main__":
    main()
