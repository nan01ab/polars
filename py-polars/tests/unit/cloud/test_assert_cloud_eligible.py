from pathlib import Path

import pyarrow.dataset as ds
import pytest

import polars as pl
from polars._utils.cloud import assert_cloud_eligible

CLOUD_PATH = "s3://my-nonexistent-bucket/dataset"


@pytest.mark.parametrize(
    "lf",
    [
        pl.scan_parquet(CLOUD_PATH).select("c", pl.lit(2)).with_row_index(),
        pl.LazyFrame({"a": [1, 2], "b": [3, 4]})
        .select("a", "b")
        .filter(pl.col("a") == pl.lit(1)),
    ],
)
def test_assert_cloud_eligible(lf: pl.LazyFrame) -> None:
    assert_cloud_eligible(lf)


@pytest.mark.parametrize(
    "lf",
    [
        pl.LazyFrame({"a": [1, 2], "b": [3, 4]}).select(
            pl.col("a").map_elements(lambda x: sum(x))
        ),
        pl.LazyFrame({"a": [1, 2], "b": [3, 4]}).select(
            pl.col("b").map_batches(lambda x: sum(x))
        ),
        pl.LazyFrame({"a": [{"x": 1, "y": 2}]}).select(
            pl.col("a").name.map(lambda x: x.upper())
        ),
        pl.LazyFrame({"a": [{"x": 1, "y": 2}]}).select(
            pl.col("a").name.map_fields(lambda x: x.upper())
        ),
        pl.LazyFrame({"a": [1, 2], "b": [3, 4]}).map_batches(lambda x: x),
        pl.LazyFrame({"a": [1, 2], "b": [3, 4]})
        .group_by("a")
        .map_groups(lambda x: x, schema={"b": pl.Int64}),
        pl.LazyFrame({"a": [1, 2], "b": [3, 4]})
        .group_by("a")
        .agg(pl.col("b").map_batches(lambda x: sum(x))),
        pl.scan_parquet(CLOUD_PATH).filter(
            pl.col("a") < pl.lit(1).map_elements(lambda x: x + 1)
        ),
    ],
)
def test_assert_cloud_eligible_fail_on_udf(lf: pl.LazyFrame) -> None:
    with pytest.raises(
        AssertionError, match="logical plan ineligible for execution on Polars Cloud"
    ):
        assert_cloud_eligible(lf)


@pytest.mark.parametrize(
    "lf",
    [
        pl.scan_parquet("data.parquet"),
        pl.scan_ndjson(Path("data.ndjson")),
        pl.scan_csv("data-*.csv"),
        pl.scan_ipc(["data-1.feather", "data-2.feather"]),
    ],
)
def test_assert_cloud_eligible_fail_on_local_data_source(lf: pl.LazyFrame) -> None:
    with pytest.raises(
        AssertionError, match="logical plan ineligible for execution on Polars Cloud"
    ):
        assert_cloud_eligible(lf)


@pytest.mark.write_disk()
def test_assert_cloud_eligible_fail_on_python_scan(tmp_path: Path) -> None:
    tmp_path.mkdir(exist_ok=True)
    data_path = tmp_path / "data.parquet"
    pl.DataFrame({"a": [1, 2]}).write_parquet(data_path)
    dataset = ds.dataset(data_path, format="parquet")

    lf = pl.scan_pyarrow_dataset(dataset)
    with pytest.raises(
        AssertionError, match="logical plan ineligible for execution on Polars Cloud"
    ):
        assert_cloud_eligible(lf)
