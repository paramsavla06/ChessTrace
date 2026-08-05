from dataclasses import dataclass, field


@dataclass
class ImportSummary:
    processed: int = 0
    imported: int = 0
    skipped: int = 0
    failed: int = 0
    game_ids: list[int] = field(default_factory=list)
