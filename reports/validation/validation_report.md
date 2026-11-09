# Dataset Validation Report

**Timestamp:** 2026-11-09T11:37:29.740087
**Status:** ⚠️ `approved_with_warnings`

## Summary

| Metric | Value |
|---|---|
| Total records | 33 |
| Unique reviews | 20 |
| Records with aspects | 31 |
| Records without aspects | 2 |
| Unique users | 20 |
| Unique stores | 0 |
| Unique orders | 20 |

## Aspect Distribution

| Aspect | Count |
|---|---|
| aparencia | 1 |
| atendimento | 1 |
| condicao_entrega | 1 |
| custo_beneficio | 3 |
| embalagem | 3 |
| pedido_correto | 2 |
| preparo | 2 |
| qualidade | 1 |
| quantidade | 3 |
| sabor | 6 |
| temperatura | 3 |
| tempo_entrega | 5 |

## Sentiment Distribution by Aspect

| Aspect | Positivo | Negativo | Neutro |
|---|---|---|---|
| aparencia | 1 | 0 | 0 |
| atendimento | 1 | 0 | 0 |
| condicao_entrega | 0 | 1 | 0 |
| custo_beneficio | 1 | 2 | 0 |
| embalagem | 1 | 2 | 0 |
| pedido_correto | 0 | 2 | 0 |
| preparo | 1 | 1 | 0 |
| qualidade | 1 | 0 | 0 |
| quantidade | 2 | 1 | 0 |
| sabor | 5 | 0 | 1 |
| temperatura | 2 | 1 | 0 |
| tempo_entrega | 2 | 2 | 1 |

## Conflicts: 0

## Duplicates: 0

## Class Warnings

**Below 200 examples (critical):** sabor, qualidade, quantidade, temperatura, aparencia, preparo, atendimento, pedido_correto, embalagem, custo_beneficio, tempo_entrega, condicao_entrega
**Imbalanced (>80% single sentiment):** sabor, qualidade, aparencia, atendimento, pedido_correto, condicao_entrega

## Recommendations

- Aspect 'sabor' has only 6 examples (< 200 minimum). Consider collecting more data.
- Aspect 'sabor' has 83% 'positivo' sentiment. Consider balancing the distribution.
- Aspect 'qualidade' has only 1 examples (< 200 minimum). Consider collecting more data.
- Aspect 'qualidade' has 100% 'positivo' sentiment. Consider balancing the distribution.
- Aspect 'quantidade' has only 3 examples (< 200 minimum). Consider collecting more data.
- Aspect 'temperatura' has only 3 examples (< 200 minimum). Consider collecting more data.
- Aspect 'aparencia' has only 1 examples (< 200 minimum). Consider collecting more data.
- Aspect 'aparencia' has 100% 'positivo' sentiment. Consider balancing the distribution.
- Aspect 'preparo' has only 2 examples (< 200 minimum). Consider collecting more data.
- Aspect 'atendimento' has only 1 examples (< 200 minimum). Consider collecting more data.
- Aspect 'atendimento' has 100% 'positivo' sentiment. Consider balancing the distribution.
- Aspect 'pedido_correto' has only 2 examples (< 200 minimum). Consider collecting more data.
- Aspect 'pedido_correto' has 100% 'negativo' sentiment. Consider balancing the distribution.
- Aspect 'embalagem' has only 3 examples (< 200 minimum). Consider collecting more data.
- Aspect 'custo_beneficio' has only 3 examples (< 200 minimum). Consider collecting more data.
- Aspect 'tempo_entrega' has only 5 examples (< 200 minimum). Consider collecting more data.
- Aspect 'condicao_entrega' has only 1 examples (< 200 minimum). Consider collecting more data.
- Aspect 'condicao_entrega' has 100% 'negativo' sentiment. Consider balancing the distribution.
