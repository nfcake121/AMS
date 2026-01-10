from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, List, Tuple, Optional

import torch
from transformers import AutoTokenizer, AutoModelForTokenClassification


# Простая токенизация, похожая на твою разметку датасета:
# числа, слова, отдельные знаки препинания.
_TOKEN_RE = re.compile(r"\d+(?:[.,]\d+)?|[A-Za-zА-Яа-яЁё]+|[^\w\s]", re.UNICODE)


def basic_tokenize(text: str) -> List[str]:
    return _TOKEN_RE.findall(text)


@dataclass
class NEROutput:
    tokens: List[str]
    tags: List[str]
    entities: Dict[str, List[str]]


@lru_cache(maxsize=4)
def _load(model_dir: str):
    tok = AutoTokenizer.from_pretrained(model_dir)
    model = AutoModelForTokenClassification.from_pretrained(model_dir)
    model.eval()
    return tok, model


def _bio_to_entities(tokens: List[str], tags: List[str]) -> Dict[str, List[str]]:
    entities: Dict[str, List[str]] = {}
    cur_type: Optional[str] = None
    cur_tokens: List[str] = []

    def flush():
        nonlocal cur_type, cur_tokens
        if cur_type and cur_tokens:
            entities.setdefault(cur_type, []).append(" ".join(cur_tokens))
        cur_type = None
        cur_tokens = []

    for tok, tag in zip(tokens, tags):
        if tag.startswith("B-"):
            flush()
            cur_type = tag[2:]
            cur_tokens = [tok]
        elif tag.startswith("I-") and cur_type == tag[2:]:
            cur_tokens.append(tok)
        else:
            flush()

    flush()
    return entities


def predict(text: str, model_dir: str, max_len: int = 128, device: Optional[str] = None) -> NEROutput:
    tokenizer, model = _load(model_dir)

    words = basic_tokenize(text)

    enc = tokenizer(
        words,
        is_split_into_words=True,
        return_tensors="pt",
        truncation=True,
        max_length=max_len,
    )

    # ВАЖНО: word_ids берём ДО переноса на device и ДО любых преобразований
    if hasattr(enc, "word_ids"):
        word_ids = enc.word_ids(batch_index=0)
    else:
        raise RuntimeError(
            "Tokenizer returned a plain dict without word_ids(). "
            "Ensure you are using a fast tokenizer or keep BatchEncoding object."
        )

    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"

    model.to(device)

    # переносим тензоры, но НЕ затираем enc целиком
    enc_on_device = {k: v.to(device) for k, v in enc.items()}

    with torch.no_grad():
        logits = model(**enc_on_device).logits

    pred_ids = torch.argmax(logits, dim=-1)[0].tolist()
    id2label = model.config.id2label

    word_tags: List[str] = ["O"] * len(words)
    used = set()
    for i, w_id in enumerate(word_ids):
        if w_id is None:
            continue
        if w_id in used:
            continue
        used.add(w_id)
        word_tags[w_id] = id2label[pred_ids[i]]

    entities = _bio_to_entities(words, word_tags)
    return NEROutput(tokens=words, tags=word_tags, entities=entities)

