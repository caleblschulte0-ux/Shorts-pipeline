from __future__ import annotations

from .contracts import AudienceSignal, ChannelProfile, CompetitorObservation, MediaAsset
from .creative import Idea


def audience_signals() -> tuple[AudienceSignal, ...]:
    return (AudienceSignal("v1", "c1", "Why does the cartridge say empty when it still has ink?", 120, 8), AudienceSignal("v1", "c2", "Please do one on printers blocking third party ink", 80, 3), AudienceSignal("v2", "c3", "Why do printers block third party ink cartridges?", 150, 12))


def competitor_observations() -> tuple[CompetitorObservation, ...]:
    return (CompetitorObservation("v1", "Ink scam", 26, 12, 400000, "Your printer is lying.", "EMPTY?", 4, 18, "center", (0, 1.4, 2.8, 4.2, 6.0)), CompetitorObservation("v2", "Printer secret", 31, 24, 500000, "Why is ink so expensive?", "$75", 3, 21, "lower-third", (0, 1.8, 3.3, 5.0, 7.1)))


def media_assets() -> tuple[MediaAsset, ...]:
    return (MediaAsset("pexels", "a1", "https://example.test/a1", "https://example.test/a1.mp4", "video", 1080, 1920, 8, "Pexels", description="printer close-up", content_hash="abc"), MediaAsset("wikimedia", "a2", "https://example.test/a2", "https://example.test/a2.jpg", "image", 1600, 900, 0, "CC-BY-SA", description="historic printer", content_hash="def"), MediaAsset("archive", "a3", "https://example.test/a3", "https://example.test/a3.mp4", "video", 1080, 1920, 12, "PDM-1.0", description="factory footage", content_hash="abc"))


def channels() -> tuple[ChannelProfile, ...]:
    return (ChannelProfile("daily", ("business", "technology", "news"), ("text_card", "narrated")), ChannelProfile("explainer", ("data", "business", "science"), ("graph_race", "narrated")), ChannelProfile("curiosity", ("history", "science", "technology"), ("narrated", "animation")))


def idea() -> Idea:
    return Idea("idea_1", "Why printers reject full cartridges", "Electronic locks can reject cartridges that still contain ink.", ("technology", "business"), ("narrated",))
