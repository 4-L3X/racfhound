#!/usr/bin/env python3
import paramiko
import argparse
import sys
import os
import time


def collect_datasets(client, delay, output_dir):
    """Two-step dataset enumeration: SEARCH to list profiles, then LD DA per profile."""

    # Step 1 – get all dataset profile names
    print("[datasets] Searching for dataset profiles...")
    _, stdout, stderr = client.exec_command('tsocmd "sr class(dataset) filter(**)"')
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
        # Two-column format: "DATASET  <name>" – take the second token
        if len(parts) == 2 and parts[0].upper() == "DATASET":
            profile_names.append(parts[1])
        # Single-column format: just the profile name on its own line
        elif len(parts) == 1 and parts[0].upper() not in ("DATASET", "CLASS", "NAME"):
            if not set(parts[0]).issubset(set("-=")):  # skip separator lines
                profile_names.append(parts[0])

    print(f"[datasets] Found {len(profile_names)} dataset profiles.")

    # Step 2 – enumerate each profile individually
    if delay > 0:
        print(f"[rate-limit] Sleeping {delay}s before ld da enumeration...")
        time.sleep(delay)

    combined_output = []
    for name in profile_names:
        _, stdout, stderr = client.exec_command(f"tsocmd \"ld da('{name}') all\"")
        out = stdout.read().decode('utf-8', errors='replace')
        err = stderr.read().decode('utf-8', errors='replace')
        if out:
            combined_output.append(out)
        if err:
            print(f"[datasets] STDERR for {name}: {err}", file=sys.stderr)

    output_path = os.path.join(output_dir, "rhoundoutput_DATASET.txt")
    with open(output_path, "w") as f:
        f.write("\n".join(combined_output))
    print(f"[datasets] Output saved to {output_path}")


def collect(host, username, password=None, key_path=None, port=22, delay=0.0):
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

        client.connect(**connect_kwargs)

        commands = [
            ('tsocmd "lg *"', "rhoundoutput_GROUP.txt"),
            ('tsocmd "lu *"', "rhoundoutput_USER.txt"),
            ('tsocmd "rlist surrogat * all"', "rhoundoutput_SURROGAT.txt"),
            ('tsocmd "rlist unixpriv * all"', "rhoundoutput_UNIXPRIV.txt"),
        ]

        os.makedirs("output", exist_ok=True)

        for i, (command, output_file) in enumerate(commands):
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
                print(f"[{command}] Output saved to {output_path}")
            if errors:
                print(f"[{command}] STDERR: {errors}", file=sys.stderr)

        if delay > 0:
            print(f"[rate-limit] Sleeping {delay}s before dataset enumeration...")
            time.sleep(delay)
        collect_datasets(client, delay, "output")

    finally:
        client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='SSH into the mainframe and run tsocmd to collect RACF data')
    parser.add_argument("host", help="Target hostname or IP")
    parser.add_argument("username", help="SSH username")
    parser.add_argument("--password", help="SSH password")
    parser.add_argument("--key", dest="key_path", help="Path to SSH private key")
    parser.add_argument("--port", type=int, default=22, help="SSH port (default: 22)")
    parser.add_argument("--delay", type=float, default=0.0, metavar="SECONDS",
                        help="Seconds to wait between commands (default: 0)")

    args = parser.parse_args()
    collect(args.host, args.username, args.password, args.key_path, args.port, args.delay)
