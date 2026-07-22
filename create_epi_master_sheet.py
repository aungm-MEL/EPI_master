from __future__ import annotations

import argparse
import importlib
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple
from urllib.parse import urlparse

import pandas as pd


VTHC_LAT_LONG_MAP: Dict[str, str] = {
    "Hpruso": "19.41371920655298, 97.12808848224114",
    "Loikaw": "19.674987784319832, 97.21586410248338",
    "Demoso": "19.549409069246945, 97.15318439683296",
    "Mobyae": "19.74359740772167, 97.08905672999389",
    "Pekon": "19.85476300470482, 97.00081399281648",
    "Bilin": "17.412504872457955, 97.37865441198204",
    "Dawei": "14.087083169361211, 98.18876153804929",
    "Hlaingbwe": "17.123471508053957, 97.81681489474765",
    "Hpa-an": "16.873356585425828, 97.63984282832611",
    "Hpapun": "18.076955032431393, 97.45014263348429",
    "Htantabin": "18.845266800080726, 96.48122670441902",
    "Kawkareik": "16.557184115554183, 98.23905909187735",
    "Kyaikto": "17.313787231231927, 97.01402988401479",
    "Kyainseikgyi": "16.04055444014056, 98.12170740121576",
    "Kyaukkyi": "18.33696130836575, 96.7771480542691",
    "Myawaddy": "16.682062882815853, 98.50680539953483",
    "Shwegyin": "17.929986949713754, 96.88085314350398",
    "Tanintharyi": "12.038030338892476, 98.67544992877913",
    "Thandaunggyi": "19.07236907306163, 96.67837849903596",
    "Thaton": "16.931252402263876, 97.3681343111516",
    "Ye": "15.249116911619446, 97.8563187273287",
    "Hpasawng": "18.871366250483685, 97.3155318797221",
    "Mese": "18.644294867077328, 97.65343532382707",
    "Shadaw": "19.52340244368902, 97.7387743653126",
}


Spec = Tuple[int, Sequence[Tuple[str, str]]]


def build_long(
    source_df: pd.DataFrame,
    base_col_count: int,
    specs: Iterable[Spec],
    value_col_name: str,
) -> pd.DataFrame:
    """Build a long table from repeated value columns and metadata specs."""
    base = source_df.iloc[:, :base_col_count].copy()
    out_frames: List[pd.DataFrame] = []

    for source_col_1_based, extras in specs:
        value = source_df.iloc[:, [source_col_1_based - 1]].copy()
        block = pd.concat([base.copy(), value], axis=1)
        block.columns = [*base.columns, value_col_name]
        for key, val in extras:
            block[key] = val
        out_frames.append(block)

    return pd.concat(out_frames, ignore_index=True)


def to_numeric_round(df: pd.DataFrame, col: str, digits: int = 2) -> pd.DataFrame:
    result = df.copy()
    result[col] = pd.to_numeric(result[col], errors="coerce").round(digits)
    return result


def _year_to_text(value: object) -> str:
    if pd.isna(value):
        return ""
    try:
        return str(int(float(value)))
    except (ValueError, TypeError):
        return str(value).strip()


def apply_dynamic_period_from_year(df: pd.DataFrame) -> pd.DataFrame:
    """Build period labels like Q1_2024 or 2024_Annual using each row's Year."""
    if "period" not in df.columns or "Year" not in df.columns:
        return df

    out = df.copy()
    years = out["Year"].map(_year_to_text)

    def _build_period(template: str, year_text: str) -> str:
        if not year_text:
            return template
        if "Annual" in template:
            return f"{year_text}_Annual"

        token = template.split("_", 1)[0]
        if token.upper().startswith(("Q", "S")):
            return f"{token}_{year_text}"
        return f"{template}_{year_text}"

    out["period"] = [
        _build_period(str(template), year_text)
        for template, year_text in zip(out["period"], years)
    ]
    return out


