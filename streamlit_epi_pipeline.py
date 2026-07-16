from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import streamlit as st


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

    candidate_roots: List[Path] = []
    for root in [Path.cwd(), app_file.parent, *app_file.parents]:
        if root not in candidate_roots:
            candidate_roots.append(root)

    for root in candidate_roots:
        candidate_thematics = [root / "EPI_thematic_sheet", root]
        for thematic_dir in candidate_thematics:
            script_overall = thematic_dir / "create_epi_overall.py"
            script_master = thematic_dir / "EPI_master" / "create_epi_master_sheet.py"
            if script_overall.exists() and script_master.exists():
                return {
                    "project_root": root,
                    "thematic_dir": thematic_dir,
                    "script_overall": script_overall,
                    "script_master": script_master,
                    "output_overall": thematic_dir / "EPI_overall.xlsx",
                    "output_master": thematic_dir / "EPI_master" / "SE_EPI_master.xlsx",
                    "credentials": thematic_dir / ".secrets" / "credentials.json",
                    "authorized": thematic_dir / ".secrets" / "authorized_user.json",
                }

    # Fallback for unexpected layouts; validation will report exact missing files.
    fallback_root = app_file.parents[2] if len(app_file.parents) > 2 else app_file.parent
    fallback_thematic = fallback_root / "EPI_thematic_sheet"
    return {
        "project_root": fallback_root,
        "thematic_dir": fallback_thematic,
        "script_overall": fallback_thematic / "create_epi_overall.py",
        "script_master": fallback_thematic / "EPI_master" / "create_epi_master_sheet.py",
        "output_overall": fallback_thematic / "EPI_overall.xlsx",
        "output_master": fallback_thematic / "EPI_master" / "SE_EPI_master.xlsx",
        "credentials": fallback_thematic / ".secrets" / "credentials.json",
        "authorized": fallback_thematic / ".secrets" / "authorized_user.json",
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


def build_master_command(sync_google: bool, sheet_name: str) -> List[str]:
    cmd = [sys.executable, str(PATHS["script_master"]), "--sheet-name", sheet_name]
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
    st.caption("Fresh workflow: configure once in sidebar, run exactly the step you need.")

    with st.sidebar:
        st.header("Run Settings")
        sync_google = st.toggle("Enable Google Sheet sync", value=True)
        sheet_name = st.text_input("Google Sheet name", value="SE_EPI_master").strip() or "SE_EPI_master"

        st.markdown("### Secrets Status")
        st.write(f"credentials.json: {'found' if PATHS['credentials'].exists() else 'missing'}")
        st.write(f"authorized_user.json: {'found' if PATHS['authorized'].exists() else 'missing'}")

        st.markdown("### Location")
        st.write(str(PATHS["project_root"]))
        st.write(str(PATHS["thematic_dir"]))

    issues = validate_prerequisites(sync_google=sync_google)
    if issues:
        st.error("Prerequisite check failed")
        for issue in issues:
            st.write(f"- {issue}")
        st.stop()

    st.subheader("Actions")
    a, b, c = st.columns(3)
    run_full = a.button("Run Full Pipeline", use_container_width=True, type="primary")
    run_overall = b.button("Run Step 1 Only", use_container_width=True)
    run_master = c.button("Run Step 2 Only", use_container_width=True)

    if run_full:
        progress = st.progress(0, text="Starting full pipeline")

        progress.progress(30, text="Running Step 1")
        step1 = run_command(
            "Step 1 - create_epi_overall",
            [sys.executable, str(PATHS["script_overall"])],
            cwd=PATHS["project_root"],
        )
        show_result(step1)
        if step1.return_code != 0:
            progress.empty()
            st.stop()

        progress.progress(75, text="Running Step 2")
        step2 = run_command(
            "Step 2 - create_epi_master_sheet",
            build_master_command(sync_google=sync_google, sheet_name=sheet_name),
            cwd=PATHS["project_root"],
        )
        show_result(step2)
        if step2.return_code != 0:
            progress.empty()
            st.stop()

        progress.progress(100, text="Completed")
        st.success("Pipeline finished successfully.")

    if run_overall:
        result = run_command(
            "Step 1 - create_epi_overall",
            [sys.executable, str(PATHS["script_overall"])],
            cwd=PATHS["project_root"],
        )
        show_result(result)

    if run_master:
        result = run_command(
            "Step 2 - create_epi_master_sheet",
            build_master_command(sync_google=sync_google, sheet_name=sheet_name),
            cwd=PATHS["project_root"],
        )
        show_result(result)

    st.divider()
    show_outputs()
    st.divider()
    show_history()


if __name__ == "__main__":
    main()
