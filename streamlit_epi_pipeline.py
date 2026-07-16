from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import streamlit as st


DEFAULT_SHEET_URL = "https://docs.google.com/spreadsheets/d/1Ez20yBOCnyI2tIbve6jDT18EMzk8oN4MDDsUtithVBQ/edit?gid=33698989#gid=33698989"


@dataclass
class CommandResult:
    step: str
    command: List[str]
    return_code: int
    stdout: str
    stderr: str
    started_at: datetime
    ended_at: datetime

    @property
    def duration_seconds(self) -> float:
        return (self.ended_at - self.started_at).total_seconds()


def resolve_paths() -> Dict[str, Path]:
    app_file = Path(__file__).resolve()
    app_dir = app_file.parent
    thematic_dir = app_dir.parent
    project_root = thematic_dir.parent

    candidate_roots: List[Path] = []
    for root in [Path.cwd(), app_dir, thematic_dir, project_root, *app_file.parents]:
        if root not in candidate_roots:
            candidate_roots.append(root)

    def first_existing_path(candidates: List[Path]) -> Path:
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return candidates[0]

    overall_candidates: List[Path] = []
    master_candidates: List[Path] = []
    for root in candidate_roots:
        overall_candidates.extend(
            [
                root / "streamlit_app_files" / "create_epi_overall.py",
                root / "create_epi_overall.py",
                root / "EPI_thematic_sheet" / "create_epi_overall.py",
                root / "epi_master" / "streamlit_app_files" / "create_epi_overall.py",
            ]
        )
        master_candidates.extend(
            [
                root / "streamlit_app_files" / "create_epi_master_sheet.py",
                root / "create_epi_master_sheet.py",
                root / "EPI_master" / "create_epi_master_sheet.py",
                root / "EPI_thematic_sheet" / "EPI_master" / "create_epi_master_sheet.py",
                root / "epi_master" / "streamlit_app_files" / "create_epi_master_sheet.py",
            ]
        )

    script_overall = first_existing_path(overall_candidates)
    script_master = first_existing_path(master_candidates)
    script_base_dir = script_master.parent if script_master.exists() else app_dir

    secrets_candidates: List[Path] = []
    for root in candidate_roots:
        secrets_candidates.extend(
            [
                root / ".secrets",
                root / "EPI_thematic_sheet" / ".secrets",
                root / "epi_master" / ".secrets",
            ]
        )
    secrets_dir = first_existing_path(secrets_candidates)

    outputs_dir = app_dir / "streamlit_app_files" / "outputs"
    uploads_dir = app_dir / "streamlit_app_files" / "uploads"

    outputs_dir.mkdir(parents=True, exist_ok=True)
    uploads_dir.mkdir(parents=True, exist_ok=True)

    return {
        "project_root": project_root,
        "thematic_dir": thematic_dir,
        "script_overall": script_overall,
        "script_master": script_master,
        "output_overall": outputs_dir / "EPI_overall.xlsx",
        "output_master": outputs_dir / "SE_EPI_master.xlsx",
        "uploads_dir": uploads_dir,
        "secrets_dir": secrets_dir,
        "credentials": secrets_dir / "credentials.json",
        "authorized": secrets_dir / "authorized_user.json",
        "script_base_dir": script_base_dir,
    }


PATHS = resolve_paths()


def ensure_state() -> None:
    if "history" not in st.session_state:
        st.session_state.history = []


def run_command(step: str, command: List[str], cwd: Path) -> CommandResult:
    started = datetime.now()
    proc = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
    )
    ended = datetime.now()
    result = CommandResult(
        step=step,
        command=command,
        return_code=proc.returncode,
        stdout=(proc.stdout or "").strip(),
        stderr=(proc.stderr or "").strip(),
        started_at=started,
        ended_at=ended,
    )
    st.session_state.history.append(result)
    return result


def file_stamp(path: Path) -> str:
    if not path.exists():
        return "Not found"
    return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")


def validate_prerequisites(sync_google: bool) -> List[str]:
    issues: List[str] = []
    if not PATHS["script_overall"].exists():
        issues.append(f"Missing script: {PATHS['script_overall']}")
    if not PATHS["script_master"].exists():
        issues.append(f"Missing script: {PATHS['script_master']}")
    if sync_google and not PATHS["credentials"].exists():
        issues.append(f"Missing credentials.json: {PATHS['credentials']}")
    return issues


