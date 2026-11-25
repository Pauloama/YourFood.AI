"""Sentiment classifier model module for ABSA pipeline.

Aspect-conditioned sequence classification using BERTimbau
(neuralmind/bert-base-portuguese-cased).
Uses sentence pairs: [CLS] review_text [SEP] aspect_name [SEP].
Outputs 3 classes: positivo, negativo, neutro.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset
from transformers import (
    AutoConfig,
    AutoModelForSequenceClassification,
    AutoTokenizer,
    PreTrainedTokenizerBase,
)

from ..logging_config import get_logger
from ..metrics import compute_sentiment_metrics
from ..taxonomy import Taxonomy, get_taxonomy

logger = get_logger(__name__)


class SentimentDataset(Dataset):
    """PyTorch Dataset for aspect-conditioned sentiment classification."""

    def __init__(
        self,
        texts: list[str],
        aspects: list[str],
        labels: list[int] | np.ndarray | None,
        tokenizer: PreTrainedTokenizerBase,
        max_length: int = 128,
    ) -> None:
        self.texts = texts
        self.aspects = aspects
        self.labels = labels
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self) -> int:
        return len(self.texts)

    def __getitem__(self, idx: int) -> dict[str, torch.Tensor]:
        text = str(self.texts[idx])
        aspect = str(self.aspects[idx])

        # Sentence pair: text + aspect
        encoding = self.tokenizer(
            text=text,
            text_pair=aspect,
            truncation=True,
            max_length=self.max_length,
            padding="max_length",
            return_tensors="pt",
        )

        item = {
            "input_ids": encoding["input_ids"].squeeze(0),
            "attention_mask": encoding["attention_mask"].squeeze(0),
        }
        if "token_type_ids" in encoding:
            item["token_type_ids"] = encoding["token_type_ids"].squeeze(0)

        if self.labels is not None:
            item["labels"] = torch.tensor(self.labels[idx], dtype=torch.long)

        return item


class SentimentClassifier(nn.Module):
    """Aspect-conditioned sentiment classifier based on BERTimbau."""

    def __init__(
        self,
        base_model_name: str = "neuralmind/bert-base-portuguese-cased",
        num_labels: int = 3,
        class_weights: torch.Tensor | None = None,
    ) -> None:
        super().__init__()
        self.num_labels = num_labels
        self.config = AutoConfig.from_pretrained(
            base_model_name,
            num_labels=num_labels,
        )
        self.bert = AutoModelForSequenceClassification.from_pretrained(
            base_model_name,
            config=self.config,
        )
        self.class_weights = class_weights

    def forward(
        self,
        input_ids: torch.Tensor,
        attention_mask: torch.Tensor,
        token_type_ids: torch.Tensor | None = None,
        labels: torch.Tensor | None = None,
    ) -> dict[str, torch.Tensor]:
        kwargs: dict[str, Any] = {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
        }
        if token_type_ids is not None:
            kwargs["token_type_ids"] = token_type_ids

        outputs = self.bert.bert(**kwargs)
        sequence_output = outputs[0]
        pooled_output = outputs[1] if len(outputs) > 1 else sequence_output[:, 0]

        if hasattr(self.bert, "dropout"):
            pooled_output = self.bert.dropout(pooled_output)
        logits = self.bert.classifier(pooled_output)

        loss = None
        if labels is not None:
            if self.class_weights is not None:
                cw = self.class_weights.to(logits.device)
                loss_fn = nn.CrossEntropyLoss(weight=cw)
            else:
                loss_fn = nn.CrossEntropyLoss()
            loss = loss_fn(logits, labels)

        return {"loss": loss, "logits": logits}

    @torch.inference_mode()
    def predict_proba(
        self,
        input_ids: torch.Tensor,
        attention_mask: torch.Tensor,
        token_type_ids: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """Returns softmax probabilities across 3 classes."""
        outputs = self.forward(input_ids, attention_mask, token_type_ids)
        return torch.softmax(outputs["logits"], dim=-1)


def compute_class_weights(y_train: list[int] | np.ndarray, num_classes: int = 3) -> torch.Tensor:
    """Calculate balanced class weights from training labels only."""
    y = np.array(y_train)
    counts = np.bincount(y, minlength=num_classes)
    total = len(y)
    counts = np.clip(counts, 1, total)
    weights = total / (num_classes * counts)
    return torch.tensor(weights, dtype=torch.float)


def train_sentiment_classifier(
    model: SentimentClassifier,
    tokenizer: PreTrainedTokenizerBase,
    train_dataset: SentimentDataset,
    val_dataset: SentimentDataset,
    output_dir: Path | str,
    epochs: int = 5,
    batch_size: int = 16,
    learning_rate: float = 2e-5,
    weight_decay: float = 0.01,
    warmup_ratio: float = 0.1,
    gradient_accumulation_steps: int = 1,
    early_stopping_patience: int = 2,
    mixed_precision: bool = True,
    seed: int = 42,
    taxonomy: Taxonomy | None = None,
) -> dict[str, Any]:
    """Train the sentiment classifier with early stopping on macro F1."""
    if taxonomy is None:
        taxonomy = get_taxonomy()

    torch.manual_seed(seed)
    np.random.seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    use_amp = mixed_precision and device.type == "cuda"
    scaler = torch.cuda.amp.GradScaler(enabled=use_amp)

    model.to(device)

    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False,
    )

    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=learning_rate,
        weight_decay=weight_decay,
    )

    total_steps = (len(train_loader) // gradient_accumulation_steps) * epochs
    warmup_steps = int(total_steps * warmup_ratio)

    from transformers import get_linear_schedule_with_warmup
    scheduler = get_linear_schedule_with_warmup(
        optimizer,
        num_warmup_steps=warmup_steps,
        num_training_steps=total_steps,
    )

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    best_val_macro_f1 = -1.0
    patience_counter = 0
    training_history: list[dict[str, Any]] = []

    logger.info(
        "sentiment_training_start",
        device=str(device),
        use_amp=use_amp,
        epochs=epochs,
        train_samples=len(train_dataset),
        val_samples=len(val_dataset),
    )

    sentiment_names = list(taxonomy.sentiments)

    for epoch in range(1, epochs + 1):
        model.train()
        total_train_loss = 0.0

        for step, batch in enumerate(train_loader):
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            token_type_ids = batch.get("token_type_ids")
            if token_type_ids is not None:
                token_type_ids = token_type_ids.to(device)
            labels = batch["labels"].to(device)

            with torch.cuda.amp.autocast(enabled=use_amp):
                outputs = model(
                    input_ids=input_ids,
                    attention_mask=attention_mask,
                    token_type_ids=token_type_ids,
                    labels=labels,
                )
                loss = outputs["loss"] / gradient_accumulation_steps

            scaler.scale(loss).backward()
            total_train_loss += loss.item() * gradient_accumulation_steps

            if (step + 1) % gradient_accumulation_steps == 0 or (step + 1) == len(train_loader):
                scaler.step(optimizer)
                scaler.update()
                optimizer.zero_grad()
                scheduler.step()

        avg_train_loss = total_train_loss / len(train_loader)

        # Validation step
        val_metrics = evaluate_sentiment_classifier(
            model=model,
            val_loader=val_loader,
            val_aspects=val_dataset.aspects,
            device=device,
            sentiment_names=sentiment_names,
        )

        val_macro_f1 = val_metrics["macro_f1"]
        logger.info(
            "sentiment_epoch_end",
            epoch=epoch,
            train_loss=round(avg_train_loss, 4),
            val_macro_f1=val_macro_f1,
            val_accuracy=val_metrics["accuracy"],
        )

        training_history.append({
            "epoch": epoch,
            "train_loss": round(avg_train_loss, 4),
            "val_macro_f1": val_macro_f1,
            "val_accuracy": val_metrics["accuracy"],
        })

        if val_macro_f1 > best_val_macro_f1:
            best_val_macro_f1 = val_macro_f1
            patience_counter = 0
            save_sentiment_classifier_artifact(
                model=model,
                tokenizer=tokenizer,
                save_dir=output_dir / "best_model",
            )
            with open(output_dir / "val_metrics.json", "w", encoding="utf-8") as f:
                json.dump(val_metrics, f, indent=2)
        else:
            patience_counter += 1
            if patience_counter >= early_stopping_patience:
                logger.info("early_stopping_triggered", epoch=epoch, patience=patience_counter)
                break

    return {
        "best_val_macro_f1": best_val_macro_f1,
        "history": training_history,
        "saved_path": str(output_dir / "best_model"),
    }


def evaluate_sentiment_classifier(
    model: SentimentClassifier,
    val_loader: DataLoader,
    val_aspects: list[str],
    device: torch.device,
    sentiment_names: list[str],
) -> dict[str, Any]:
    """Evaluate sentiment classifier on DataLoader."""
    model.eval()
    all_preds: list[int] = []
    all_trues: list[int] = []

    with torch.inference_mode():
        for batch in val_loader:
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            token_type_ids = batch.get("token_type_ids")
            if token_type_ids is not None:
                token_type_ids = token_type_ids.to(device)
            labels = batch["labels"]

            probs = model.predict_proba(input_ids, attention_mask, token_type_ids)
            preds = torch.argmax(probs, dim=-1)

            all_preds.extend(preds.cpu().tolist())
            all_trues.extend(labels.tolist())

    y_true_str = [sentiment_names[i] for i in all_trues]
    y_pred_str = [sentiment_names[i] for i in all_preds]

    return compute_sentiment_metrics(
        y_true=y_true_str,
        y_pred=y_pred_str,
        aspects=val_aspects,
        sentiment_names=sentiment_names,
    )


def save_sentiment_classifier_artifact(
    model: SentimentClassifier,
    tokenizer: PreTrainedTokenizerBase,
    save_dir: Path | str,
) -> None:
    """Save model and tokenizer."""
    save_dir = Path(save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)
    model.bert.save_pretrained(save_dir / "model")
    tokenizer.save_pretrained(save_dir / "tokenizer")


def load_sentiment_classifier_artifact(
    artifact_dir: Path | str,
    device: torch.device | None = None,
) -> tuple[SentimentClassifier, PreTrainedTokenizerBase]:
    """Load an exported sentiment classifier artifact."""
    artifact_dir = Path(artifact_dir)
    if device is None:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    model_path = artifact_dir / "model"
    if not model_path.exists():
        model_path = artifact_dir / "best_model" / "model"

    tokenizer_path = artifact_dir / "tokenizer"
    if not tokenizer_path.exists():
        tokenizer_path = artifact_dir / "best_model" / "tokenizer"

    tokenizer = AutoTokenizer.from_pretrained(str(tokenizer_path))
    classifier = SentimentClassifier(base_model_name=str(model_path))
    classifier.to(device)
    classifier.eval()

    return classifier, tokenizer
