"""Download curated Census ZIPs without extracting or changing their contents."""

import shutil
from urllib.request import urlopen

from catalog import SOURCES
from census import DATA_DIR


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for source in SOURCES.values():
        target = DATA_DIR / source.filename
        if target.exists():
            print(f"Already downloaded: {target.name}")
            continue
        partial = target.with_suffix(target.suffix + ".part")
        print(f"Downloading {source.url}")
        try:
            with urlopen(source.url, timeout=60) as response, partial.open("wb") as out:
                shutil.copyfileobj(response, out)
            partial.replace(target)
        finally:
            partial.unlink(missing_ok=True)
        print(f"Saved {target.name} ({target.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