def save_uploaded_file(uploaded_file, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(uploaded_file.getbuffer())
    return destination


def build_overall_command(kdhw_path: Path, kna_path: Path, chdn_path: Path) -> List[str]:
    return [
        sys.executable,
        str(PATHS["script_overall"]),
        "--kdhw",
        str(kdhw_path),
        "--kna",
        str(kna_path),
        "--chdn",
        str(chdn_path),
        "--output",
        str(PATHS["output_overall"]),
    ]


def build_master_command(sync_google: bool, sheet_name: str, sheet_url: str) -> List[str]:
    cmd = [
        sys.executable,
        str(PATHS["script_master"]),
        "--sheet-name",
        sheet_name,
        "--input",
        str(PATHS["output_overall"]),
        "--output",
        str(PATHS["output_master"]),
        "--secrets-dir",
        str(PATHS["secrets_dir"]),
        "--sheet-url",
        sheet_url,
    ]
    if not sync_google:
        cmd.append("--no-sync-google")
    return cmd


def show_result(result: CommandResult) -> None:
    header = f"{result.step} ({result.duration_seconds:.1f}s)"
    if result.return_code == 0:
        st.success(f"{header} succeeded")
    else:
        st.error(f"{header} failed with exit code {result.return_code}")

    with st.expander(f"Logs: {result.step}", expanded=result.return_code != 0):
        st.code(" ".join(result.command), language="bash")
        st.text_area(
            label=f"STDOUT - {result.step}",
            value=result.stdout or "(no stdout)",
            height=180,
            disabled=True,
        )
        st.text_area(
            label=f"STDERR - {result.step}",
            value=result.stderr or "(no stderr)",
            height=180,
            disabled=True,
        )
        if "drive.googleapis.com" in result.stderr.lower() or "api has not been used" in result.stderr.lower():
            st.warning(
                "Google Drive API appears disabled for the OAuth project. "
                "Enable Drive API in Google Cloud Console, wait a few minutes, and rerun."
            )


def show_outputs() -> None:
    st.subheader("Outputs")
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"EPI_overall.xlsx updated: {file_stamp(PATHS['output_overall'])}")
        if PATHS["output_overall"].exists():
            with PATHS["output_overall"].open("rb") as handle:
                st.download_button(
                    "Download EPI_overall.xlsx",
                    data=handle.read(),
                    file_name=PATHS["output_overall"].name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
    with col2:
        st.write(f"SE_EPI_master.xlsx updated: {file_stamp(PATHS['output_master'])}")
        if PATHS["output_master"].exists():
            with PATHS["output_master"].open("rb") as handle:
                st.download_button(
                    "Download SE_EPI_master.xlsx",
                    data=handle.read(),
                    file_name=PATHS["output_master"].name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )


def show_history() -> None:
    st.subheader("Run History")
    if not st.session_state.history:
        st.info("No runs in this session yet.")
        return

    for item in reversed(st.session_state.history[-12:]):
        icon = "OK" if item.return_code == 0 else "FAIL"
        st.write(
            f"{icon} | {item.started_at.strftime('%H:%M:%S')} | {item.step} | "
            f"exit {item.return_code} | {item.duration_seconds:.1f}s"
        )


def main() -> None:
    st.set_page_config(page_title="EPI Pipeline Control Center", layout="wide")
    ensure_state()

    st.title("EPI Pipeline Control Center")
    st.caption("Upload files, run pipeline, and auto-sync to Google Sheet.")

    with st.sidebar:
        st.header("Run Settings")
        sync_google_default = PATHS["credentials"].exists()
        sync_google = st.toggle("Enable Google Sheet sync", value=sync_google_default)
        sheet_name = st.text_input("Google Sheet name", value="SE_EPI_master").strip() or "SE_EPI_master"
        sheet_url = st.text_input("Google Sheet URL", value=DEFAULT_SHEET_URL).strip() or DEFAULT_SHEET_URL

        st.markdown("### Secrets Status")
        st.write(f"credentials.json: {'found' if PATHS['credentials'].exists() else 'missing'}")
        st.write(f"authorized_user.json: {'found' if PATHS['authorized'].exists() else 'missing'}")

        st.markdown("### Output Location")
        st.write(str(PATHS["project_root"]))
        st.write(str(PATHS["output_overall"]))
        st.write(str(PATHS["output_master"]))
        st.write(str(PATHS["secrets_dir"]))
        st.markdown("### Scripts")
        st.write(str(PATHS["script_overall"]))
        st.write(str(PATHS["script_master"]))

    issues = validate_prerequisites(sync_google=sync_google)
    if issues:
        st.error("Prerequisite check failed")
        for issue in issues:
            st.write(f"- {issue}")
        st.stop()

    st.subheader("Upload Source Files")
    upload_col1, upload_col2, upload_col3 = st.columns(3)
    with upload_col1:
        uploaded_kdhw = st.file_uploader(
            "KDHW workbook",
            type=["xlsx", "xlsm", "xls"],
            key="upload_kdhw_streamlit",
            help="Required for Step 1",
        )
    with upload_col2:
        uploaded_kna = st.file_uploader(
            "KNA workbook",
            type=["xlsx", "xlsm", "xls"],
            key="upload_kna_streamlit",
            help="Required for Step 1",
        )
    with upload_col3:
        uploaded_chdn = st.file_uploader(
            "CHDN workbook",
            type=["xlsx", "xlsm", "xls"],
            key="upload_chdn_streamlit",
            help="Required for Step 1",
        )

    st.subheader("Actions")
    a, b, c = st.columns(3)
    run_full = a.button("Run Full Pipeline", use_container_width=True, type="primary")
    run_overall = b.button("Run Step 1 Only", use_container_width=True)
    run_master = c.button("Run Step 2 Only", use_container_width=True)

    missing_uploads = []
    if uploaded_kdhw is None:
        missing_uploads.append("KDHW")
    if uploaded_kna is None:
        missing_uploads.append("KNA")
    if uploaded_chdn is None:
        missing_uploads.append("CHDN")

    if run_full:
        if missing_uploads:
            st.error(f"Please upload all required files before running Step 1: {', '.join(missing_uploads)}")
            st.stop()

        kdhw_path = save_uploaded_file(uploaded_kdhw, PATHS["uploads_dir"] / "quarterly compile.update.xlsx")
        kna_path = save_uploaded_file(uploaded_kna, PATHS["uploads_dir"] / "KNA_EPI_long.xlsx")
        chdn_path = save_uploaded_file(uploaded_chdn, PATHS["uploads_dir"] / "CHDN dataset_long.xlsx")

        progress = st.progress(0, text="Starting full pipeline")

        progress.progress(30, text="Running Step 1")
        step1 = run_command(
            "Step 1 - create_epi_overall",
            build_overall_command(kdhw_path=kdhw_path, kna_path=kna_path, chdn_path=chdn_path),
            cwd=PATHS["project_root"],
        )
        show_result(step1)
        if step1.return_code != 0:
            progress.empty()
            st.stop()

        progress.progress(75, text="Running Step 2")
        step2 = run_command(
            "Step 2 - create_epi_master_sheet",
            build_master_command(sync_google=sync_google, sheet_name=sheet_name, sheet_url=sheet_url),
            cwd=PATHS["project_root"],
        )
        show_result(step2)
        if step2.return_code != 0:
            progress.empty()
            st.stop()

        progress.progress(100, text="Completed")
        st.success("Pipeline finished successfully.")

    if run_overall:
        if missing_uploads:
            st.error(f"Please upload all required files before running Step 1: {', '.join(missing_uploads)}")
            st.stop()

        kdhw_path = save_uploaded_file(uploaded_kdhw, PATHS["uploads_dir"] / "quarterly compile.update.xlsx")
        kna_path = save_uploaded_file(uploaded_kna, PATHS["uploads_dir"] / "KNA_EPI_long.xlsx")
        chdn_path = save_uploaded_file(uploaded_chdn, PATHS["uploads_dir"] / "CHDN dataset_long.xlsx")

        result = run_command(
            "Step 1 - create_epi_overall",
            build_overall_command(kdhw_path=kdhw_path, kna_path=kna_path, chdn_path=chdn_path),
            cwd=PATHS["project_root"],
        )
        show_result(result)

    if run_master:
        result = run_command(
            "Step 2 - create_epi_master_sheet",
            build_master_command(sync_google=sync_google, sheet_name=sheet_name, sheet_url=sheet_url),
            cwd=PATHS["project_root"],
        )
        show_result(result)

    st.divider()
    show_outputs()
    st.divider()
    show_history()


if __name__ == "__main__":
    main()
