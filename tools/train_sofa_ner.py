from __future__ import annotations
import json
import random
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
from datasets import Dataset
from transformers import (
    AutoTokenizer,
    AutoModelForTokenClassification,
    DataCollatorForTokenClassification,
    TrainingArguments,
    Trainer,
)
from seqeval.metrics import f1_score, precision_score, recall_score, classification_report


# ----------------------------
# Config
# ----------------------------
RANDOM_SEED = 42

# стабильная, хорошая стартовая RU-модель для NER
DEFAULT_MODEL_NAME = "DeepPavlov/rubert-base-cased"


def read_jsonl(path: str) -> List[Dict]:
    items = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            items.append(json.loads(line))
    return items


def build_label_list(items: List[Dict]) -> List[str]:
    # собираем список всех тегов, чтобы label2id/id2label были стабильны
    labels = set()
    for it in items:
        for t in it["tags"]:
            labels.add(t)
    # важно: O первым
    labels = sorted(labels)
    if "O" in labels:
        labels.remove("O")
    return ["O"] + labels


def split_items(items: List[Dict], train_ratio=0.9) -> Tuple[List[Dict], List[Dict]]:
    random.shuffle(items)
    n_train = int(len(items) * train_ratio)
    return items[:n_train], items[n_train:]


def align_labels_with_tokens(tokenizer, tokens: List[str], tags: List[str], label2id: Dict[str, int], max_length: int):
    # токенизация по словам + alignment
    enc = tokenizer(
        tokens,
        is_split_into_words=True,
        truncation=True,
        max_length=max_length,
    )
    word_ids = enc.word_ids()
    label_ids = []
    prev_word_id = None

    for word_id in word_ids:
        if word_id is None:
            label_ids.append(-100)
        elif word_id != prev_word_id:
            label_ids.append(label2id[tags[word_id]])
        else:
            # если токен является продолжением слова:
            # B-XXX -> I-XXX, иначе остаётся как есть
            tag = tags[word_id]
            if tag.startswith("B-"):
                tag = "I-" + tag[2:]
                tag = tag if tag in label2id else tags[word_id]
            label_ids.append(label2id[tag])
        prev_word_id = word_id

    enc["labels"] = label_ids
    return enc


def compute_metrics_builder(id2label: Dict[int, str]):
    def compute_metrics(eval_pred):
        logits, labels = eval_pred
        preds = np.argmax(logits, axis=-1)

        true_labels = []
        true_preds = []

        for pred_row, label_row in zip(preds, labels):
            seq_true = []
            seq_pred = []
            for p, l in zip(pred_row, label_row):
                if l == -100:
                    continue
                seq_true.append(id2label[int(l)])
                seq_pred.append(id2label[int(p)])
            true_labels.append(seq_true)
            true_preds.append(seq_pred)

        return {
            "precision": precision_score(true_labels, true_preds),
            "recall": recall_score(true_labels, true_preds),
            "f1": f1_score(true_labels, true_preds),
        }
    return compute_metrics


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=str, default="data/sofa_ner_train.jsonl")
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL_NAME)
    parser.add_argument("--out", type=str, default="models/sofa_ner_rubert")
    parser.add_argument("--max_len", type=int, default=192)
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--lr", type=float, default=3e-5)
    args = parser.parse_args()

    random.seed(RANDOM_SEED)
    np.random.seed(RANDOM_SEED)

    items = read_jsonl(args.data)
    if not items:
        raise RuntimeError("Dataset is empty")

    labels = build_label_list(items)
    label2id = {l: i for i, l in enumerate(labels)}
    id2label = {i: l for l, i in label2id.items()}

    train_items, val_items = split_items(items, train_ratio=0.9)

    tokenizer = AutoTokenizer.from_pretrained(args.model)

    def to_features(item):
        return align_labels_with_tokens(
            tokenizer,
            item["tokens"],
            item["tags"],
            label2id=label2id,
            max_length=args.max_len,
        )

    train_ds = Dataset.from_list(train_items).map(to_features, remove_columns=["tokens", "tags"])
    val_ds = Dataset.from_list(val_items).map(to_features, remove_columns=["tokens", "tags"])

    model = AutoModelForTokenClassification.from_pretrained(
        args.model,
        num_labels=len(labels),
        id2label=id2label,
        label2id=label2id,
    )

    collator = DataCollatorForTokenClassification(tokenizer)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    training_args = TrainingArguments(
    output_dir=str(out_dir),
    eval_strategy="epoch",
    save_strategy="epoch",
        learning_rate=args.lr,
        per_device_train_batch_size=args.batch,
        per_device_eval_batch_size=args.batch,
        num_train_epochs=args.epochs,
        weight_decay=0.01,
        logging_steps=100,
        report_to="none",
        fp16=True,  # на RTX 5070 обычно ок
        seed=RANDOM_SEED,
        save_total_limit=2,
        load_best_model_at_end=True,
        metric_for_best_model="f1",
        greater_is_better=True,
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        tokenizer=tokenizer,
        data_collator=collator,
        compute_metrics=compute_metrics_builder(id2label),
    )

    trainer.train()

    # финальная оценка + отчёт
    preds = trainer.predict(val_ds)
    logits, labels_ids = preds.predictions, preds.label_ids
    preds_ids = np.argmax(logits, axis=-1)

    true_labels = []
    true_preds = []
    for pr, lb in zip(preds_ids, labels_ids):
        seq_true = []
        seq_pred = []
        for p, l in zip(pr, lb):
            if l == -100:
                continue
            seq_true.append(id2label[int(l)])
            seq_pred.append(id2label[int(p)])
        true_labels.append(seq_true)
        true_preds.append(seq_pred)

    print("\n=== SeqEval report (VAL) ===")
    print(classification_report(true_labels, true_preds))

    # сохраняем модель
    trainer.save_model(str(out_dir))
    tokenizer.save_pretrained(str(out_dir))
    print(f"\n✅ Saved model to: {out_dir.resolve()}")


if __name__ == "__main__":
    main()