def build_vthc(vthc: pd.DataFrame) -> pd.DataFrame:
    specs: List[Spec] = [
        (9, (("indicator", "At_least_one_dose"), ("AgeGroup", "Under 1-yr-old"))),
        (10, (("indicator", "At_least_one_dose"), ("AgeGroup", "1to5-yr-old"))),
        (11, (("indicator", "At_least_one_dose"), ("AgeGroup", ">5-yr-old"))),
        (13, (("indicator", "BCG"), ("AgeGroup", "1to5-yr-old"))),
        (12, (("indicator", "BCG"), ("AgeGroup", "Under 1-yr-old"))),
        (25, (("indicator", "Penta1"), ("AgeGroup", "1to5-yr-old"))),
        (24, (("indicator", "Penta1"), ("AgeGroup", "Under 1-yr-old"))),
        (26, (("indicator", "Penta1"), ("AgeGroup", ">5-yr-old"))),
        (27, (("indicator", "Penta2"), ("AgeGroup", "Under 1-yr-old"))),
        (28, (("indicator", "Penta2"), ("AgeGroup", "1to5-yr-old"))),
        (29, (("indicator", "Penta2"), ("AgeGroup", ">5-yr-old"))),
        (30, (("indicator", "Penta3"), ("AgeGroup", "Under 1-yr-old"))),
        (31, (("indicator", "Penta3"), ("AgeGroup", "1to5-yr-old"))),
        (32, (("indicator", "Penta3"), ("AgeGroup", ">5-yr-old"))),
        (15, (("indicator", "OPV1"), ("AgeGroup", "Under 1-yr-old"))),
        (16, (("indicator", "OPV1"), ("AgeGroup", "1to5-yr-old"))),
        (17, (("indicator", "OPV1"), ("AgeGroup", ">5-yr-old"))),
        (18, (("indicator", "OPV2"), ("AgeGroup", "Under 1-yr-old"))),
        (19, (("indicator", "OPV2"), ("AgeGroup", "1to5-yr-old"))),
        (20, (("indicator", "OPV2"), ("AgeGroup", ">5-yr-old"))),
        (21, (("indicator", "OPV3"), ("AgeGroup", "Under 1-yr-old"))),
        (22, (("indicator", "OPV3"), ("AgeGroup", "1to5-yr-old"))),
        (23, (("indicator", "OPV3"), ("AgeGroup", ">5-yr-old"))),
        (33, (("indicator", "MMR1"), ("AgeGroup", "Under 1-yr-old"))),
        (34, (("indicator", "MMR1"), ("AgeGroup", "1to5-yr-old"))),
        (35, (("indicator", "MMR1"), ("AgeGroup", ">5-yr-old"))),
        (36, (("indicator", "MMR2"), ("AgeGroup", "Under 1-yr-old"))),
        (37, (("indicator", "MMR2"), ("AgeGroup", "1to5-yr-old"))),
        (38, (("indicator", "MMR2"), ("AgeGroup", ">5-yr-old"))),
        (39, (("indicator", "JE"), ("AgeGroup", "Under 1-yr-old"))),
        (40, (("indicator", "JE"), ("AgeGroup", "1to5-yr-old"))),
        (41, (("indicator", "JE"), ("AgeGroup", ">5-yr-old"))),
        (42, (("indicator", "IPV"), ("AgeGroup", "Under 1-yr-old"))),
        (43, (("indicator", "IPV"), ("AgeGroup", "1to5-yr-old"))),
        (44, (("indicator", "IPV"), ("AgeGroup", ">5-yr-old"))),
        (45, (("indicator", "complete_dose"), ("AgeGroup", "Under 1-yr-old"))),
        (46, (("indicator", "complete_dose"), ("AgeGroup", "1to5-yr-old"))),
        (47, (("indicator", "complete_dose"), ("AgeGroup", ">5-yr-old"))),
        (48, (("indicator", "Td1"), ("AgeGroup", "PW"))),
        (49, (("indicator", "Td2"), ("AgeGroup", "PW"))),
        (50, (("indicator", "Td_At_least_one"), ("AgeGroup", "PW"))),
    ]
    return to_numeric_round(build_long(vthc, 8, specs, "Achievement"), "Achievement", 2)


