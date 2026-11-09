"""Aspect detector model module for ABSA pipeline.

Multi-label sequence classification using BERTimbau (neuralmind/bert-base-portuguese-cased).
Uses BCEWithLogitsLoss, supports class weighting (pos_weight),
and per-aspect threshold calibration.
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
from ..metrics import compute_aspect_metrics, find_optimal_thresholds
from ..taxonomy import Taxonomy, get_taxonomy

logger = get_logger(__name__)


class AspectDetectionDataset(Dataset):
    """PyTorch Dataset for multi-label aspect detection."""

    def __init__(
        self,
        texts: list[str],
        labels: list[list[int]] | np.ndarray | None,
        tokenizer: PreTrainedTokenizerBase,
        max_length: int = 128,
    ) -> None:
        self.texts = texts
        self.labels = labels
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self) -> int:
        return len(self.texts)

    def __getitem__(self, idx: int) -> dict[str, torch.Tensor]:
        text = str(self.texts[idx])
        encoding = self.tokenizer(
            text,
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
            item["labels"] = torch.tensor(self.labels[idx], dtype=torch.float)

        return item


class AspectDetector(nn.Module):
    """Multi-label aspect detector based on BERTimbau."""

    def __init__(
        self,
        base_model_name: str = "neuralmind/bert-base-portuguese-cased",
        num_labels: int = 12,
        pos_weight: torch.Tensor | None = None,
    ) -> None:
        super().__init__()
        self.num_labels = num_labels
        self.config = AutoConfig.from_pretrained(
            base_model_name,
            num_labels=num_labels,
            problem_type="multi_label_classification",
        )
        self.bert = AutoModelForSequenceClassification.from_pretrained(
            base_model_name,
            config=self.config,
        )
        self.pos_weight = pos_weight

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
            if self.pos_weight is not None:
                pw = self.pos_weight.to(logits.device)
                loss_fn = nn.BCEWithLogitsLoss(pos_weight=pw)
            else:
                loss_fn = nn.BCEWithLogitsLoss()
            loss = loss_fn(logits, labels)

        return {"loss": loss, "logits": logits}

    @torch.inference_mode()
    def predict_proba(
        self,
        input_ids: torch.Tensor,
        attention_mask: torch.Tensor,
        token_type_ids: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """Returns sigmoid probabilities."""
        outputs = self.forward(input_ids, attention_mask, token_type_ids)
        return torch.sigmoid(outputs["logits"])


def compute_pos_weights(y_train: np.ndarray) -> torch.Tensor:
    """Calculate pos_weight for BCEWithLogitsLoss from training labels only.

    pos_weight[i] = (N - P_i) / P_i
    """
    total_samples = y_train.shape[0]
    positives = y_train.sum(axis=0)
    # Avoid div by zero with clipping
    positives = np.clip(positives, 1, total_samples - 1)
    negatives = total_samples - positives
    weights = negatives / positives
    return torch.tensor(weights, dtype=torch.float)


def train_aspect_detector(
    model: AspectDetector,
    tokenizer: PreTrainedTokenizerBase,
    train_dataset: AspectDetectionDataset,
    val_dataset: AspectDetectionDataset,
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
    """Train the aspect detector with early stopping on macro F1."""
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
        "aspect_training_start",
        device=str(device),
        use_amp=use_amp,
        epochs=epochs,
        train_samples=len(train_dataset),
        val_samples=len(val_dataset),
    )

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
        val_metrics, val_probs, val_trues = evaluate_aspect_detector(
            model=model,
            val_loader=val_loader,
            device=device,
            aspect_names=taxonomy.aspect_codes,
        )

        val_macro_f1 = val_metrics["macro_f1"]
        logger.info(
            "aspect_epoch_end",
            epoch=epoch,
            train_loss=round(avg_train_loss, 4),
            val_macro_f1=val_macro_f1,
            val_micro_f1=val_metrics["micro_f1"],
        )

        epoch_record = {
            "epoch": epoch,
            "train_loss": round(avg_train_loss, 4),
            "val_macro_f1": val_macro_f1,
            "val_micro_f1": val_metrics["micro_f1"],
        }
        training_history.append(epoch_record)

        # Early stopping check
        if val_macro_f1 > best_val_macro_f1:
            best_val_macro_f1 = val_macro_f1
            patience_counter = 0
            save_aspect_detector_artifact(
                model=model,
                tokenizer=tokenizer,
                save_dir=output_dir / "best_model",
            )
            # Find optimal thresholds on best model
            threshold_analysis = find_optimal_thresholds(
                y_true=val_trues,
                y_prob=val_probs,
                aspect_names=taxonomy.aspect_codes,
            )
            with open(output_dir / "thresholds.json", "w", encoding="utf-8") as f:
                json.dump(threshold_analysis["per_aspect_thresholds"], f, indent=2)
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


def evaluate_aspect_detector(
    model: AspectDetector,
    val_loader: DataLoader,
    device: torch.device,
    aspect_names: list[str],
) -> tuple[dict[str, Any], np.ndarray, np.ndarray]:
    """Evaluate detector on a DataLoader returning metrics, probs, and trues."""
    model.eval()
    all_probs: list[np.ndarray] = []
    all_trues: list[np.ndarray] = []

    with torch.inference_mode():
        for batch in val_loader:
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            token_type_ids = batch.get("token_type_ids")
            if token_type_ids is not None:
                token_type_ids = token_type_ids.to(device)
            labels = batch["labels"]

            probs = model.predict_proba(input_ids, attention_mask, token_type_ids)
            all_probs.append(probs.cpu().numpy())
            all_trues.append(labels.numpy())

    y_prob = np.concatenate(all_probs, axis=0)
    y_true = np.concatenate(all_trues, axis=0)
    y_pred = (y_prob >= 0.5).astype(int)

    metrics = compute_aspect_metrics(
        y_true=y_true,
        y_pred=y_pred,
        y_prob=y_prob,
        aspect_names=aspect_names,
    )
    return metrics, y_prob, y_true


def save_aspect_detector_artifact(
    model: AspectDetector,
    tokenizer: PreTrainedTokenizerBase,
    save_dir: Path | str,
) -> None:
    """Save model and tokenizer."""
    save_dir = Path(save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)
    model.bert.save_pretrained(save_dir / "model")
    tokenizer.save_pretrained(save_dir / "tokenizer")


def load_aspect_detector_artifact(
    artifact_dir: Path | str,
    device: torch.device | None = None,
) -> tuple[AspectDetector, PreTrainedTokenizerBase, dict[str, float]]:
    """Load an exported aspect detector artifact."""
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
    detector = AspectDetector(base_model_name=str(model_path))
    detector.to(device)
    detector.eval()

    thresholds_path = artifact_dir / "thresholds.json"
    thresholds: dict[str, float] = {}
    if thresholds_path.exists():
        with open(thresholds_path, "r", encoding="utf-8") as f:
            thresholds = json.load(f)

    return detector, tokenizer, thresholds
