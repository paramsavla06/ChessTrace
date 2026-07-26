from dataclasses import dataclass


@dataclass(slots=True)
class ImportSummary:
    processed: int = 0
    imported: int = 0
    skipped: int = 0
    failed: int = 0