def build_cummulative(cummulative: pd.DataFrame) -> pd.DataFrame:
    specs: List[Spec] = [
        (8, (("Doses", "At_least_one_dose"), ("AgeGroup", "Under 1-yr-old"))),
        (9, (("Doses", "At_least_one_dose"), ("AgeGroup", "1to5-yr-old"))),
        (10, (("Doses", "At_least_one_dose"), ("AgeGroup", ">5-yr-old"))),
        (11, (("Doses", "Td_at_least_one_dose"), ("AgeGroup", "PW"))),
        (12, (("Doses", "U5_population"), ("AgeGroup", "U5target"))),
    ]
    out = to_numeric_round(build_long(cummulative, 7, specs, "Achievement"), "Achievement", 2)

    is_target_row = out["AgeGroup"] == "U5target"
    keep_mask = (is_target_row & (out["Doses"] == "U5_population")) | (
        (~is_target_row) & (out["Doses"] != "U5_population")
    )
    out = out[keep_mask].copy()

    if "Twp_MIMU" in out.columns:
        out["Lat_Long"] = out["Twp_MIMU"].map(VTHC_LAT_LONG_MAP)
    return out


def build_indicator(indicator: pd.DataFrame) -> pd.DataFrame:
    specs: List[Spec] = [
        (5, (("period", "Q1_2025"), ("TvA", "target"), ("Gender", "Combine"), ("AgeGroup", "U5"))),
        (6, (("period", "Q1_2025"), ("TvA", "achievement"), ("Gender", "Male"), ("AgeGroup", "U1"))),
        (7, (("period", "Q1_2025"), ("TvA", "achievement"), ("Gender", "Female"), ("AgeGroup", "U1"))),
        (9, (("period", "Q1_2025"), ("TvA", "achievement"), ("Gender", "Female"), ("AgeGroup", "1to5"))),
        (8, (("period", "Q1_2025"), ("TvA", "achievement"), ("Gender", "Male"), ("AgeGroup", "1to5"))),
        (14, (("period", "Q2_2025"), ("TvA", "achievement"), ("Gender", "Female"), ("AgeGroup", "1to5"))),
        (10, (("period", "Q2_2025"), ("TvA", "target"), ("Gender", "Combine"), ("AgeGroup", "U5"))),
        (13, (("period", "Q2_2025"), ("TvA", "achievement"), ("Gender", "Male"), ("AgeGroup", "1to5"))),
        (12, (("period", "Q2_2025"), ("TvA", "achievement"), ("Gender", "Female"), ("AgeGroup", "U1"))),
        (11, (("period", "Q2_2025"), ("TvA", "achievement"), ("Gender", "Male"), ("AgeGroup", "U1"))),
        (15, (("period", "Q3_2025"), ("TvA", "target"), ("Gender", "Combine"), ("AgeGroup", "U5"))),
        (16, (("period", "Q3_2025"), ("TvA", "achievement"), ("Gender", "Male"), ("AgeGroup", "U1"))),
        (17, (("period", "Q3_2025"), ("TvA", "achievement"), ("Gender", "Female"), ("AgeGroup", "U1"))),
        (18, (("period", "Q3_2025"), ("TvA", "achievement"), ("Gender", "Male"), ("AgeGroup", "1to5"))),
        (19, (("period", "Q3_2025"), ("TvA", "achievement"), ("Gender", "Female"), ("AgeGroup", "1to5"))),
        (20, (("period", "Q4_2025"), ("TvA", "target"), ("Gender", "Combine"), ("AgeGroup", "U5"))),
        (21, (("period", "Q4_2025"), ("TvA", "achievement"), ("Gender", "Male"), ("AgeGroup", "U1"))),
        (22, (("period", "Q4_2025"), ("TvA", "achievement"), ("Gender", "Female"), ("AgeGroup", "U1"))),
        (24, (("period", "Q4_2025"), ("TvA", "achievement"), ("Gender", "Female"), ("AgeGroup", "1to5"))),
        (23, (("period", "Q4_2025"), ("TvA", "achievement"), ("Gender", "Male"), ("AgeGroup", "1to5"))),
    ]
    out = to_numeric_round(build_long(indicator, 4, specs, "value"), "value", 2)
    return apply_dynamic_period_from_year(out)


