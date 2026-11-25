# Dataset Validation Report

**Timestamp:** 2026-11-25T16:05:38.092838
**Status:** ⚠️ `approved_with_warnings`

## Summary

| Metric | Value |
|---|---|
| Total records | 6 |
| Unique reviews | 2 |
| Records with aspects | 6 |
| Records without aspects | 0 |
| Unique users | 1 |
| Unique stores | 2 |
| Unique orders | 2 |

## Aspect Distribution

| Aspect | Count |
|---|---|
| embalagem | 1 |
| preparo | 1 |
| sabor | 1 |
| temperatura | 2 |
| tempo_entrega | 1 |

## Sentiment Distribution by Aspect

| Aspect | Positivo | Negativo | Neutro |
|---|---|---|---|
| embalagem | 1 | 0 | 0 |
| preparo | 1 | 0 | 0 |
| sabor | 1 | 0 | 0 |
| temperatura | 1 | 1 | 0 |
| tempo_entrega | 0 | 1 | 0 |

## Conflicts: 0

## Duplicates: 0

## Class Warnings

**Below 200 examples (critical):** sabor, qualidade, quantidade, temperatura, aparencia, preparo, atendimento, pedido_correto, embalagem, custo_beneficio, tempo_entrega, condicao_entrega
**Imbalanced (>80% single sentiment):** sabor, preparo, embalagem, tempo_entrega

## Recommendations

- Aspect 'sabor' has only 1 examples (< 200 minimum). Consider collecting more data.
- Aspect 'sabor' has 100% 'positivo' sentiment. Consider balancing the distribution.
- Aspect 'qualidade' has only 0 examples (< 200 minimum). Consider collecting more data.
- Aspect 'quantidade' has only 0 examples (< 200 minimum). Consider collecting more data.
- Aspect 'temperatura' has only 2 examples (< 200 minimum). Consider collecting more data.
- Aspect 'aparencia' has only 0 examples (< 200 minimum). Consider collecting more data.
- Aspect 'preparo' has only 1 examples (< 200 minimum). Consider collecting more data.
- Aspect 'preparo' has 100% 'positivo' sentiment. Consider balancing the distribution.
- Aspect 'atendimento' has only 0 examples (< 200 minimum). Consider collecting more data.
- Aspect 'pedido_correto' has only 0 examples (< 200 minimum). Consider collecting more data.
- Aspect 'embalagem' has only 1 examples (< 200 minimum). Consider collecting more data.
- Aspect 'embalagem' has 100% 'positivo' sentiment. Consider balancing the distribution.
- Aspect 'custo_beneficio' has only 0 examples (< 200 minimum). Consider collecting more data.
- Aspect 'tempo_entrega' has only 1 examples (< 200 minimum). Consider collecting more data.
- Aspect 'tempo_entrega' has 100% 'negativo' sentiment. Consider balancing the distribution.
- Aspect 'condicao_entrega' has only 0 examples (< 200 minimum). Consider collecting more data.
