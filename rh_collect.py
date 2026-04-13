#!/usr/bin/env python3
import paramiko
import argparse
import sys
import os
import time

ALL_CLASSES = ["GROUP", "USER", "SURROGAT", "UNIXPRIV", "FACILITY", "DATASET", "TCICSTRN", "GCICSTRN"]

# Simple TSO commands for non-dataset classes
SIMPLE_COMMANDS = {
    "GROUP":    ('tsocmd "LISTGRP *"',              "racfhound_GROUP.txt"),
    "USER":     ('tsocmd "LISTUSER *"',             "racfhound_USER.txt"),
    "SURROGAT": ('tsocmd "RLIST SURROGAT * ALL"',   "racfhound_SURROGAT.txt"),
    "UNIXPRIV": ('tsocmd "RLIST UNIXPRIV * ALL"',   "racfhound_UNIXPRIV.txt"),
    "FACILITY": ('tsocmd "RLIST FACILITY * ALL"',   "racfhound_FACILITY.txt"),
    "TCICSTRN": ('tsocmd "RLIST TCICSTRN * ALL"',   "racfhound_TCICSTRN.txt"),
    "GCICSTRN": ('tsocmd "RLIST GCICSTRN * ALL"',   "racfhound_GCICSTRN.txt"),
}


def collect_datasets(client, delay, output_dir):
    
    # Step 1 – get all dataset profile names
    print("[datasets] Searching for DATASET profiles...")
    _, stdout, stderr = client.exec_command('tsocmd "SEARCH CLASS(DATASET) FILTER(**)"')
    search_out = stdout.read().decode('utf-8', errors='replace')
    search_err = stderr.read().decode('utf-8', errors='replace')
    if search_err:
        print(f"[datasets] STDERR: {search_err}", file=sys.stderr)

    # Parse names: skip blank lines and header/separator lines
    profile_names = []
    for line in search_out.splitlines():
        parts = line.split()
        if not parts:
            continue
        # Generic profile: "DATASET.** (G)" – name is first token, second is "(G)"
        if len(parts) == 2 and parts[1] == "(G)":
            profile_names.append(parts[0])
        # Discrete profile: just the name on its own line
        elif len(parts) == 1 and parts[0].upper() not in ("DATASET", "CLASS", "NAME"):
            if not set(parts[0]).issubset(set("-=")):  # skip separator lines
                profile_names.append(parts[0])

    print(f"[datasets] Found {len(profile_names)} DATASET profiles.")

    # Step 2 – enumerate each profile individually
    if delay > 0:
        print(f"[rate-limit] Sleeping {delay}s before profile enumeration...")
        time.sleep(delay)

    combined_output = []
    for name in profile_names:
        generic_kw = " GENERIC" if any(c in name for c in ('*', '%')) else ""
        _, stdout, stderr = client.exec_command(f"tsocmd \"LISTDSD DATASET('{name}') ALL{generic_kw}\"")
        out = stdout.read().decode('utf-8', errors='replace')
        err = stderr.read().decode('utf-8', errors='replace')
        if out:
            combined_output.append(out)
        if err:
            print(f"[datasets] STDERR for {name}: {err}", file=sys.stderr)

    output_path = os.path.join(output_dir, "racfhound_DATASET.txt")
    with open(output_path, "w") as f:
        f.write("\n".join(combined_output))
    print(f"[datasets] Output saved to {output_path}")


def collect(host, username, password=None, key_path=None, port=22, delay=0.0, classes=None):
    if classes is None:
        classes = ALL_CLASSES

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        connect_kwargs = {
            "hostname": host,
            "port": port,
            "username": username,
        }
        if key_path:
            connect_kwargs["key_filename"] = key_path
        elif password:
            connect_kwargs["password"] = password
        else:
            print("Error: provide either --password or --key", file=sys.stderr)
            sys.exit(1)

        client.connect(**connect_kwargs, timeout=5)

        os.makedirs("output", exist_ok=True)

        simple = [(cls, *SIMPLE_COMMANDS[cls]) for cls in classes if cls in SIMPLE_COMMANDS]
        for i, (cls, command, output_file) in enumerate(simple):
            if i > 0 and delay > 0:
                print(f"[rate-limit] Sleeping {delay}s before next command...")
                time.sleep(delay)

            stdin, stdout, stderr = client.exec_command(command)

            output = stdout.read().decode('utf-8', errors='replace')
            errors = stderr.read().decode('utf-8', errors='replace')

            if output:
                output_path = os.path.join("output", output_file)
                with open(output_path, "w") as f:
                    f.write(output)
                print(f"[{cls}] Output saved to {output_path}")
            if errors:
                print(f"[{cls}] STDERR: {errors}", file=sys.stderr)

        if "DATASET" in classes:
            if simple and delay > 0:
                print(f"[rate-limit] Sleeping {delay}s before dataset enumeration...")
                time.sleep(delay)
            collect_datasets(client, delay, "output")

    finally:
        client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=r"""
    ____             ______  __                      __
   / __ \____ ______/ __/ / / /___  __  ______  ____/ /
  / /_/ / __ `/ ___/ /_/ /_/ / __ \/ / / / __ \/ __  / 
 / _, _/ /_/ / /__/ __/ __  / /_/ / /_/ / / / / /_/ /  
/_/ |_|\__,_/\___/_/ /_/ /_/\____/\__,_/_/ /_/\__,_/   
                             Six Degrees of IBMUSER""",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("host", help="Target hostname or IP")
    parser.add_argument("username", help="SSH username")
    parser.add_argument("--password", help="SSH password")
    parser.add_argument("--key", dest="key_path", help="Path to SSH private key")
    parser.add_argument("--port", type=int, default=22, help="SSH port (default: 22)")
    parser.add_argument("--delay", type=float, default=0.0, metavar="SECONDS",
                        help="Seconds to wait between commands (default: 0.0)")

    class_group = parser.add_mutually_exclusive_group()
    class_group.add_argument(
        "--all", dest="all_classes", action="store_true",
        help="Enumerate all classes (default behaviour)",
    )
    class_group.add_argument(
        "--classes", nargs="+", metavar="CLASS",
        help=f"Classes to enumerate (choices: {', '.join(ALL_CLASSES)})",
    )

    args = parser.parse_args()

    if args.classes:
        selected = [c.upper() for c in args.classes]
        invalid = [c for c in selected if c not in ALL_CLASSES]
        if invalid:
            parser.error(f"Unknown class(es): {', '.join(invalid)}. Valid choices: {', '.join(ALL_CLASSES)}")
        classes = selected
    else:
        classes = ALL_CLASSES

    collect(args.host, args.username, args.password, args.key_path, args.port, args.delay, classes)