def build_cmu_indicator(cmu_indicator: pd.DataFrame) -> pd.DataFrame:
    specs: List[Spec] = [
        (5, (("period", "2025_Annual"), ("TvA", "target"), ("Gender", "Combine"), ("AgeGroup", "U5"))),
        (6, (("period", "2025_Annual"), ("TvA", "achievement"), ("Gender", "Male"), ("AgeGroup", "U1"))),
        (7, (("period", "2025_Annual"), ("TvA", "achievement"), ("Gender", "Female"), ("AgeGroup", "U1"))),
        (9, (("period", "2025_Annual"), ("TvA", "achievement"), ("Gender", "Female"), ("AgeGroup", "1to5"))),
        (8, (("period", "2025_Annual"), ("TvA", "achievement"), ("Gender", "Male"), ("AgeGroup", "1to5"))),
    ]
    out = to_numeric_round(build_long(cmu_indicator, 4, specs, "value"), "value", 2)
    return apply_dynamic_period_from_year(out)


def build_td2(td2_indicator: pd.DataFrame) -> pd.DataFrame:
    specs: List[Spec] = [
        (5, (("period", "Q1_2025"), ("TvA", "target"))),
        (6, (("period", "Q1_2025"), ("TvA", "achievement"))),
        (7, (("period", "Q2_2025"), ("TvA", "target"))),
        (8, (("period", "Q2_2025"), ("TvA", "achievement"))),
        (9, (("period", "Q3_2025"), ("TvA", "target"))),
        (10, (("period", "Q3_2025"), ("TvA", "achievement"))),
        (11, (("period", "Q4_2025"), ("TvA", "target"))),
        (12, (("period", "Q4_2025"), ("TvA", "achievement"))),
    ]
    out = to_numeric_round(build_long(td2_indicator, 4, specs, "value"), "value", 2)
    return apply_dynamic_period_from_year(out)


def build_td_alod(td_alod: pd.DataFrame) -> pd.DataFrame:
    specs: List[Spec] = [
        (5, (("period", "2025_Annual"), ("TvA", "target"))),
        (6, (("period", "2025_Annual"), ("TvA", "achievement"))),
    ]
    out = to_numeric_round(build_long(td_alod, 4, specs, "value"), "value", 2)
    return apply_dynamic_period_from_year(out)


def extract_spreadsheet_id(sheet_url: str) -> str | None:
    parsed = urlparse(sheet_url)
    parts = [part for part in parsed.path.split("/") if part]
    if "d" not in parts:
        return None
    idx = parts.index("d")
    if idx + 1 >= len(parts):
        return None
    return parts[idx + 1]


def try_sync_google_sheets(
    sheet_name: str,
    tables: Dict[str, pd.DataFrame],
    secrets_dir: Path,
    sheet_url: str | None = None,
) -> None:
    try:
        gspread = importlib.import_module("gspread")
        set_with_dataframe = importlib.import_module(
            "gspread_dataframe"
        ).set_with_dataframe
    except ImportError as exc:
        raise RuntimeError(
            "Google sync requires 'gspread' and 'gspread-dataframe'. "
            "Install with: pip install gspread gspread-dataframe google-auth-oauthlib"
        ) from exc

    scopes = [
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/spreadsheets",
    ]
    credentials_filename = secrets_dir / "credentials.json"
    authorized_user_filename = secrets_dir / "authorized_user.json"

    if not credentials_filename.exists():
        raise FileNotFoundError(
            f"Google OAuth credentials not found: {credentials_filename}. "
            "Place your downloaded OAuth client file as credentials.json in the .secrets folder."
        )
    if not authorized_user_filename.exists():
        print(
            "Google authorized_user.json not found. "
            "Starting first-time OAuth flow to create it..."
        )

    gc = gspread.oauth(
        scopes=scopes,
        credentials_filename=str(credentials_filename),
        authorized_user_filename=str(authorized_user_filename),
    )

    spreadsheet = None
    if sheet_url:
        spreadsheet_id = extract_spreadsheet_id(sheet_url)
        if spreadsheet_id:
            spreadsheet = gc.open_by_key(spreadsheet_id)
        else:
            spreadsheet = gc.open_by_url(sheet_url)
    else:
        try:
            spreadsheet = gc.open(sheet_name)
        except gspread.SpreadsheetNotFound:
            spreadsheet = gc.create(sheet_name)

    for ws_name, table in tables.items():
        try:
            worksheet = spreadsheet.worksheet(ws_name)
            worksheet.clear()
        except gspread.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(
                title=ws_name,
                rows=max(len(table) + 5, 100),
                cols=max(len(table.columns) + 5, 20),
            )

        set_with_dataframe(worksheet, table, include_index=False, include_column_header=True, resize=True)

    print(f"Google Sheet synced: {spreadsheet.url}")


