from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import re
from statistics import median
from typing import Iterable, Sequence

from .contracts import AudienceSignal, CommandPlan, CompetitorObservation, RequestPlan
from .providers import YouTubeAdapter


@dataclass(frozen=True)
class DemandCluster:
    category: str
    phrase: str
    count: int
    total_likes: int
    examples: tuple[str, ...]


class CommentMiner:
    _QUESTION = re.compile(r"\?|\b(why|how|what|when|where|who|can|does|did|is|are)\b", re.I)
    _REQUEST = re.compile(r"\b(please|next|do one on|make a video|cover|part 2|talk about)\b", re.I)
    _CORRECTION = re.compile(r"\b(actually|wrong|incorrect|not true|correction|misleading)\b", re.I)
    _CONFLICT = re.compile(r"\b(disagree|agree|scam|fake|lie|bullshit|debate)\b", re.I)

    def classify(self, text: str) -> tuple[str, ...]:
        categories: list[str] = []
        if self._QUESTION.search(text): categories.append("question")
        if self._REQUEST.search(text): categories.append("request")
        if self._CORRECTION.search(text): categories.append("correction")
        if self._CONFLICT.search(text): categories.append("conflict")
        if not categories: categories.append("reaction")
        return tuple(categories)

    def phrases(self, text: str, *, max_words: int = 6) -> tuple[str, ...]:
        clean = re.sub(r"[^A-Za-z0-9' ]+", " ", text.lower())
        words = [word for word in clean.split() if len(word) > 2]
        phrases: list[str] = []
        for width in (3, 4, 5, 6):
            if width > max_words: break
            for index in range(0, max(0, len(words) - width + 1)):
                phrase = " ".join(words[index:index + width])
                if phrase not in phrases: phrases.append(phrase)
        return tuple(phrases[:12])

    def enrich(self, signal: AudienceSignal) -> AudienceSignal:
        return AudienceSignal(signal.source_video_id, signal.comment_id, signal.text, signal.likes, signal.reply_count, self.classify(signal.text), self.phrases(signal.text))

    def cluster(self, signals: Iterable[AudienceSignal], *, minimum_count: int = 2) -> tuple[DemandCluster, ...]:
        phrase_rows: dict[tuple[str, str], list[AudienceSignal]] = defaultdict(list)
        for raw in signals:
            signal = self.enrich(raw)
            for category in signal.categories:
                for phrase in signal.extracted_phrases:
                    phrase_rows[(category, phrase)].append(signal)
        clusters = [DemandCluster(category, phrase, len(rows), sum(row.likes for row in rows), tuple(row.text for row in rows[:3])) for (category, phrase), rows in phrase_rows.items() if len(rows) >= minimum_count]
        return tuple(sorted(clusters, key=lambda cluster: (cluster.count, cluster.total_likes), reverse=True))


@dataclass(frozen=True)
class CompetitorPattern:
    median_duration: float
    median_views_per_hour: float
    median_first_five_second_cuts: float
    median_payoff_second: float | None
    common_hook_forms: tuple[tuple[str, int], ...]
    recommended_visual_change_interval: float | None


class CompetitorAnalyzer:
    def summarize(self, observations: Sequence[CompetitorObservation]) -> CompetitorPattern:
        if not observations: raise ValueError("no competitor observations")
        hooks: Counter[str] = Counter(self._hook_form(item.hook_text) for item in observations)
        payoffs = [item.payoff_second for item in observations if item.payoff_second is not None]
        intervals: list[float] = []
        for item in observations:
            intervals.extend(b - a for a, b in zip(item.visual_change_seconds, item.visual_change_seconds[1:]) if b > a)
        return CompetitorPattern(median(item.duration_seconds for item in observations), median(item.views_per_hour for item in observations), median(item.first_five_second_cuts for item in observations), median(payoffs) if payoffs else None, tuple(hooks.most_common(5)), median(intervals) if intervals else None)

    def outperformance(self, item: CompetitorObservation, cohort: Sequence[CompetitorObservation]) -> float:
        baseline = median(row.views_per_hour for row in cohort) if cohort else 1.0
        return item.views_per_hour / max(baseline, 1.0)

    @staticmethod
    def _hook_form(text: str) -> str:
        value = text.strip().lower()
        if not value: return "missing"
        if value.endswith("?") or value.startswith(("why ", "how ", "what ", "did ", "can ")): return "question"
        if any(token in value for token in ("never", "secret", "actually", "truth")): return "reveal"
        if re.search(r"\d", value): return "number"
        if any(token in value for token in ("but", "however", "instead", "vs")): return "conflict"
        return "claim"


class YouTubeResearchPlanner:
    def __init__(self) -> None:
        self.youtube = YouTubeAdapter()

    def competitor_requests(self, query: str, video_ids: tuple[str, ...] = ()) -> tuple[RequestPlan, ...]:
        plans: list[RequestPlan] = [self.youtube.search_videos(query)]
        if video_ids:
            plans.append(self.youtube.video_details(video_ids))
            plans.extend(self.youtube.comment_threads(video_id) for video_id in video_ids)
        return tuple(plans)


@dataclass(frozen=True)
class EvidenceCapture:
    url: str
    selector: str
    output_png: str
    highlight_text: str = ""
    viewport_width: int = 1080
    viewport_height: int = 1920
    scroll_steps: int = 0


class BrowserEvidencePlanner:
    def screenshot(self, capture: EvidenceCapture) -> CommandPlan:
        args = ("python", "-m", "review_prototypes.capability_studio.browser_capture", "--url", capture.url, "--selector", capture.selector, "--output", capture.output_png, "--width", str(capture.viewport_width), "--height", str(capture.viewport_height), "--scroll-steps", str(capture.scroll_steps), "--highlight", capture.highlight_text)
        return CommandPlan("playwright", args, outputs=(capture.output_png,), notes=("Requires a deliberately reviewed network-enabled adapter before production use.",))

    def animate_still(self, image: str, output: str, *, duration: float = 4.0, zoom: float = 1.08) -> CommandPlan:
        frames = max(1, int(duration * 30))
        vf = f"zoompan=z='min(zoom+0.0008,{zoom})':d={frames}:s=1080x1920:fps=30"
        return CommandPlan("ffmpeg", ("ffmpeg", "-y", "-loop", "1", "-i", image, "-vf", vf, "-t", str(duration), "-pix_fmt", "yuv420p", output), inputs=(image,), outputs=(output,))

    def pdf_page(self, pdf: str, output_prefix: str, *, dpi: int = 180) -> CommandPlan:
        return CommandPlan("pdftoppm", ("pdftoppm", "-png", "-r", str(dpi), pdf, output_prefix), inputs=(pdf,), outputs=(output_prefix,), notes=("Use OCR only when parsed text is unavailable.",))
