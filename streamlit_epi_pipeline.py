from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

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

INPUT_KDHW = PROJECT_ROOT / "KDHW" / "quarterly compile.update.xlsx"
INPUT_KNA = PROJECT_ROOT / "KNA" / "KNA_EPI_long.xlsx"
INPUT_CHDN = PROJECT_ROOT / "CHDN EPI" / "data" / "CHDN dataset_long.xlsx"

OUTPUT_OVERALL = EPI_THEMATIC / "EPI_overall.xlsx"
OUTPUT_MASTER = EPI_THEMATIC / "EPI_master" / "SE_EPI_master.xlsx"

GOOGLE_SECRETS_DIR = EPI_THEMATIC / ".secrets"
GOOGLE_CREDENTIALS = GOOGLE_SECRETS_DIR / "credentials.json"
GOOGLE_AUTHORIZED = GOOGLE_SECRETS_DIR / "authorized_user.json"


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


def save_uploaded_file(uploaded_file, target_path: Path) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_bytes(uploaded_file.getbuffer())


def format_mtime(path: Path) -> str:
    if not path.exists():
        return "Not found"
    ts = datetime.fromtimestamp(path.stat().st_mtime)
    return ts.strftime("%Y-%m-%d %H:%M:%S")


def status_row(label: str, path: Path) -> None:
    exists = path.exists()
    if exists:
        st.success(f"{label}: Found")
    else:
        st.warning(f"{label}: Missing")
    st.caption(str(path))
    st.caption(f"Last modified: {format_mtime(path)}")


def render_step_result(result: StepResult) -> None:
    if result.returncode == 0:
        st.success(f"{result.name} completed")
    else:
        st.error(f"{result.name} failed (exit code: {result.returncode})")

    with st.expander(f"{result.name} logs", expanded=result.returncode != 0):
        st.text("COMMAND:\n" + " ".join(result.command))
        st.text("STDOUT:\n" + (result.stdout.strip() or "(no stdout)"))
        st.text("STDERR:\n" + (result.stderr.strip() or "(no stderr)"))


def precheck(sync_google: bool) -> Tuple[bool, List[str]]:
    ok = True
    messages: List[str] = []

    if not SCRIPT_CREATE_OVERALL.exists():
        ok = False
        messages.append(f"Missing script: {SCRIPT_CREATE_OVERALL}")

    if not SCRIPT_CREATE_MASTER.exists():
        ok = False
        messages.append(f"Missing script: {SCRIPT_CREATE_MASTER}")

    for label, path in [
        ("KDHW input", INPUT_KDHW),
        ("KNA input", INPUT_KNA),
        ("CHDN input", INPUT_CHDN),
    ]:
        if not path.exists():
            ok = False
            messages.append(f"Missing {label}: {path}")

    if sync_google and not GOOGLE_CREDENTIALS.exists():
        ok = False
        messages.append(f"Missing Google credentials: {GOOGLE_CREDENTIALS}")

    return ok, messages


