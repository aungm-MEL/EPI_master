from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
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


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EPI_THEMATIC = PROJECT_ROOT / "EPI_thematic_sheet"
SCRIPT_CREATE_OVERALL = EPI_THEMATIC / "create_epi_overall.py"
SCRIPT_CREATE_MASTER = EPI_THEMATIC / "EPI_master" / "create_epi_master_sheet.py"
OUTPUT_OVERALL = EPI_THEMATIC / "EPI_overall.xlsx"
OUTPUT_MASTER = EPI_THEMATIC / "EPI_master" / "SE_EPI_master.xlsx"
GOOGLE_CREDENTIALS = EPI_THEMATIC / ".secrets" / "credentials.json"
GOOGLE_AUTHORIZED = EPI_THEMATIC / ".secrets" / "authorized_user.json"


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
        st.success(f"{result.name} completed")
    else:
        st.error(f"{result.name} failed (exit code: {result.returncode})")

    with st.expander(f"{result.name} logs", expanded=result.returncode != 0):
        st.text("COMMAND:\n" + " ".join(result.command))
        st.text("STDOUT:\n" + (result.stdout.strip() or "(no stdout)"))
        st.text("STDERR:\n" + (result.stderr.strip() or "(no stderr)"))


def format_mtime(path: Path) -> str:
    if not path.exists():
        return "Not generated yet"
    ts = datetime.fromtimestamp(path.stat().st_mtime)
    return ts.strftime("%Y-%m-%d %H:%M:%S")


def requirements_check(sync_google: bool) -> bool:
    ok = True

    if not SCRIPT_CREATE_OVERALL.exists():
        st.error(f"Missing script: {SCRIPT_CREATE_OVERALL}")
        ok = False

    if not SCRIPT_CREATE_MASTER.exists():
        st.error(f"Missing script: {SCRIPT_CREATE_MASTER}")
        ok = False

    if sync_google and not GOOGLE_CREDENTIALS.exists():
        st.error(f"Google credentials.json missing: {GOOGLE_CREDENTIALS}")
        st.info("Add credentials.json in .secrets, then rerun.")
        ok = False

    return ok


def build_master_args(sync_google: bool, sheet_name: str) -> List[str]:
    args = [sys.executable, str(SCRIPT_CREATE_MASTER), "--sheet-name", sheet_name]
    if not sync_google:
        args.append("--no-sync-google")
    return args


def render_download(path: Path, label: str, mime: str) -> None:
    if not path.exists():
        return
    with path.open("rb") as f:
        st.download_button(
            label=label,
            data=f.read(),
            file_name=path.name,
            mime=mime,
        )


def main() -> None:
    st.set_page_config(page_title="EPI Pipeline Runner", layout="wide")
    st.title("EPI Overall to SE_EPI_master Runner")
    st.caption("Step 1 creates EPI_overall.xlsx. Step 2 creates SE_EPI_master.xlsx and optionally updates Google Sheet.")

    left, right = st.columns(2)
    with left:
        st.subheader("Step 1: EPI overall")
        st.write(str(SCRIPT_CREATE_OVERALL))
        st.write(f"Output: {OUTPUT_OVERALL}")
        st.write(f"Last updated: {format_mtime(OUTPUT_OVERALL)}")

    with right:
        st.subheader("Step 2: SE master")
        st.write(str(SCRIPT_CREATE_MASTER))
        st.write(f"Output: {OUTPUT_MASTER}")
        st.write(f"Last updated: {format_mtime(OUTPUT_MASTER)}")

    st.divider()

    st.subheader("Google Sync")
    sync_google = st.checkbox("Update Google Sheet after Step 2", value=True)
    sheet_name = st.text_input("Google Sheet Name", value="SE_EPI_master")

    if sync_google:
        if GOOGLE_CREDENTIALS.exists():
            st.success("credentials.json found")
        else:
            st.warning(f"credentials.json missing at {GOOGLE_CREDENTIALS}")

        if GOOGLE_AUTHORIZED.exists():
            st.success("authorized_user.json found")
        else:
            st.info("authorized_user.json will be created on first successful login")

    st.divider()

    run_pipeline = st.button("Run Full Pipeline (Step 1 then Step 2)", type="primary")
    run_step1 = st.button("Run Step 1 only")
    run_step2 = st.button("Run Step 2 only")

    if run_pipeline:
        if not requirements_check(sync_google=sync_google):
            st.stop()

        progress = st.progress(0, text="Starting pipeline...")

        progress.progress(20, text="Running Step 1: create_epi_overall.py")
        step1 = run_step("Step 1 - create_epi_overall", [sys.executable, str(SCRIPT_CREATE_OVERALL)])
        render_step_result(step1)
        if step1.returncode != 0:
            progress.empty()
            st.stop()

        progress.progress(70, text="Running Step 2: create_epi_master_sheet.py")
        step2 = run_step(
            "Step 2 - create_epi_master_sheet",
            build_master_args(sync_google=sync_google, sheet_name=sheet_name),
        )
        render_step_result(step2)
        if step2.returncode != 0:
            progress.empty()
            st.stop()

        progress.progress(100, text="Pipeline completed")
        st.success("Finished: EPI_overall and SE_EPI_master are updated.")

    if run_step1:
        if not requirements_check(sync_google=False):
            st.stop()
        result = run_step("Step 1 - create_epi_overall", [sys.executable, str(SCRIPT_CREATE_OVERALL)])
        render_step_result(result)

    if run_step2:
        if not requirements_check(sync_google=sync_google):
            st.stop()
        result = run_step(
            "Step 2 - create_epi_master_sheet",
            build_master_args(sync_google=sync_google, sheet_name=sheet_name),
        )
        render_step_result(result)

    st.divider()
    st.subheader("Download Latest Outputs")
    c1, c2 = st.columns(2)
    with c1:
        render_download(
            OUTPUT_OVERALL,
            "Download EPI_overall.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    with c2:
        render_download(
            OUTPUT_MASTER,
            "Download SE_EPI_master.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


if __name__ == "__main__":
    main()