def main() -> None:
    script_dir = Path(__file__).resolve().parent
    epi_thematic_dir = script_dir.parent

    parser = argparse.ArgumentParser(
        description="Transform EPI_overall.xlsx into EPI master sheets (R-to-Python conversion)."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=epi_thematic_dir / "EPI_overall.xlsx",
        help="Path to EPI_overall.xlsx",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=script_dir / "SE_EPI_master.xlsx",
        help="Path to output SE_EPI_master.xlsx",
    )
    sync_group = parser.add_mutually_exclusive_group()
    sync_group.add_argument(
        "--sync-google",
        dest="sync_google",
        action="store_true",
        default=True,
        help="Sync output tables to Google Sheets (default: enabled).",
    )
    sync_group.add_argument(
        "--no-sync-google",
        dest="sync_google",
        action="store_false",
        help="Skip Google Sheets sync and only create local Excel output.",
    )
    parser.add_argument(
        "--sheet-name",
        type=str,
        default="SE_EPI_master",
        help="Google Sheet name for --sync-google.",
    )
    parser.add_argument(
        "--sheet-url",
        type=str,
        default="",
        help="Google Sheet URL for --sync-google. If provided, this is used instead of --sheet-name.",
    )
    parser.add_argument(
        "--secrets-dir",
        type=Path,
        default=epi_thematic_dir / ".secrets",
        help="Directory containing Google OAuth credentials.",
    )
    args = parser.parse_args()

    input_file = args.input.resolve()
    output_file = args.output.resolve()

    if not input_file.exists():
        raise FileNotFoundError(f"Input workbook not found: {input_file}")

    vthc = pd.read_excel(input_file, sheet_name="VTHC_Doses disaggregate")
    cummulative = pd.read_excel(input_file, sheet_name="Cummulative")
    indicator = pd.read_excel(input_file, sheet_name="indicators")
    cmu_indicator = pd.read_excel(input_file, sheet_name="ALOD_cummu")
    td2_indicator = pd.read_excel(input_file, sheet_name="Td2_indicator")
    td_alod = pd.read_excel(input_file, sheet_name="Td_ALOD")

    tables: Dict[str, pd.DataFrame] = {
        "VTHCwise_doses": build_vthc(vthc),
        "cummulative_indicator_coverage": build_cummulative(cummulative),
        "indicator": build_indicator(indicator),
        "cummu_ALOD_child": build_cmu_indicator(cmu_indicator),
        "Td2": build_td2(td2_indicator),
        "TD_ALOD_cum": build_td_alod(td_alod),
    }

    output_file.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
        for sheet_name, table in tables.items():
            table.to_excel(writer, sheet_name=sheet_name, index=False)

    print(f"Created workbook: {output_file}")
    for name, table in tables.items():
        print(f"- {name}: {len(table):,} rows x {len(table.columns)} cols")

    if args.sync_google:
        try_sync_google_sheets(
            args.sheet_name,
            tables,
            args.secrets_dir.resolve(),
            sheet_url=args.sheet_url.strip() or None,
        )


if __name__ == "__main__":
    main()
