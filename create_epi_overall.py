"""Create EPI_overall.xlsx by combining KDHW, KNA, and CHDN data."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent


def resolve_data_paths() -> dict[str, Path]:
    candidate_roots: list[Path] = []
    for root in [Path.cwd(), BASE_DIR, BASE_DIR.parent, *BASE_DIR.parents]:
        if root not in candidate_roots:
            candidate_roots.append(root)

    relative_paths = {
        "kdhw": Path("KDHW") / "quarterly compile.update.xlsx",
        "kna": Path("KNA") / "KNA_EPI_long.xlsx",
        "chdn": Path("CHDN EPI") / "data" / "CHDN dataset_long.xlsx",
    }

    for root in candidate_roots:
        kdhw = root / relative_paths["kdhw"]
        kna = root / relative_paths["kna"]
        chdn = root / relative_paths["chdn"]
        if kdhw.exists() and kna.exists() and chdn.exists():
            output_base = BASE_DIR if (BASE_DIR / "EPI_master").exists() else root
            return {
                "root": root,
                "output": output_base / "EPI_overall.xlsx",
                "kdhw": kdhw,
                "kna": kna,
                "chdn": chdn,
            }

    # Fallback to the most likely project root so error messages are informative.
    fallback_root = BASE_DIR.parent if (BASE_DIR / "EPI_master").exists() else BASE_DIR
    return {
        "root": fallback_root,
        "output": (BASE_DIR if (BASE_DIR / "EPI_master").exists() else fallback_root) / "EPI_overall.xlsx",
        "kdhw": fallback_root / relative_paths["kdhw"],
        "kna": fallback_root / relative_paths["kna"],
        "chdn": fallback_root / relative_paths["chdn"],
    }


VTHC_COLUMNS = [
    "Year",
    "period",
    "Organization",
    "Project Name",
    "District (EHO)",
    "Township_EHO",
    "Twp_MIMU",
    "Clinic Name",
    "ALOD_U1",
    "ALOD_U5",
    "ALOD_>5",
    "BCG_U1",
    "BCG_U5",
    "BCG_>5",
    "OPV1_U1",
    "OPV1_U5",
    "OPV1_>5",
    "OPV2_U1",
    "OPV2_U5",
    "OPV2_>5",
    "OPV3_U1",
    "OPV3_U5",
    "OPV3_>5",
    "Penta1_U1",
    "Penta1_U5",
    "Penta1_>5",
    "Penta2_U1",
    "Penta2_U5",
    "Penta2_>5",
    "Penta3_U1",
    "Penta3_U5",
    "Penta3_>5",
    "MMR1_U1",
    "MMR1_U5",
    "MMR1_>5",
    "MMR2_U1",
    "MMR2_U5",
    "MMR2_>5",
    "JE_U1",
    "JE_U5",
    "JE_>5",
    "IPV_U1",
    "IPV_U5",
    "IPV_>5",
    "CD_U1",
    "CD_U5",
    "CD_>5",
    "Td1",
    "Td2",
    "Td At least one dose",
]

CUMULATIVE_COLUMNS = [
    "Year",
    "Organization",
    "Project Name",
    "District (EHO)",
    "Township_EHO",
    "Twp_MIMU",
    "Clinic Name",
    "ALOD_U1",
    "ALOD_U5",
    "ALOD_>5",
    "Td At least one dose",
    "U5 population",
    "Unnamed: 12",
    "Unnamed: 13",
    "Unnamed: 14",
]

ALOD_CUMMU_COLUMNS = [
    "Year",
    "Organization",
    "Project Name",
    "Indicator",
    "Annual Target",
    "Annual U1 Male",
    "Annaul U1 Female",
    "Annual 1-5 Male",
    "Annual 1-5 Female",
    "indicator",
]

INDICATOR_COLUMNS = [
    "Year",
    "Organization",
    "Project Name",
    "indicator",
    "Q1 Target",
    "Q1 U1 Male",
    "Q1 U1 Female",
    "Q1 1-5 Male",
    "Q1 1-5 Female",
    "Q1 Total",
    "Q2 Target",
    "Q2 U1 Male",
    "Q2 U1 Female",
    "Q2 1-5 Male",
    "Q2 1-5 Female",
    "Q2 Total",
    "Q3 Target",
    "Q3 U1 Male",
    "Q3 U1 Female",
    "Q3 1-5 Male",
    "Q3 1-5 Female",
    "Q3 Total",
    "Q4 Target",
    "Q4 U1 Male",
    "Q4 U1 Female",
    "Q4 1-5 Male",
    "Q4 1-5 Female",
    "Q4 Total",
    "Period",
]

TD2_COLUMNS = [
    "Year",
    "Organization",
    "Project Name",
    "Indicators",
    "Q1 Target",
    "Q1 Achievement",
    "Q2 Target",
    "Q2 Achievement",
    "Q3 Target",
    "Q3 Achievement",
    "Q4 Target",
    "Q4 Achievement",
]

TD_ALOD_COLUMNS = [
    "Year",
    "Organization",
    "Project Name",
    "Indicators",
    "Annual Target",
    "Annual Achievement",
]


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename_map = {}
    for column in df.columns:
        if not isinstance(column, str):
            continue
        stripped = column.strip()
        if stripped == column:
            continue
        rename_map[column] = stripped

    df = df.rename(columns=rename_map)

    explicit_aliases = {
        "ALOD-U1": "ALOD_U1",
        "ALOD-U5": "ALOD_U5",
        "ALOD->5": "ALOD_>5",
        "Organization ": "Organization",
        "Indicators ": "Indicators",
        "Indicator ": "Indicator",
    }
    return df.rename(columns=explicit_aliases)


def resolve_sheet_name(workbook: pd.ExcelFile, expected: str) -> str:
    target = "".join(ch for ch in expected.lower() if ch.isalnum())
    for sheet_name in workbook.sheet_names:
        normalized = "".join(ch for ch in sheet_name.lower() if ch.isalnum())
        if normalized == target:
            return sheet_name
    raise KeyError(f"Could not find sheet {expected!r} in {workbook.io}")


def read_sheet(workbook_path: Path, sheet_name: str) -> pd.DataFrame:
    workbook = pd.ExcelFile(workbook_path)
    resolved_name = resolve_sheet_name(workbook, sheet_name)
    return pd.read_excel(workbook_path, sheet_name=resolved_name, engine="openpyxl")


def standardize_frame(df: pd.DataFrame, columns: Iterable[str]) -> pd.DataFrame:
    df = normalize_columns(df)
    return df.reindex(columns=list(columns))


def build_vthc_frame(source_path: Path, sheet_name: str) -> pd.DataFrame:
    return standardize_frame(read_sheet(source_path, sheet_name), VTHC_COLUMNS)


def build_cumulative_frame(source_path: Path, sheet_name: str) -> pd.DataFrame:
    df = normalize_columns(read_sheet(source_path, sheet_name))
    if "period" in df.columns:
        df = df.rename(columns={"period": "Year"})
    return df.reindex(columns=CUMULATIVE_COLUMNS)


def build_alod_cummu_frame(source_path: Path, sheet_name: str, source_is_kd_hw: bool) -> pd.DataFrame:
    df = normalize_columns(read_sheet(source_path, sheet_name))
    if "Period" in df.columns:
        df = df.rename(columns={"Period": "Year"})
    if "indicator" in df.columns and source_is_kd_hw:
        df["Indicator"] = ""
    if "indicator" in df.columns and not source_is_kd_hw:
        df = df.rename(columns={"indicator": "Indicator"})
        df["indicator"] = ""
    if "Indicator" not in df.columns:
        df["Indicator"] = ""
    if "indicator" not in df.columns:
        df["indicator"] = ""
    return df.reindex(columns=ALOD_CUMMU_COLUMNS)


def build_indicators_frame(source_path: Path, sheet_name: str) -> pd.DataFrame:
    df = normalize_columns(read_sheet(source_path, sheet_name))
    return df.reindex(columns=INDICATOR_COLUMNS)


def build_td2_frame(source_path: Path, sheet_name: str) -> pd.DataFrame:
    df = normalize_columns(read_sheet(source_path, sheet_name))
    if "Period" in df.columns:
        df = df.rename(columns={"Period": "Year"})
    return df.reindex(columns=TD2_COLUMNS)


def build_td_alod_frame(source_path: Path, sheet_name: str) -> pd.DataFrame:
    df = normalize_columns(read_sheet(source_path, sheet_name))
    if "Period" in df.columns:
        df = df.rename(columns={"Period": "Year"})
    return df.reindex(columns=TD_ALOD_COLUMNS)


def concat_frames(frames: list[pd.DataFrame], columns: Iterable[str]) -> pd.DataFrame:
    combined = pd.concat(frames, ignore_index=True)
    combined = combined.reindex(columns=list(columns))
    return combined.dropna(how="all")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create EPI_overall.xlsx from KDHW, KNA, and CHDN workbooks.")
    parser.add_argument("--kdhw", type=Path, help="Path to KDHW source workbook")
    parser.add_argument("--kna", type=Path, help="Path to KNA source workbook")
    parser.add_argument("--chdn", type=Path, help="Path to CHDN source workbook")
    parser.add_argument("--output", type=Path, help="Path to output EPI_overall.xlsx")
    args = parser.parse_args()

    paths = resolve_data_paths()
    if args.kdhw:
        paths["kdhw"] = args.kdhw.resolve()
    if args.kna:
        paths["kna"] = args.kna.resolve()
    if args.chdn:
        paths["chdn"] = args.chdn.resolve()
    if args.output:
        paths["output"] = args.output.resolve()

    output_file = paths["output"]
    kdhw_file = paths["kdhw"]
    kna_file = paths["kna"]
    chdn_file = paths["chdn"]

    missing: list[Path] = []
    for source in [kdhw_file, kna_file, chdn_file]:
        if not source.exists():
            missing.append(source)

    if missing:
        missing_lines = "\n".join(f"- {item}" for item in missing)
        raise FileNotFoundError(
            "Missing source workbook(s):\n"
            f"{missing_lines}\n"
            "Upload the KDHW, KNA, and CHDN source folders/workbooks to the deployed repository."
        )

    sheet_map = {
        "VTHC_Doses disaggregate": concat_frames(
            [
                build_vthc_frame(kdhw_file, "VTHC_Doses disaggregate"),
                build_vthc_frame(kna_file, "Summary"),
                build_vthc_frame(chdn_file, "Summary"),
            ],
            VTHC_COLUMNS,
        ),
        "Cummulative": concat_frames(
            [
                build_cumulative_frame(kdhw_file, "Cummulative_sheet"),
                build_cumulative_frame(kna_file, "yearly_cumulative"),
                build_cumulative_frame(chdn_file, "yearly_cumulative"),
            ],
            CUMULATIVE_COLUMNS,
        ),
        "ALOD_cummu": concat_frames(
            [
                build_alod_cummu_frame(kdhw_file, "Cummu_indicator", source_is_kd_hw=True),
                build_alod_cummu_frame(kna_file, "ALOD_cummu", source_is_kd_hw=False),
                build_alod_cummu_frame(chdn_file, "ALOD_cummu", source_is_kd_hw=False),
            ],
            ALOD_CUMMU_COLUMNS,
        ),
        "indicators": concat_frames(
            [
                build_indicators_frame(kdhw_file, "Indicator"),
                build_indicators_frame(kna_file, "indicators"),
                build_indicators_frame(chdn_file, "indicators"),
            ],
            INDICATOR_COLUMNS,
        ),
        "Td2_indicator": concat_frames(
            [
                build_td2_frame(kdhw_file, "TD2_indicator"),
                build_td2_frame(kna_file, "Td2_indicator"),
                build_td2_frame(chdn_file, "Td2_indicator"),
            ],
            TD2_COLUMNS,
        ),
        "Td_ALOD": concat_frames(
            [
                build_td_alod_frame(kdhw_file, "Td_ALOD"),
                build_td_alod_frame(kna_file, "Td_alod"),
                build_td_alod_frame(chdn_file, "Td_ALOD"),
            ],
            TD_ALOD_COLUMNS,
        ),
    }

    output_file.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
        for sheet_name, df in sheet_map.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)

    print(f"Wrote {output_file}")


if __name__ == "__main__":
    main()