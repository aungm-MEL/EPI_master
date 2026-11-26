import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import create_epi_overall as overall
from create_epi_master_sheet import (
    build_cmu_indicator,
    build_cummulative,
    build_indicator,
    build_vthc,
)


class PrfYearFilterTest(unittest.TestCase):
    def test_pipeline_filters_prf_only_across_report_sheets(self):
        source_sheets = {
            "kdhw": ["VTHC_Doses disaggregate", "Cummulative_sheet", "Cummu_indicator", "Indicator", "TD2_indicator", "Td_ALOD"],
            "kna": ["Summary", "yearly_cumulative", "ALOD_cummu", "indicators", "Td2_indicator", "Td_alod"],
            "chdn": ["Summary", "yearly_cumulative", "ALOD_cummu", "indicators", "Td2_indicator", "Td_ALOD"],
            "prf": ["Summary", "yearly_cumulative", "ALOD_cummu", "indicators"],
        }
        columns = [
            overall.VTHC_COLUMNS,
            overall.CUMULATIVE_COLUMNS,
            overall.ALOD_CUMMU_COLUMNS,
            overall.INDICATOR_COLUMNS,
            overall.TD2_COLUMNS,
            overall.TD_ALOD_COLUMNS,
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for source, sheets in source_sheets.items():
                with pd.ExcelWriter(root / f"{source}.xlsx") as writer:
                    for index, name in enumerate(sheets):
                        years = [2025, 2026, 2027, None] if source == "prf" else [2025]
                        rows = pd.DataFrame(
                            [{"Year": year, "Organization": source} for year in years]
                        ).reindex(columns=columns[index])
                        if index == 2 and source != "kdhw":
                            rows = rows.drop(columns="Indicator")
                        if source == "prf" and index == 1:
                            rows = rows.rename(columns={"Year": "period"})
                        if source == "prf" and index == 2:
                            rows = rows.rename(columns={"Year": "Period"})
                        rows.to_excel(writer, sheet_name=name, index=False)

            output = root / "overall.xlsx"
            args = ["create_epi_overall.py"]
            for source in source_sheets:
                args.extend([f"--{source}", str(root / f"{source}.xlsx")])
            args.extend(["--output", str(output)])
            with patch.object(sys, "argv", args):
                overall.main()

            reports = {
                "VTHC_Doses disaggregate": build_vthc,
                "Cummulative": build_cummulative,
                "ALOD_cummu": build_cmu_indicator,
                "indicators": build_indicator,
            }
            for sheet, builder in reports.items():
                with self.subTest(sheet=sheet):
                    frame = pd.read_excel(output, sheet_name=sheet)
                    self.assertEqual(frame.loc[frame["Organization"] == "prf", "Year"].tolist(), [2026])
                    self.assertEqual(frame.loc[frame["Organization"] != "prf", "Year"].tolist(), [2025] * 3)
                    master = builder(frame)
                    self.assertEqual(set(master.loc[master["Organization"] == "prf", "Year"]), {2026})
                    self.assertEqual(set(master.loc[master["Organization"] != "prf", "Year"]), {2025})

            for sheet in ("Td2_indicator", "Td_ALOD"):
                frame = pd.read_excel(output, sheet_name=sheet)
                self.assertEqual(frame["Organization"].tolist(), ["kdhw", "kna", "chdn"])

    def test_prf_with_no_readable_year_fails(self):
        frame = pd.DataFrame({"Year": [None], "Organization": ["prf"]})
        with self.assertRaisesRegex(ValueError, "no readable Year"):
            overall.filter_prf_2026(frame, "Summary")


if __name__ == "__main__":
    unittest.main()
