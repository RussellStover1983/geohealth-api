from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("pandas", reason="ETL tests require pandas (install with .[dev,etl])")

from geohealth.etl.load_all import run_pipeline, query_loaded_states


def _make_engine_mock():
    engine = MagicMock()
    conn = MagicMock()
    engine.begin.return_value.__enter__ = MagicMock(return_value=conn)
    engine.begin.return_value.__exit__ = MagicMock(return_value=False)
    engine.connect.return_value.__enter__ = MagicMock(return_value=conn)
    engine.connect.return_value.__exit__ = MagicMock(return_value=False)
    return engine


@patch("geohealth.etl.compute_sdoh_index.compute_for_state", return_value=100)
@patch("geohealth.etl.load_places.load_state", return_value=100)
@patch("geohealth.etl.load_svi.load_state", return_value=100)
@patch("geohealth.etl.load_svi._download_svi")
@patch("geohealth.etl.load_acs.load_state", return_value=100)
@patch("geohealth.etl.load_tiger.load_state", return_value=100)
@patch("geohealth.etl.load_tiger.ensure_table")
@patch("geohealth.etl.load_all.query_loaded_states", return_value=set())
def test_all_steps_called_in_order(
    mock_loaded, mock_ensure, mock_tiger, mock_acs, mock_svi_download,
    mock_svi, mock_places, mock_sdoh,
):
    """All 5 ETL steps should be called for each state."""
    mock_svi_download.return_value = MagicMock()
    engine = _make_engine_mock()

    success, failed = run_pipeline(["27", "06"], year=2022, places_year=2023, engine=engine)

    assert success == 2
    assert failed == 0
    assert mock_tiger.call_count == 2
    assert mock_acs.call_count == 2
    assert mock_svi.call_count == 2
    assert mock_places.call_count == 2
    assert mock_sdoh.call_count == 2


@patch("geohealth.etl.compute_sdoh_index.compute_for_state", return_value=100)
@patch("geohealth.etl.load_places.load_state", return_value=100)
@patch("geohealth.etl.load_svi.load_state", return_value=100)
@patch("geohealth.etl.load_svi._download_svi")
@patch("geohealth.etl.load_acs.load_state", return_value=100)
@patch("geohealth.etl.load_tiger.load_state")
@patch("geohealth.etl.load_tiger.ensure_table")
@patch("geohealth.etl.load_all.query_loaded_states", return_value=set())
def test_per_state_failure_continues(
    mock_loaded, mock_ensure, mock_tiger, mock_acs, mock_svi_download,
    mock_svi, mock_places, mock_sdoh,
):
    """Failure in one state should not prevent processing of the next."""
    mock_svi_download.return_value = MagicMock()
    mock_tiger.side_effect = [Exception("download error"), 100]
    engine = _make_engine_mock()

    success, failed = run_pipeline(["27", "06"], year=2022, places_year=2023, engine=engine)

    assert success == 1
    assert failed == 1


@patch("geohealth.etl.compute_sdoh_index.compute_for_state", return_value=100)
@patch("geohealth.etl.load_places.load_state", return_value=100)
@patch("geohealth.etl.load_svi.load_state", return_value=100)
@patch("geohealth.etl.load_svi._download_svi")
@patch("geohealth.etl.load_acs.load_state", return_value=100)
@patch("geohealth.etl.load_tiger.load_state", return_value=100)
@patch("geohealth.etl.load_tiger.ensure_table")
@patch("geohealth.etl.load_all.query_loaded_states")
def test_resume_skips_tiger_for_loaded_states(
    mock_loaded, mock_ensure, mock_tiger, mock_acs, mock_svi_download,
    mock_svi, mock_places, mock_sdoh,
):
    """--resume should skip TIGER for states already in DB."""
    mock_svi_download.return_value = MagicMock()
    mock_loaded.return_value = {"27"}
    engine = _make_engine_mock()

    success, failed = run_pipeline(
        ["27", "06"], year=2022, places_year=2023, engine=engine, resume=True
    )

    assert success == 2
    assert failed == 0
    # TIGER should only be called for state 06
    assert mock_tiger.call_count == 1
    mock_tiger.assert_called_once_with(2022, "06", engine)
    # But ACS should be called for both
    assert mock_acs.call_count == 2


@patch("geohealth.etl.compute_sdoh_index.compute_for_state", return_value=100)
@patch("geohealth.etl.load_places.load_state", return_value=100)
@patch("geohealth.etl.load_svi.load_state", return_value=100)
@patch("geohealth.etl.load_svi._download_svi")
@patch("geohealth.etl.load_acs.load_state", return_value=100)
@patch("geohealth.etl.load_tiger.load_state", return_value=100)
@patch("geohealth.etl.load_tiger.ensure_table")
@patch("geohealth.etl.load_all.query_loaded_states", return_value=set())
def test_svi_downloaded_once(
    mock_loaded, mock_ensure, mock_tiger, mock_acs, mock_svi_download,
    mock_svi, mock_places, mock_sdoh,
):
    """SVI national CSV should be downloaded only once across all states."""
    svi_df = MagicMock()
    mock_svi_download.return_value = svi_df
    engine = _make_engine_mock()

    run_pipeline(["27", "06", "48"], year=2022, places_year=2023, engine=engine)

    mock_svi_download.assert_called_once()
    assert mock_svi.call_count == 3
    # Each call should pass the same svi_df
    for c in mock_svi.call_args_list:
        assert c[0][0] is svi_df


def test_query_loaded_states():
    """query_loaded_states should return a set of FIPS codes."""
    engine = MagicMock()
    mock_conn = MagicMock()
    engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
    engine.connect.return_value.__exit__ = MagicMock(return_value=False)
    mock_conn.execute.return_value = [("27",), ("06",)]

    result = query_loaded_states(engine)
    assert result == {"27", "06"}
