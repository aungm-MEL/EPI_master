from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List

import streamlit as st


@dataclass
class StepResult:
    name: str
    command: List[str]
    returncode: int
    stdout: str
    stderr: str


def first_existing(*paths: Path) -> Path:
    for path in paths:
        if path.exists():
            return path
    return paths[0]


BASE_DIR = Path(__file__).resolve().parent
LEGACY_EPI_THEMATIC = BASE_DIR.parent / "EPI_thematic_sheet"

PROJECT_ROOT = first_existing(BASE_DIR, LEGACY_EPI_THEMATIC)
SCRIPT_CREATE_OVERALL = first_existing(
    BASE_DIR / "create_epi_overall.py",
    LEGACY_EPI_THEMATIC / "create_epi_overall.py",
)
SCRIPT_CREATE_MASTER = first_existing(
    BASE_DIR / "create_epi_master_sheet.py",
    LEGACY_EPI_THEMATIC / "EPI_master" / "create_epi_master_sheet.py",
)
OUTPUT_OVERALL = first_existing(
    BASE_DIR / "EPI_overall.xlsx",
    LEGACY_EPI_THEMATIC / "EPI_overall.xlsx",
)
OUTPUT_MASTER = first_existing(
    BASE_DIR / "SE_EPI_master.xlsx",
    LEGACY_EPI_THEMATIC / "EPI_master" / "SE_EPI_master.xlsx",
)
GOOGLE_CREDENTIALS = first_existing(
    BASE_DIR / ".secrets" / "credentials.json",
    LEGACY_EPI_THEMATIC / ".secrets" / "credentials.json",
)
GOOGLE_AUTHORIZED = first_existing(
    BASE_DIR / ".secrets" / "authorized_user.json",
    LEGACY_EPI_THEMATIC / ".secrets" / "authorized_user.json",
)


def run_step(name: str, command: List[str]) -> StepResult:
    proc = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
    )
    return StepResult(
        name=name,
        command=command,
        returncode=proc.returncode,
        stdout=proc.stdout or "",
        stderr=proc.stderr or "",
    )


def render_step_result(result: StepResult) -> None:
    if result.returncode == 0:
        st.success(f"{result.name} completed successfully")
    else:
        st.error(f"{result.name} failed with exit code {result.returncode}")

    with st.expander(f"{result.name} command", expanded=False):
        st.code(" ".join(result.command), language="bash")

    with st.expander(f"{result.name} output", expanded=result.returncode != 0):
        st.text("STDOUT:\n" + (result.stdout.strip() or "(no stdout)"))
        st.text("STDERR:\n" + (result.stderr.strip() or "(no stderr)"))


def requirements_check(sync_google: bool) -> bool:
    ok = True

    if not SCRIPT_CREATE_OVERALL.exists():
        st.error(f"Missing file: {SCRIPT_CREATE_OVERALL}")
        ok = False
    if not SCRIPT_CREATE_MASTER.exists():
        st.error(f"Missing file: {SCRIPT_CREATE_MASTER}")
        ok = False

    if sync_google and not GOOGLE_CREDENTIALS.exists():
        st.error(
            "Google credentials file is missing. Expected: "
            f"{GOOGLE_CREDENTIALS}"
        )
        st.info("Place OAuth credentials.json there, then run again.")
        ok = False

    return ok


def build_master_args(sync_google: bool, sheet_name: str) -> List[str]:
    args = [sys.executable, str(SCRIPT_CREATE_MASTER), "--sheet-name", sheet_name]
    if not sync_google:
        args.append("--no-sync-google")
    return args


def main() -> None:
    st.set_page_config(page_title="EPI Pipeline Runner", layout="wide")
    st.title("EPI Overall -> EPI Master Pipeline")
    st.caption("Runs create_epi_overall.py, then create_epi_master_sheet.py, and optionally syncs Google Sheets.")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.write("**Input Script**")
        st.write(str(SCRIPT_CREATE_OVERALL))
        st.write("**Output**")
        st.write(str(OUTPUT_OVERALL))

    with col2:
        st.write("**Master Script**")
        st.write(str(SCRIPT_CREATE_MASTER))
        st.write("**Output**")
        st.write(str(OUTPUT_MASTER))

    with col3:
        st.write("**Google Credentials**")
        st.write(str(GOOGLE_CREDENTIALS))
        if GOOGLE_CREDENTIALS.exists():
            st.success("credentials.json found")
        else:
            st.warning("credentials.json missing")

        if GOOGLE_AUTHORIZED.exists():
            st.success("authorized_user.json found")
        else:
            st.info("authorized_user.json will be created on first successful login")

    st.divider()

    sync_google = st.checkbox("Update Google Sheet after creating master file", value=True)
    sheet_name = st.text_input("Google Sheet Name", value="SE_EPI_master")

    run_all = st.button("Run Full Pipeline", type="primary")
    run_overall_only = st.button("Run Step 1 Only: create_epi_overall")
    run_master_only = st.button("Run Step 2 Only: create_epi_master_sheet")

    if run_all:
        if not requirements_check(sync_google=sync_google):
            st.stop()

        with st.spinner("Running Step 1: create_epi_overall.py"):
            step1 = run_step("Step 1 - create_epi_overall", [sys.executable, str(SCRIPT_CREATE_OVERALL)])
        render_step_result(step1)
        if step1.returncode != 0:
            st.stop()

        with st.spinner("Running Step 2: create_epi_master_sheet.py"):
            step2 = run_step(
                "Step 2 - create_epi_master_sheet",
                build_master_args(sync_google=sync_google, sheet_name=sheet_name),
            )
        render_step_result(step2)
        if step2.returncode != 0:
            st.stop()

        st.success("Pipeline finished successfully.")
        if OUTPUT_MASTER.exists():
            st.write(f"Updated local master file: {OUTPUT_MASTER}")

    if run_overall_only:
        if not requirements_check(sync_google=False):
            st.stop()
        with st.spinner("Running create_epi_overall.py"):
            result = run_step("Step 1 - create_epi_overall", [sys.executable, str(SCRIPT_CREATE_OVERALL)])
        render_step_result(result)

    if run_master_only:
        if not requirements_check(sync_google=sync_google):
            st.stop()
        with st.spinner("Running create_epi_master_sheet.py"):
            result = run_step(
                "Step 2 - create_epi_master_sheet",
                build_master_args(sync_google=sync_google, sheet_name=sheet_name),
            )
        render_step_result(result)


if __name__ == "__main__":
    main()
