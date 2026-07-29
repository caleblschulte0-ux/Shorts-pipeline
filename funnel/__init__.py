"""funnel/ — TOP OF FUNNEL MEDIA (pipeline reorg, see docs/PIPELINE_LAYOUT.md).

Every module that FINDS or GENERATES media for any channel lives here:
the 22-provider funnel, subject/entity image finders, stock video search,
AI image generation, og: scraping, the cross-video usage ledger, and the
gameplay library scanner. All channels import from this package.

Keep this __init__ import-free: modules here are heavy and lazily imported
by channels; a fat __init__ would create cycles and slow every entrypoint.
"""
