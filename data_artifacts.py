import gzip
import json
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, List, Tuple, Union


ROOT = Path(__file__).resolve().parent
DEFAULT_CACHE_PATH = ROOT / "cache" / "cache.jsonl.gz"
DEFAULT_PARQUET_PATH = ROOT / "cache" / "papers.parquet"
PathLike = Union[str, Path]


@contextmanager
def open_cache(cache_path: Path):
    if cache_path.suffix == ".gz":
        with gzip.open(cache_path, "rt", encoding="utf-8") as handle:
            yield handle
    else:
        with cache_path.open("r", encoding="utf-8") as handle:
            yield handle


def iter_cache_records(cache_path: PathLike) -> Iterable[dict]:
    cache_path = Path(cache_path)
    with open_cache(cache_path) as handle:
        for line_num, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            conf = record.get("conf")
            if not conf:
                raise ValueError(f"Missing conf on line {line_num} of {cache_path}")
            authors = record.get("paper_authors") or []
            if not isinstance(authors, list):
                authors = [str(authors)]
            yield {
                "conf": str(conf),
                "paper_name": record.get("paper_name") or "",
                "paper_url": record.get("paper_url") or "",
                "paper_authors": [str(author) for author in authors],
                "paper_abstract": record.get("paper_abstract") or "",
                "paper_code": record.get("paper_code") or "#",
            }


def build_parquet(
    cache_path: PathLike = DEFAULT_CACHE_PATH,
    output_path: PathLike = DEFAULT_PARQUET_PATH,
    batch_size: int = 10000,
) -> Tuple[Path, int]:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise RuntimeError(
            "Parquet export requires pyarrow. Install requirements.txt first."
        ) from exc

    cache_path = Path(cache_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    if tmp_path.exists():
        tmp_path.unlink()

    schema = pa.schema(
        [
            ("conf", pa.string()),
            ("paper_name", pa.string()),
            ("paper_url", pa.string()),
            ("paper_authors", pa.list_(pa.string())),
            ("paper_abstract", pa.string()),
            ("paper_code", pa.string()),
        ]
    )

    writer = None
    batch = []
    total = 0
    try:
        for record in iter_cache_records(cache_path):
            batch.append(record)
            if len(batch) >= batch_size:
                writer = _write_parquet_batch(tmp_path, schema, writer, batch)
                total += len(batch)
                batch.clear()
        if batch:
            writer = _write_parquet_batch(tmp_path, schema, writer, batch)
            total += len(batch)
        if writer is None:
            writer = pq.ParquetWriter(tmp_path, schema, compression="zstd")
    finally:
        if writer is not None:
            writer.close()

    os.replace(tmp_path, output_path)
    return output_path, total


def _write_parquet_batch(tmp_path: Path, schema, writer, batch: List[dict]):
    import pyarrow as pa
    import pyarrow.parquet as pq

    if writer is None:
        writer = pq.ParquetWriter(tmp_path, schema, compression="zstd")
    table = pa.Table.from_pylist(batch, schema=schema)
    writer.write_table(table)
    return writer


def upload_to_huggingface(paths: Iterable[PathLike], commit_message: str) -> List[str]:
    repo_id = os.getenv("PAPERVAULT_HF_REPO_ID")
    if not repo_id:
        print("[*] PAPERVAULT_HF_REPO_ID is not set; skipping Hugging Face upload.")
        return []

    try:
        from huggingface_hub import HfApi
    except ImportError as exc:
        raise RuntimeError(
            "Hugging Face upload requires huggingface_hub. Install requirements.txt first."
        ) from exc

    repo_type = os.getenv("PAPERVAULT_HF_REPO_TYPE", "dataset")
    api = HfApi(token=os.getenv("HF_TOKEN") or None)
    uploaded = []
    for path in paths:
        path = Path(path).resolve()
        if not path.exists():
            continue
        path_in_repo = path.relative_to(ROOT).as_posix()
        api.upload_file(
            path_or_fileobj=str(path),
            path_in_repo=path_in_repo,
            repo_id=repo_id,
            repo_type=repo_type,
            commit_message=commit_message,
        )
        uploaded.append(path_in_repo)
        print(f"[+] Uploaded to Hugging Face: {repo_id}/{path_in_repo}")
    return uploaded


def sync_cache_artifacts(
    cache_path: PathLike = DEFAULT_CACHE_PATH,
    parquet_path: PathLike = DEFAULT_PARQUET_PATH,
    upload: bool = True,
    commit_message: str = "Update PaperVault data artifacts",
) -> None:
    cache_path = Path(cache_path)
    parquet_path = Path(parquet_path)

    parquet_file, count = build_parquet(cache_path, parquet_path)
    print(f"[+] Parquet generated: {parquet_file} ({count} papers)")

    if upload:
        upload_to_huggingface(
            [cache_path, parquet_file],
            commit_message=commit_message,
        )
