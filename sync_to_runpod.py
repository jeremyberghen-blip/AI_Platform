"""
sync_to_runpod.py — Sync local ComfyUI files to a RunPod network volume via SFTP.

Usage:
    python sync_to_runpod.py --host <ssh_host> --port <ssh_port> [--key ~/.ssh/id_rsa]

Find your SSH host/port in the RunPod pod dashboard under "SSH".
Example connection string RunPod gives you:
    ssh root@ssh.runpod.io -p 12345 -i ~/.ssh/id_rsa
                ^host              ^port

What gets synced:
    workflows/      — all saved ComfyUI workflows (small, always synced)
    models/loras/   — LoRAs only (checkpoints too large; use models.txt instead)
    models/vae/     — VAEs (usually small)
    models/controlnet/ — ControlNet models

What is intentionally skipped:
    models/checkpoints/ — use models.txt; pod downloads direct from CivitAI much faster
    custom_nodes/       — baked into Docker image
    venv/               — baked into Docker image

Install dependencies:
    pip install paramiko tqdm
"""

import argparse
import os
import sys
from pathlib import Path

try:
    import paramiko
except ImportError:
    sys.exit("Missing dependency: pip install paramiko")

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False


# ── Config ────────────────────────────────────────────────────────────────────

LOCAL_COMFYUI = Path("C:/ComfyUI")
REMOTE_WORKSPACE = "/workspace/comfyui"

# (local_subpath, remote_subpath, sync_large_files)
SYNC_TARGETS = [
    ("user/default/workflows",  "workflows",            True),   # JSON, always sync
    ("models/loras",            "models/loras",         True),   # sync (custom LoRAs)
    ("models/vae",              "models/vae",           True),   # usually small
    ("models/controlnet",       "models/controlnet",    True),   # medium size
    ("models/upscale_models",   "models/upscale_models",True),
    # Checkpoints skipped — use models.txt for pod-side download
]

LARGE_FILE_THRESHOLD_MB = 500  # warn before uploading files over this size


# ── Helpers ───────────────────────────────────────────────────────────────────

def remote_exists(sftp, path: str) -> bool:
    try:
        sftp.stat(path)
        return True
    except FileNotFoundError:
        return False


def remote_mkdir_p(sftp, remote_path: str):
    parts = remote_path.split("/")
    current = ""
    for part in parts:
        if not part:
            current = "/"
            continue
        current = f"{current}/{part}" if current != "/" else f"/{part}"
        try:
            sftp.stat(current)
        except FileNotFoundError:
            sftp.mkdir(current)


def human_size(size_bytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def upload_file(sftp, local_path: Path, remote_path: str):
    size = local_path.stat().st_size

    if HAS_TQDM:
        pbar = tqdm(total=size, unit="B", unit_scale=True, desc=local_path.name, leave=False)
        def callback(transferred, total):
            pbar.update(transferred - pbar.n)
        sftp.put(str(local_path), remote_path, callback=callback)
        pbar.close()
    else:
        print(f"    Uploading {local_path.name} ({human_size(size)})...")
        sftp.put(str(local_path), remote_path)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Sync local ComfyUI files to RunPod network volume")
    parser.add_argument("--host", required=True, help="SSH host (e.g. ssh.runpod.io)")
    parser.add_argument("--port", required=True, type=int, help="SSH port from RunPod dashboard")
    parser.add_argument("--user", default="root", help="SSH user (default: root)")
    parser.add_argument("--key",  default=None,   help="Path to SSH private key (default: ~/.ssh/id_rsa)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be uploaded without uploading")
    args = parser.parse_args()

    key_path = args.key or os.path.expanduser("~/.ssh/id_rsa")
    if not os.path.exists(key_path):
        sys.exit(f"SSH key not found: {key_path}\nSpecify with --key or generate one with: ssh-keygen -t rsa")

    print(f"\nConnecting to {args.user}@{args.host}:{args.port}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(args.host, port=args.port, username=args.user, key_filename=key_path)
    except Exception as e:
        sys.exit(f"SSH connection failed: {e}")

    sftp = ssh.open_sftp()
    print("Connected.\n")

    total_uploaded = 0
    total_skipped  = 0
    total_missing  = 0  # local path doesn't exist

    for local_sub, remote_sub, _ in SYNC_TARGETS:
        local_dir  = LOCAL_COMFYUI / local_sub
        remote_dir = f"{REMOTE_WORKSPACE}/{remote_sub}"

        if not local_dir.exists():
            print(f"[SKIP] Local path not found: {local_dir}")
            total_missing += 1
            continue

        files = [f for f in local_dir.rglob("*") if f.is_file()]
        if not files:
            print(f"[EMPTY] {local_sub} — nothing to sync")
            continue

        print(f"\n── {local_sub} ({len(files)} files) ──────────────────")

        for local_file in sorted(files):
            rel = local_file.relative_to(local_dir)
            remote_file = f"{remote_dir}/{str(rel).replace(os.sep, '/')}"
            remote_parent = remote_file.rsplit("/", 1)[0]

            size_mb = local_file.stat().st_size / (1024 * 1024)

            if remote_exists(sftp, remote_file):
                print(f"  OK      {rel}  ({size_mb:.0f} MB)")
                total_skipped += 1
                continue

            if size_mb > LARGE_FILE_THRESHOLD_MB:
                print(f"  LARGE   {rel}  ({size_mb:.0f} MB)")
                print(f"          Consider adding this to models.txt for direct pod download instead.")
                answer = input("          Upload anyway? [y/N]: ").strip().lower()
                if answer != "y":
                    print("          Skipped.")
                    total_skipped += 1
                    continue

            if args.dry_run:
                print(f"  DRY-RUN {rel}  ({size_mb:.0f} MB) — would upload")
                continue

            remote_mkdir_p(sftp, remote_parent)
            upload_file(sftp, local_file, remote_file)
            print(f"  UPLOADED {rel}  ({size_mb:.0f} MB)")
            total_uploaded += 1

    sftp.close()
    ssh.close()

    print(f"\n{'─'*50}")
    print(f"Done.  Uploaded: {total_uploaded}  |  Already present: {total_skipped}  |  Local missing: {total_missing}")
    if args.dry_run:
        print("(Dry run — nothing was actually uploaded)")
    print()


if __name__ == "__main__":
    main()
