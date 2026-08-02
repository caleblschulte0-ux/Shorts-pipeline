# Subscription fallback lab

This review-only package makes daily posting independent from Claude, Gemini, or any
other same-day generation service.

## Core rule

```text
generation job -> approved buffer -> posting job
```

The posting transaction never calls Claude, Gemini, a template writer, research APIs,
or renderers. It atomically claims a previously completed, QA-passed, approved package.

## Fallback ladder

1. Claude adapter when explicitly configured and healthy.
2. Gemini adapter when `GEMINI_API_KEY` is configured and healthy.
3. Local deterministic evidence-bound template writer.
4. Existing approved evergreen buffer.

A consumer Claude subscription is not a GitHub Actions credential and is never a
posting dependency.

## Included systems

- health-aware provider routing and circuit breakers;
- evidence-bound deterministic scripts requiring no model;
- atomic approved-package queue;
- 30/14/7 buffer health policy;
- explicit FULL/ACCEPTABLE/DEGRADED/BUFFERED/BLOCKED states;
- upload idempotency ledger;
- generation/posting separation;
- synthetic demo and isolated tests.

## Checks

```bash
python -m unittest review_prototypes.subscription_fallback.test_subscription_fallback
python -m review_prototypes.subscription_fallback.cli demo
python -m review_prototypes.subscription_fallback.cli keys
```

## Safety boundary

No production imports, workflow changes, uploader calls, network execution, secret
reads beyond optional presence checks, or publishing authority are included.
