from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
from urllib.parse import quote

from .contracts import RequestPlan


def _clean(value: str, field: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{field} cannot be empty")
    return cleaned


@dataclass(frozen=True)
class ResearchTopic:
    query: str
    country: str = "US"
    language: str = "English"
    year: int = 2025

    def __post_init__(self) -> None:
        _clean(self.query, "query")
        if self.year < 1900 or self.year > 2100:
            raise ValueError("year must be between 1900 and 2100")


class FreeResearchAdapters:
    """Builds inspectable plans for free or free-tier public-data sources.

    The adapter never sends a request. A future production port must add HTTP
    execution, caching, rate limits, provenance capture, and source-specific terms.
    """

    def gdelt(self, query: str, *, max_records: int = 50, mode: str = "ArtList") -> RequestPlan:
        query = _clean(query, "query")
        if not 1 <= max_records <= 250:
            raise ValueError("max_records must be between 1 and 250")
        return RequestPlan(
            provider="gdelt",
            method="GET",
            url="https://api.gdeltproject.org/api/v2/doc/doc",
            query={"query": query, "mode": mode, "format": "json", "maxrecords": str(max_records), "sort": "HybridRel"},
            notes=("No API key required.", "Store article URL, publisher, date, and query with every result."),
        )

    def wikidata(self, sparql: str) -> RequestPlan:
        sparql = _clean(sparql, "sparql")
        return RequestPlan(
            provider="wikidata",
            method="GET",
            url="https://query.wikidata.org/sparql",
            headers={"Accept": "application/sparql-results+json", "User-Agent": "ShortsPipelineReviewPrototype/1.0"},
            query={"query": sparql, "format": "json"},
            notes=("No API key required.", "Production must use a descriptive User-Agent and cache repeated queries."),
        )

    def wikipedia_summary(self, title: str, *, language: str = "en") -> RequestPlan:
        title = _clean(title, "title")
        language = _clean(language, "language")
        return RequestPlan(
            provider="wikipedia",
            method="GET",
            url=f"https://{language}.wikipedia.org/api/rest_v1/page/summary/{quote(title, safe='')}",
            notes=("No API key required.", "Use as discovery context; verify material claims against primary sources."),
        )

    def common_crawl_indexes(self) -> RequestPlan:
        return RequestPlan(
            provider="common_crawl",
            method="GET",
            url="https://index.commoncrawl.org/collinfo.json",
            notes=("No API key required.", "Select an index, then query its CDX endpoint in a separately recorded request."),
        )

    def common_crawl_cdx(self, index_name: str, url_pattern: str, *, limit: int = 50) -> RequestPlan:
        index_name = _clean(index_name, "index_name")
        url_pattern = _clean(url_pattern, "url_pattern")
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        return RequestPlan(
            provider="common_crawl",
            method="GET",
            url=f"https://index.commoncrawl.org/{index_name}-index",
            query={"url": url_pattern, "output": "json", "limit": str(limit), "filter": "status:200"},
            notes=("No API key required.", "Archived content still requires rights and attribution review."),
        )

    def our_world_in_data(self, grapher_slug: str) -> RequestPlan:
        slug = _clean(grapher_slug, "grapher_slug").strip("/")
        return RequestPlan(
            provider="our_world_in_data",
            method="GET",
            url=f"https://ourworldindata.org/grapher/{quote(slug)}.csv",
            output_kind="csv",
            notes=("No API key required.", "Persist the chart URL, CSV snapshot hash, and retrieval date."),
        )

    def fred(self, series_id: str, *, start: str = "2000-01-01") -> RequestPlan:
        series_id = _clean(series_id, "series_id")
        return RequestPlan(
            provider="fred",
            method="GET",
            url="https://api.stlouisfed.org/fred/series/observations",
            query={"series_id": series_id, "file_type": "json", "observation_start": start, "api_key": "${FRED_API_KEY}"},
            secret_names=("FRED_API_KEY",),
            notes=("The key is free but required by this endpoint.", "Preserve series ID, units, frequency, and vintage date."),
        )

    def census_acs5(self, *, year: int, variables: Iterable[str], geography: str) -> RequestPlan:
        variables = tuple(_clean(value, "variable") for value in variables)
        if not variables:
            raise ValueError("at least one Census variable is required")
        query = {"get": ",".join(("NAME", *variables)), "for": _clean(geography, "geography"), "key": "${CENSUS_API_KEY}"}
        return RequestPlan(
            provider="census",
            method="GET",
            url=f"https://api.census.gov/data/{year}/acs/acs5",
            query=query,
            secret_names=("CENSUS_API_KEY",),
            notes=("Census now requires a free API key for data queries.", "Persist dataset vintage, variables, geography, and response snapshot."),
        )

    def noaa_cdo(self, *, dataset_id: str, location_id: str, start_date: str, end_date: str, limit: int = 1000) -> RequestPlan:
        return RequestPlan(
            provider="noaa",
            method="GET",
            url="https://www.ncei.noaa.gov/cdo-web/api/v2/data",
            headers={"token": "${NOAA_TOKEN}"},
            query={
                "datasetid": _clean(dataset_id, "dataset_id"),
                "locationid": _clean(location_id, "location_id"),
                "startdate": _clean(start_date, "start_date"),
                "enddate": _clean(end_date, "end_date"),
                "limit": str(limit),
                "units": "standard",
            },
            secret_names=("NOAA_TOKEN",),
            notes=("NOAA access tokens are free.", "Cache responses and retain dataset/location identifiers."),
        )

    def sec_company_facts(self, cik: str, *, contact: str = "research@example.com") -> RequestPlan:
        normalized = "".join(character for character in cik if character.isdigit()).zfill(10)
        if len(normalized) != 10:
            raise ValueError("CIK must contain at most ten digits")
        return RequestPlan(
            provider="sec_edgar",
            method="GET",
            url=f"https://data.sec.gov/api/xbrl/companyfacts/CIK{normalized}.json",
            headers={"User-Agent": f"ShortsPipelineReviewPrototype {contact}"},
            notes=("No API key required.", "Production must provide a real contact address and obey SEC request-rate guidance."),
        )


@dataclass(frozen=True)
class ResearchBundle:
    topic: ResearchTopic
    plans: tuple[RequestPlan, ...]
    source_priority: tuple[str, ...]


class PublicDataResearchPlanner:
    def __init__(self, adapters: FreeResearchAdapters | None = None) -> None:
        self.adapters = adapters or FreeResearchAdapters()

    def discovery_bundle(self, topic: ResearchTopic) -> ResearchBundle:
        escaped = topic.query.replace('"', '\\"')
        sparql = f'SELECT ?item ?itemLabel WHERE {{ ?item rdfs:label "{escaped}"@en . SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }} }} LIMIT 25'
        plans = (
            self.adapters.gdelt(topic.query, max_records=50),
            self.adapters.wikidata(sparql),
            self.adapters.wikipedia_summary(topic.query),
            self.adapters.common_crawl_indexes(),
        )
        return ResearchBundle(topic, plans, ("primary_source", "government_data", "structured_knowledge", "news_discovery", "archive"))
