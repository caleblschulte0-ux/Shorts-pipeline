"""data_learning — a data-driven micro-learning add-on for Shorts-pipeline.

This package sits *on top of* the existing Shorts-pipeline. It never
modifies any existing module. Its only contract with the base pipeline is
the JSON "package" schema consumed by
``make_explainer_stacked.build_from_package`` — i.e. the exact same
{title, script, shots, punches, hashtags, music_vibe} dict the daily
trending routine writes by hand.

Pipeline:

    free public data  ->  transform  ->  pick strongest insight
                      ->  render chart PNG (matplotlib, optional)
                      ->  emit a base-pipeline package (existing schema)
                      ->  QA validate

The emitted package drops into ``state/trending_packages/YYYYMMDD/`` (or a
review folder) and the *unchanged* orchestrator renders + uploads it.
"""

__all__ = ["__version__"]
__version__ = "0.1.0"