def main() -> None:
    st.set_page_config(page_title="EPI Overall -> SE_EPI_master", layout="wide")
    st.title("EPI Overall -> SE_EPI_master Pipeline (New App)")
    st.caption("This app does not modify your existing create_epi_overall.py or create_epi_master_sheet.py scripts.")

    st.subheader("1) Upload Source Files (Optional)")
    st.write("Upload only when you need to replace current source files.")

    col_up_1, col_up_2 = st.columns(2)
    with col_up_1:
        up_kdhw = st.file_uploader("KDHW file", type=["xlsx"], key="kdhw")
        if up_kdhw and st.button("Save KDHW file"):
            save_uploaded_file(up_kdhw, INPUT_KDHW)
            st.success(f"Saved: {INPUT_KDHW}")

        up_kna = st.file_uploader("KNA file", type=["xlsx"], key="kna")
        if up_kna and st.button("Save KNA file"):
            save_uploaded_file(up_kna, INPUT_KNA)
            st.success(f"Saved: {INPUT_KNA}")

    with col_up_2:
        up_chdn = st.file_uploader("CHDN file", type=["xlsx"], key="chdn")
        if up_chdn and st.button("Save CHDN file"):
            save_uploaded_file(up_chdn, INPUT_CHDN)
            st.success(f"Saved: {INPUT_CHDN}")

        up_creds = st.file_uploader("Google credentials.json (optional)", type=["json"], key="creds")
        if up_creds and st.button("Save Google credentials"):
            save_uploaded_file(up_creds, GOOGLE_CREDENTIALS)
            st.success(f"Saved: {GOOGLE_CREDENTIALS}")

    st.divider()
    st.subheader("2) Current File Status")
    s1, s2 = st.columns(2)
    with s1:
        status_row("create_epi_overall.py", SCRIPT_CREATE_OVERALL)
        status_row("KDHW input", INPUT_KDHW)
        status_row("KNA input", INPUT_KNA)
        status_row("CHDN input", INPUT_CHDN)

    with s2:
        status_row("create_epi_master_sheet.py", SCRIPT_CREATE_MASTER)
        status_row("EPI_overall.xlsx", OUTPUT_OVERALL)
        status_row("SE_EPI_master.xlsx", OUTPUT_MASTER)
        status_row("Google credentials.json", GOOGLE_CREDENTIALS)

    st.divider()
    st.subheader("3) Run Pipeline")

    sync_google = st.checkbox("Update Google Sheet (SE_EPI_master)", value=True)
    sheet_name = st.text_input("Google Sheet Name", value="SE_EPI_master")

    if GOOGLE_AUTHORIZED.exists():
        st.info("authorized_user.json found. Existing Google login token is available.")
    else:
        st.info("authorized_user.json not found. First Google sync may ask you to login.")

    if st.button("Run: create_epi_overall -> create_epi_master_sheet", type="primary"):
        ok, messages = precheck(sync_google=sync_google)
        if not ok:
            st.error("Precheck failed. Fix the following first:")
            for msg in messages:
                st.write(f"- {msg}")
            st.stop()

        progress = st.progress(0, text="Starting pipeline...")

        progress.progress(30, text="Step 1: create_epi_overall.py")
        step1 = run_step(
            "Step 1 - create_epi_overall",
            [sys.executable, str(SCRIPT_CREATE_OVERALL)],
        )
        render_step_result(step1)
        if step1.returncode != 0:
            progress.empty()
            st.stop()

        progress.progress(75, text="Step 2: create_epi_master_sheet.py")
        cmd2 = [
            sys.executable,
            str(SCRIPT_CREATE_MASTER),
            "--input",
            str(OUTPUT_OVERALL),
            "--sheet-name",
            sheet_name,
        ]
        if not sync_google:
            cmd2.append("--no-sync-google")

        step2 = run_step("Step 2 - create_epi_master_sheet", cmd2)
        render_step_result(step2)
        if step2.returncode != 0:
            progress.empty()
            st.stop()

        progress.progress(100, text="Done")
        st.success("Pipeline completed successfully.")
        st.write(f"Updated file: {OUTPUT_OVERALL}")
        st.write(f"Updated file: {OUTPUT_MASTER}")

    st.divider()
    st.subheader("4) Quick Downloads")
    d1, d2 = st.columns(2)
    with d1:
        if OUTPUT_OVERALL.exists():
            st.download_button(
                "Download EPI_overall.xlsx",
                data=OUTPUT_OVERALL.read_bytes(),
                file_name=OUTPUT_OVERALL.name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

    with d2:
        if OUTPUT_MASTER.exists():
            st.download_button(
                "Download SE_EPI_master.xlsx",
                data=OUTPUT_MASTER.read_bytes(),
                file_name=OUTPUT_MASTER.name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )


if __name__ == "__main__":
    main()
