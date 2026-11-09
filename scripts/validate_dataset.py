#!/usr/bin/env python3
"""Validate a dataset for the ABSA pipeline.

Generates a validation report in JSON and Markdown format.

Usage:
    python scripts/validate_dataset.py --input data/raw/reviews.jsonl --output reports/validation
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from absa.datasets import (
    ReviewRecord,
    ValidationError,
    detect_conflicts,
    load_data,
    records_to_reviews,
)
from absa.taxonomy import load_taxonomy


def validate_dataset(
    records: list[dict],
    taxonomy=None,
) -> dict:
    """Run all validation checks on the dataset.

    Args:
        records: Raw records loaded from file.
        taxonomy: Taxonomy instance.

    Returns:
        Validation report dictionary.
    """
    if taxonomy is None:
        taxonomy = load_taxonomy()

    errors: list[dict] = []
    warnings: list[dict] = []

    valid_aspects = set(taxonomy.aspect_codes)
    valid_sentiments = set(taxonomy.sentiments)

    # Track various counters
    aspect_counts: Counter = Counter()
    sentiment_by_aspect: dict[str, Counter] = defaultdict(Counter)
    review_texts: dict[str, str] = {}
    exact_dupes: list[dict] = []
    seen_rows: set[str] = set()
    user_ids: set[str] = set()
    store_ids: set[str] = set()
    order_ids: set[str] = set()
    reviews_with_review_flag: list[str] = []
    total_records = len(records)
    records_with_aspects = 0
    records_without_aspects = 0

    for i, rec in enumerate(records):
        rid = rec.get("review_id")
        text = rec.get("text")
        aspect = rec.get("aspect")
        sentiment = rec.get("sentiment")

        # Check required fields
        if not rid:
            errors.append({
                "index": i,
                "review_id": rid,
                "field": "review_id",
                "type": "missing_required_field",
                "message": "review_id is missing or empty",
            })

        if not text or (isinstance(text, str) and text.strip() == ""):
            errors.append({
                "index": i,
                "review_id": rid,
                "field": "text",
                "type": "empty_text",
                "message": "text is missing or empty",
            })

        # Check text consistency for same review_id
        if rid and text:
            rid_str = str(rid)
            text_str = str(text).strip()
            if rid_str in review_texts:
                if review_texts[rid_str] != text_str:
                    errors.append({
                        "index": i,
                        "review_id": rid_str,
                        "field": "text",
                        "type": "inconsistent_text",
                        "message": f"review_id '{rid_str}' has different texts",
                    })
            else:
                review_texts[rid_str] = text_str

        # Check for exact duplicates
        row_key = json.dumps(rec, sort_keys=True, ensure_ascii=False)
        if row_key in seen_rows:
            exact_dupes.append({
                "index": i,
                "review_id": str(rid) if rid else None,
            })
        seen_rows.add(row_key)

        # Validate aspect and sentiment
        if aspect is not None:
            records_with_aspects += 1
            aspect_str = str(aspect)

            if aspect_str not in valid_aspects:
                errors.append({
                    "index": i,
                    "review_id": str(rid) if rid else None,
                    "field": "aspect",
                    "type": "invalid_aspect",
                    "message": f"Aspect '{aspect_str}' is not in the taxonomy",
                })
            else:
                aspect_counts[aspect_str] += 1

            if sentiment is None:
                errors.append({
                    "index": i,
                    "review_id": str(rid) if rid else None,
                    "field": "sentiment",
                    "type": "missing_sentiment",
                    "message": "Aspect present but sentiment is missing",
                })
            else:
                sentiment_str = str(sentiment)
                if sentiment_str not in valid_sentiments:
                    errors.append({
                        "index": i,
                        "review_id": str(rid) if rid else None,
                        "field": "sentiment",
                        "type": "invalid_sentiment",
                        "message": f"Sentiment '{sentiment_str}' is not valid",
                    })
                elif aspect_str in valid_aspects:
                    sentiment_by_aspect[aspect_str][sentiment_str] += 1
        else:
            records_without_aspects += 1

        # Validate offsets
        start = rec.get("start_offset")
        end = rec.get("end_offset")
        evidence = rec.get("evidence_text")

        if start is not None or end is not None:
            if start is not None and end is not None:
                try:
                    s, e = int(start), int(end)
                    if s < 0 or e < 0:
                        errors.append({
                            "index": i,
                            "review_id": str(rid) if rid else None,
                            "field": "offsets",
                            "type": "negative_offset",
                            "message": "Offsets must be non-negative",
                        })
                    elif s >= e:
                        errors.append({
                            "index": i,
                            "review_id": str(rid) if rid else None,
                            "field": "offsets",
                            "type": "invalid_offset_range",
                            "message": f"start_offset ({s}) must be less than end_offset ({e})",
                        })
                    elif text and isinstance(text, str) and e > len(text):
                        errors.append({
                            "index": i,
                            "review_id": str(rid) if rid else None,
                            "field": "offsets",
                            "type": "offset_out_of_bounds",
                            "message": f"end_offset ({e}) exceeds text length ({len(text)})",
                        })
                    elif evidence and text and isinstance(text, str):
                        extracted = text[s:e]
                        if extracted != evidence:
                            warnings.append({
                                "index": i,
                                "review_id": str(rid) if rid else None,
                                "field": "evidence_text",
                                "type": "evidence_mismatch",
                                "message": f"evidence_text doesn't match text[{s}:{e}]",
                                "severity": "warning",
                            })
                except (ValueError, TypeError):
                    errors.append({
                        "index": i,
                        "review_id": str(rid) if rid else None,
                        "field": "offsets",
                        "type": "non_integer_offset",
                        "message": "Offsets must be integers",
                    })
            else:
                warnings.append({
                    "index": i,
                    "review_id": str(rid) if rid else None,
                    "field": "offsets",
                    "type": "partial_offsets",
                    "message": "Both start_offset and end_offset should be provided together",
                    "severity": "warning",
                })

        # Track optional fields
        if rec.get("user_id"):
            user_ids.add(str(rec["user_id"]))
        if rec.get("store_id"):
            store_ids.add(str(rec["store_id"]))
        if rec.get("order_id"):
            order_ids.add(str(rec["order_id"]))
        if rec.get("requires_review"):
            reviews_with_review_flag.append(str(rid) if rid else f"index_{i}")

    # Convert to reviews for conflict detection
    reviews = records_to_reviews(records)
    conflicts = detect_conflicts(reviews)

    # Mark conflicts as requires_review
    for conflict in conflicts:
        warnings.append({
            "review_id": conflict["review_id"],
            "field": "sentiment",
            "type": "sentiment_conflict",
            "message": (
                f"Aspect '{conflict['aspect']}' has conflicting sentiments: "
                f"{conflict['sentiments']}"
            ),
            "severity": "warning",
        })

    # Check class distribution
    recommendations: list[str] = []
    low_count_aspects: list[str] = []
    risk_aspects: list[str] = []
    imbalanced_aspects: list[str] = []

    for aspect_code in taxonomy.aspect_codes:
        count = aspect_counts.get(aspect_code, 0)
        if count < 200:
            low_count_aspects.append(aspect_code)
            recommendations.append(
                f"Aspect '{aspect_code}' has only {count} examples (< 200 minimum). "
                f"Consider collecting more data."
            )
        elif count < 500:
            risk_aspects.append(aspect_code)
            recommendations.append(
                f"Aspect '{aspect_code}' has {count} examples (< 500). "
                f"Risk for production quality."
            )

        # Check imbalance within aspect
        if aspect_code in sentiment_by_aspect:
            total_for_aspect = sum(sentiment_by_aspect[aspect_code].values())
            if total_for_aspect > 0:
                for sent, sent_count in sentiment_by_aspect[aspect_code].items():
                    ratio = sent_count / total_for_aspect
                    if ratio > 0.80:
                        imbalanced_aspects.append(aspect_code)
                        recommendations.append(
                            f"Aspect '{aspect_code}' has {ratio:.0%} '{sent}' sentiment. "
                            f"Consider balancing the distribution."
                        )
                        break

    # Determine status
    has_errors = len(errors) > 0
    has_critical_warnings = len(low_count_aspects) > 0 or len(conflicts) > 0

    if has_errors:
        status = "rejected"
    elif has_critical_warnings:
        status = "approved_with_warnings"
    else:
        status = "approved"

    # Build report
    unique_reviews = len(review_texts)
    report = {
        "validation_timestamp": datetime.now().isoformat(),
        "status": status,
        "summary": {
            "total_records": total_records,
            "total_reviews": unique_reviews,
            "records_with_aspects": records_with_aspects,
            "records_without_aspects": records_without_aspects,
            "unique_users": len(user_ids),
            "unique_stores": len(store_ids),
            "unique_orders": len(order_ids),
        },
        "aspect_distribution": dict(aspect_counts.most_common()),
        "sentiment_by_aspect": {
            asp: dict(counts) for asp, counts in sorted(sentiment_by_aspect.items())
        },
        "conflicts": {
            "count": len(conflicts),
            "details": conflicts,
        },
        "duplicates": {
            "exact_count": len(exact_dupes),
            "details": exact_dupes[:20],  # Limit output
        },
        "requires_review_count": len(reviews_with_review_flag),
        "class_warnings": {
            "below_200": low_count_aspects,
            "below_500_risk": risk_aspects,
            "imbalanced": imbalanced_aspects,
        },
        "errors": errors,
        "warnings": warnings,
        "recommendations": recommendations,
    }

    return report


def report_to_markdown(report: dict) -> str:
    """Convert validation report to Markdown format.

    Args:
        report: Validation report dictionary.

    Returns:
        Markdown string.
    """
    lines: list[str] = []
    lines.append("# Dataset Validation Report")
    lines.append("")
    lines.append(f"**Timestamp:** {report['validation_timestamp']}")

    status = report["status"]
    status_emoji = {"approved": "✅", "approved_with_warnings": "⚠️", "rejected": "❌"}
    lines.append(f"**Status:** {status_emoji.get(status, '')} `{status}`")
    lines.append("")

    # Summary
    lines.append("## Summary")
    lines.append("")
    s = report["summary"]
    lines.append(f"| Metric | Value |")
    lines.append(f"|---|---|")
    lines.append(f"| Total records | {s['total_records']} |")
    lines.append(f"| Unique reviews | {s['total_reviews']} |")
    lines.append(f"| Records with aspects | {s['records_with_aspects']} |")
    lines.append(f"| Records without aspects | {s['records_without_aspects']} |")
    lines.append(f"| Unique users | {s['unique_users']} |")
    lines.append(f"| Unique stores | {s['unique_stores']} |")
    lines.append(f"| Unique orders | {s['unique_orders']} |")
    lines.append("")

    # Aspect distribution
    lines.append("## Aspect Distribution")
    lines.append("")
    lines.append("| Aspect | Count |")
    lines.append("|---|---|")
    for aspect, count in sorted(report["aspect_distribution"].items()):
        lines.append(f"| {aspect} | {count} |")
    lines.append("")

    # Sentiment by aspect
    lines.append("## Sentiment Distribution by Aspect")
    lines.append("")
    lines.append("| Aspect | Positivo | Negativo | Neutro |")
    lines.append("|---|---|---|---|")
    for aspect, counts in sorted(report["sentiment_by_aspect"].items()):
        pos = counts.get("positivo", 0)
        neg = counts.get("negativo", 0)
        neu = counts.get("neutro", 0)
        lines.append(f"| {aspect} | {pos} | {neg} | {neu} |")
    lines.append("")

    # Conflicts
    conf = report["conflicts"]
    lines.append(f"## Conflicts: {conf['count']}")
    lines.append("")
    if conf["details"]:
        for c in conf["details"]:
            lines.append(
                f"- **{c['review_id']}** aspect `{c['aspect']}`: "
                f"sentiments {c['sentiments']}"
            )
        lines.append("")

    # Duplicates
    dupes = report["duplicates"]
    lines.append(f"## Duplicates: {dupes['exact_count']}")
    lines.append("")

    # Class warnings
    cw = report["class_warnings"]
    if cw["below_200"] or cw["below_500_risk"] or cw["imbalanced"]:
        lines.append("## Class Warnings")
        lines.append("")
        if cw["below_200"]:
            lines.append(f"**Below 200 examples (critical):** {', '.join(cw['below_200'])}")
        if cw["below_500_risk"]:
            lines.append(f"**Below 500 examples (risk):** {', '.join(cw['below_500_risk'])}")
        if cw["imbalanced"]:
            lines.append(f"**Imbalanced (>80% single sentiment):** {', '.join(cw['imbalanced'])}")
        lines.append("")

    # Errors
    if report["errors"]:
        lines.append(f"## Errors: {len(report['errors'])}")
        lines.append("")
        for err in report["errors"][:50]:
            lines.append(f"- [{err['type']}] {err['message']} (review: {err.get('review_id', 'N/A')})")
        if len(report["errors"]) > 50:
            lines.append(f"- ... and {len(report['errors']) - 50} more errors")
        lines.append("")

    # Recommendations
    if report["recommendations"]:
        lines.append("## Recommendations")
        lines.append("")
        for rec in report["recommendations"]:
            lines.append(f"- {rec}")
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    """Main entry point for dataset validation."""
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    parser = argparse.ArgumentParser(
        description="Validate a dataset for the ABSA pipeline",
    )
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Path to input data file (.jsonl or .csv)",
    )
    parser.add_argument(
        "--output", "-o",
        required=True,
        help="Output directory for validation reports",
    )
    parser.add_argument(
        "--taxonomy",
        default=None,
        help="Path to taxonomy YAML (default: configs/taxonomy.yaml)",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        return 1

    # Load taxonomy
    taxonomy = load_taxonomy(args.taxonomy)
    print(f"Loaded taxonomy v{taxonomy.version} with {taxonomy.num_aspects} aspects")

    # Load data
    print(f"Loading data from {input_path}...")
    records = load_data(input_path)
    print(f"Loaded {len(records)} records")

    # Validate
    print("Running validation...")
    report = validate_dataset(records, taxonomy)

    # Save JSON report
    json_path = output_dir / "validation_report.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"JSON report saved to {json_path}")

    # Save Markdown report
    md_content = report_to_markdown(report)
    md_path = output_dir / "validation_report.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"Markdown report saved to {md_path}")

    # Print summary
    print(f"\nValidation status: {report['status']}")
    print(f"Total records: {report['summary']['total_records']}")
    print(f"Unique reviews: {report['summary']['total_reviews']}")
    print(f"Errors: {len(report['errors'])}")
    print(f"Warnings: {len(report['warnings'])}")
    print(f"Conflicts: {report['conflicts']['count']}")

    if report["status"] == "rejected":
        print("\n❌ Dataset REJECTED. Fix errors before training.")
        return 1
    elif report["status"] == "approved_with_warnings":
        print("\n⚠️ Dataset approved with warnings. Review recommendations.")
        return 0
    else:
        print("\n✅ Dataset APPROVED.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
