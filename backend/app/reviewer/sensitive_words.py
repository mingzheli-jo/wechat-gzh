from pathlib import Path


class SensitiveWordChecker:
    def __init__(self, words: list[str]) -> None:
        self._words = [w for w in words if w]

    @classmethod
    def from_file(cls, path: Path) -> "SensitiveWordChecker":
        words: list[str] = []
        for raw in Path(path).read_text(encoding="utf-8").splitlines():
            stripped = raw.strip()
            if not stripped or stripped.startswith("#"):
                continue
            words.append(stripped)
        return cls(words)

    def check(self, text: str) -> list[str]:
        return sorted({w for w in self._words if w in text})
