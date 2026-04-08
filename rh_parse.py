#!/usr/bin/env python3
"""
Parse RACF enumeration output files into BloodHound OpenGraph JSON.

Sources
-------
  racfhound_GROUP.txt     – LISTGRP  (tsocmd "LISTGRP *")
  racfhound_USER.txt      – LISTUSER (tsocmd "LISTUSER *")
  racfhound_SURROGAT.txt  – RLIST SURROGAT  (tsocmd "RLIST SURROGAT * ALL")
  racfhound_UNIXPRIV.txt  – RLIST UNIXPRIV  (tsocmd "RLIST UNIXPRIV * ALL")
  racfhound_FACILITY.txt  – RLIST FACILITY  (tsocmd "RLIST FACILITY * ALL")
  racfhound_DATASET.txt   – LISTDSD  (tsocmd "LISTDSD DATASET('DATA.SET') ALL GENERIC")
  racfhound_TCICSTRN.txt  – RLIST TCICSTRN  (tsocmd "RLIST TCICSTRN * ALL")
  racfhound_GCICSTRN.txt  – RLIST GCICSTRN  (tsocmd "RLIST GCICSTRN * ALL")

Nodes
-----
  RACF_Group       – RACF group
  RACF_User        – RACF user
  RACF_Resource    – SURROGAT, UNIXPRIV, FACILITY or CICS profiles
  RACF_Dataset     – RACF dataset profile

Edges
-----
  RACF_MemberOf         – User/SubGroup -> Group
  RACF_HasPermission    – User -> Resource (SURROGAT, UNIXPRIV, or FACILITY profile)
  RACF_HasDatasetAccess – User -> Dataset
  RACF_TargetsUser      – Resource (SURROGAT/UNIXPRIV) -> User (derived from profile name prefix)
"""
import re
import os
from bhopengraph import OpenGraph, Node, Edge, Properties

DIR = os.path.dirname(__file__)

OUTPUT_DIR    = os.path.join(DIR, "output")
GROUP_FILE    = os.path.join(OUTPUT_DIR, "rhoundoutput_GROUP.txt")
USER_FILE     = os.path.join(OUTPUT_DIR, "rhoundoutput_USER.txt")
SURROGAT_FILE  = os.path.join(OUTPUT_DIR, "rhoundoutput_SURROGAT.txt")
UNIXPRIV_FILE  = os.path.join(OUTPUT_DIR, "rhoundoutput_UNIXPRIV.txt")
FACILITY_FILE  = os.path.join(OUTPUT_DIR, "rhoundoutput_FACILITY.txt")
DATASET_FILE   = os.path.join(OUTPUT_DIR, "rhoundoutput_DATASET.txt")
TCICSTRN_FILE  = os.path.join(OUTPUT_DIR, "rhoundoutput_TCICSTRN.txt")
GCICSTRN_FILE  = os.path.join(OUTPUT_DIR, "rhoundoutput_GCICSTRN.txt")
OUTPUT_FILE   = os.path.join(OUTPUT_DIR, "racfhound.json")


# ── Parsers ────────────────────────────────────────────────────────────────────

def parse_groups(text):
    """
    Returns list of dicts:
        { name, superior, owner, created, subgroups[], users[] }
    where users[i] = { name, access, uacc }
    """
    groups = []
    current = None
    in_subgroups = False
    in_users = False
    current_user = None

    for raw_line in text.splitlines():
        line = raw_line.rstrip()

        m = re.match(r'^INFORMATION FOR GROUP\s+(\S+)', line)
        if m:
            if current:
                if current_user:
                    current["users"].append(current_user)
                    current_user = None
                groups.append(current)
            current = {"name": m.group(1), "superior": None, "owner": None,
                       "created": None, "subgroups": [], "users": []}
            in_subgroups = False
            in_users = False
            continue

        if current is None:
            continue

        m = re.match(r'\s+SUPERIOR GROUP=(\S+)\s+OWNER=(\S+)\s+CREATED=(\S+)', line)
        if m:
            current["superior"] = m.group(1)
            current["owner"]    = m.group(2)
            current["created"]  = m.group(3)
            in_subgroups = False
            in_users = False
            continue

        if re.match(r'\s+NO SUBGROUPS', line):
            in_subgroups = False
            continue

        m = re.match(r'\s+SUBGROUP\(S\)=\s*(.*)', line)
        if m:
            in_subgroups = True
            in_users = False
            current["subgroups"].extend(m.group(1).split())
            continue

        if in_subgroups and re.match(r'\s{17,}', line) and line.strip():
            stripped = line.strip()
            if not re.match(r'(USER\(S\)|NO |TERMUACC|INSTALLATION|MODEL)', stripped):
                current["subgroups"].extend(stripped.split())
                continue
            else:
                in_subgroups = False

        if re.match(r'\s+NO USERS', line):
            in_users = False
            continue

        if re.match(r'\s+USER\(S\)=', line):
            in_subgroups = False
            in_users = True
            continue

        if not in_users:
            continue

        m = re.match(
            r'\s{2,6}(\S+)\s+(USE|READ|UPDATE|CONTROL|ALTER|NONE)\s+(\S+)\s+(\S+)',
            line
        )
        if m:
            if current_user:
                current["users"].append(current_user)
            current_user = {"name": m.group(1), "access": m.group(2), "uacc": m.group(4)}
            continue

    if current:
        if current_user:
            current["users"].append(current_user)
        groups.append(current)

    return groups


def parse_users(text):
    """
    Returns list of dicts:
        { name, fullname, owner, created, default_group, attributes,
          last_access, revoked, pass_interval, group_connections[] }
    where group_connections[i] = { group, auth, uacc, connects, last_connect }
    """
    users = []
    current = None
    in_group_section = False

    for raw_line in text.splitlines():
        line = raw_line.rstrip()

        # New user record
        m = re.match(
            r'^USER=(\S+)\s+NAME=(.*?)\s{2,}OWNER=(\S+)\s+CREATED=(\S+)',
            line
        )
        if m:
            if current:
                users.append(current)
            current = {
                "name":              m.group(1),
                "fullname":          m.group(2).strip(),
                "owner":             m.group(3),
                "created":           m.group(4),
                "default_group":     None,
                "attributes":        None,
                "last_access":       None,
                "revoked":           False,
                "pass_interval":     None,
                "group_connections": [],
            }
            in_group_section = False
            continue

        if current is None:
            continue

        # DEFAULT-GROUP and password info
        m = re.match(
            r'\s+DEFAULT-GROUP=(\S*)\s+PASSDATE=\S+\s+PASS-INTERVAL=(\S+)',
            line
        )
        if m:
            dg = m.group(1).strip()
            current["default_group"] = dg if dg else None
            pi = m.group(2)
            current["pass_interval"] = None if pi == "N/A" else pi
            continue

        # ATTRIBUTES
        m = re.match(r'\s+ATTRIBUTES=(.+)', line)
        if m:
            attrs = m.group(1).strip()
            current["attributes"] = attrs
            if "REVOKED" in attrs:
                current["revoked"] = True
            continue

        # LAST-ACCESS
        m = re.match(r'\s+LAST-ACCESS=(\S+)', line)
        if m:
            la = m.group(1)
            current["last_access"] = None if la == "UNKNOWN" else la
            continue

        # Group connection header
        m = re.match(
            r'\s+GROUP=(\S+)\s+AUTH=(\S+)\s+CONNECT-OWNER=\S+\s+CONNECT-DATE=\S+',
            line
        )
        if m:
            in_group_section = True
            current["group_connections"].append({
                "group":        m.group(1),
                "auth":         m.group(2),
                "uacc":         None,
                "connects":     None,
                "last_connect": None,
            })
            continue

        # CONNECTS / UACC / LAST-CONNECT line
        if in_group_section and current["group_connections"]:
            m = re.match(
                r'\s+CONNECTS=\s*(\S+)\s+UACC=(\S+)\s+LAST-CONNECT=(\S+)',
                line
            )
            if m:
                gc = current["group_connections"][-1]
                gc["connects"]     = m.group(1)
                gc["uacc"]         = m.group(2)
                gc["last_connect"] = m.group(3)
                continue

    if current:
        users.append(current)

    return users


def parse_rlist(text, class_name):
    """
    Parse RLIST output for SURROGAT, UNIXPRIV, FACILITY, or TCICSTRN.
    Returns list of dicts:
        { profile, owner, uacc, warning, auditing, installation_data, acl[] }
    where acl[i] = { user, access }
    """
    profiles = []
    current = None
    in_acl = False
    awaiting_value = None  # 'auditing' or 'installation_data'

    for raw_line in text.splitlines():
        line = raw_line.rstrip()

        # New profile record
        m = re.match(rf'^{class_name}\s+(\S+)', line)
        if m:
            if current:
                profiles.append(current)
            current = {
                "profile": m.group(1), "owner": None, "uacc": None,
                "warning": None, "auditing": None, "installation_data": None,
                "acl": [],
            }
            in_acl = False
            awaiting_value = None
            continue

        if current is None:
            continue

        # Owner + UACC + WARNING line
        m = re.match(
            r'\s*(\d+)\s+(\S+)\s+(NONE|READ|UPDATE|CONTROL|ALTER)\s+'
            r'(NONE|READ|UPDATE|CONTROL|ALTER)\s+(YES|NO)',
            line
        )
        if m:
            current["owner"]   = m.group(2)
            current["uacc"]    = m.group(3)
            current["warning"] = m.group(5) == "YES"
            in_acl = False
            awaiting_value = None
            continue

        # Section headers we track
        if re.match(r'^INSTALLATION DATA', line):
            awaiting_value = "installation_data"
            in_acl = False
            continue
        if re.match(r'^AUDITING\s*$', line.strip()):
            awaiting_value = "auditing"
            in_acl = False
            continue

        # Separator line after a section header
        if awaiting_value and re.match(r'^-+\s*$', line.strip()):
            continue

        # Value line: first non-blank, non-separator content after a tracked header
        if awaiting_value and line.strip() and not re.match(r'^-+\s*$', line.strip()):
            current[awaiting_value] = line.strip()
            awaiting_value = None
            continue

        # ACL section header
        if re.match(r'^USER\s+ACCESS\s+ACCESS COUNT', line):
            in_acl = True
            awaiting_value = None
            continue

        # ACL entries
        if in_acl:
            m = re.match(r'^(\S+)\s+(NONE|READ|UPDATE|CONTROL|ALTER)\s+(\d+)', line)
            if m:
                current["acl"].append({"user": m.group(1), "access": m.group(2)})
                continue
            # Blank line or other section ends the ACL
            if not line.strip() or re.match(r'^\s+ID\s+ACCESS', line):
                in_acl = False

    if current:
        profiles.append(current)

    return profiles


def parse_gcicstrn(text):
    """
    Parse RLIST output for the GCICSTRN (CICS resource group) class.
    Returns list of dicts:
        { profile, member_class, members[], owner, uacc, warning,
          auditing, installation_data, acl[] }
    where members[] are the TCICSTRN profile names listed under
    'RESOURCES IN GROUP', and acl[i] = { user, access }.
    """
    profiles = []
    current = None
    in_members = False
    in_acl = False
    awaiting_value = None  # 'auditing' or 'installation_data'

    for raw_line in text.splitlines():
        line = raw_line.rstrip()

        # New profile record: "GCICSTRN   <name>"
        m = re.match(r'^GCICSTRN\s+(\S+)', line)
        if m:
            if current:
                profiles.append(current)
            current = {
                "profile":           m.group(1),
                "member_class":      None,
                "members":           [],
                "owner":             None,
                "uacc":              None,
                "warning":           None,
                "auditing":          None,
                "installation_data": None,
                "acl":               [],
            }
            in_members = False
            in_acl = False
            awaiting_value = None
            continue

        if current is None:
            continue

        # Member class line: "MEMBER CLASS NAME" header followed by the class name
        if re.match(r'^MEMBER CLASS NAME', line):
            in_members = False
            in_acl = False
            awaiting_value = None
            continue

        # Capture the member class (e.g. "TCICSTRN") — appears right after the header
        if current["member_class"] is None and re.match(r'^(TCICSTRN)\s*$', line.strip()):
            current["member_class"] = line.strip()
            continue

        # Resources-in-group section header
        if re.match(r'^RESOURCES IN GROUP', line):
            in_members = True
            in_acl = False
            awaiting_value = None
            continue

        # Collect member transaction names (one per line, not a separator/header)
        if in_members:
            stripped = line.strip()
            if not stripped or re.match(r'^[-=\s]+$', line):
                continue
            # Any known section header ends the members block
            if re.match(r'^(LEVEL|INSTALLATION DATA|APPLICATION DATA|SECLEVEL|CATEGORIES|'
                        r'SECLABEL|AUDITING|GLOBALAUDIT|NOTIFY|CREATION DATE|ALTER COUNT|'
                        r'USER\s+ACCESS)', stripped):
                in_members = False
            else:
                current["members"].append(stripped)
                continue

        # Section headers we track for values
        if re.match(r'^INSTALLATION DATA', line):
            awaiting_value = "installation_data"
            in_acl = False
            continue
        if re.match(r'^AUDITING\s*$', line.strip()):
            awaiting_value = "auditing"
            in_acl = False
            continue

        # Separator line after a section header
        if awaiting_value and re.match(r'^-+\s*$', line.strip()):
            continue

        # Value line: first non-blank, non-separator content after a tracked header
        if awaiting_value and line.strip() and not re.match(r'^-+\s*$', line.strip()):
            current[awaiting_value] = line.strip()
            awaiting_value = None
            continue

        # Owner + UACC + WARNING line: " 00    OWNER    NONE    NONE    NO"
        m = re.match(
            r'^\s*\d+\s+(\S+)\s+(NONE|READ|UPDATE|CONTROL|ALTER)\s+'
            r'(NONE|READ|UPDATE|CONTROL|ALTER)\s+(YES|NO)',
            line
        )
        if m:
            current["owner"]   = m.group(1)
            current["uacc"]    = m.group(2)
            current["warning"] = m.group(4) == "YES"
            in_acl = False
            awaiting_value = None
            continue

        # ACL section header
        if re.match(r'^USER\s+ACCESS\s+ACCESS COUNT', line):
            in_acl = True
            awaiting_value = None
            continue

        # ACL entries
        if in_acl:
            m = re.match(r'^(\S+)\s+(NONE|READ|UPDATE|CONTROL|ALTER)\s+(\d+)', line)
            if m:
                current["acl"].append({"user": m.group(1), "access": m.group(2)})
                continue
            if not line.strip() or re.match(r'^\s+ID\s+ACCESS', line):
                in_acl = False

    if current:
        profiles.append(current)

    return profiles


# ── Graph builder ──────────────────────────────────────────────────────────────

def _ensure_user(graph, uid):
    if uid not in graph.nodes:
        p = Properties()
        p.set_property("name",     uid)
        p.set_property("objectid", uid)
        graph.add_node_without_validation(Node(id=uid, kinds=["RACF_User", "Base"], properties=p))


def _ensure_group(graph, gid):
    if gid not in graph.nodes:
        p = Properties()
        p.set_property("name",     gid)
        p.set_property("objectid", gid)
        graph.add_node_without_validation(Node(id=gid, kinds=["RACF_Group", "Base"], properties=p))


def parse_datasets(text):
    """
    Parse LISTDSD (ld da) output.
    Returns list of dicts:
        { profile, owner, uacc, warning, auditing, installation_data, acl[] }
    where acl[i] = { user, access }
    """
    profiles = []
    current = None
    in_acl = False
    awaiting_value = None  # 'auditing' or 'installation_data'

    for raw_line in text.splitlines():
        line = raw_line.rstrip()

        # New profile record: "INFORMATION FOR DATASET <name>"
        m = re.match(r'^INFORMATION FOR DATASET\s+(\S+)', line)
        if m:
            if current:
                profiles.append(current)
            current = {
                "profile": m.group(1), "owner": None, "uacc": None,
                "warning": None, "auditing": None, "installation_data": None,
                "acl": [],
            }
            in_acl = False
            awaiting_value = None
            continue

        if current is None:
            continue

        # Level / owner / uacc / warning line: " 00    IBMUSER    NONE    NO    NO"
        # Columns: LEVEL  OWNER  UNIVERSAL ACCESS  WARNING  ERASE
        m = re.match(
            r'^\s*\d+\s+(\S+)\s+(NONE|READ|UPDATE|CONTROL|ALTER)\s+(YES|NO)',
            line
        )
        if m:
            current["owner"]   = m.group(1)
            current["uacc"]    = m.group(2)
            current["warning"] = m.group(3) == "YES"
            in_acl = False
            awaiting_value = None
            continue

        # Section headers we track for values
        if re.match(r'^INSTALLATION DATA', line):
            awaiting_value = "installation_data"
            in_acl = False
            continue
        if re.match(r'^AUDITING\s*$', line.strip()):
            awaiting_value = "auditing"
            in_acl = False
            continue

        # Separator line after a section header
        if awaiting_value and re.match(r'^-+\s*$', line.strip()):
            continue

        # Value line: first non-blank, non-separator content after a tracked header
        if awaiting_value and line.strip() and not re.match(r'^-+\s*$', line.strip()):
            current[awaiting_value] = line.strip()
            awaiting_value = None
            continue

        # Standard ACL header — "   ID     ACCESS   ACCESS COUNT"
        # Exclude conditional access list header which appends "CLASS  ENTITY NAME"
        if re.match(r'^\s*ID\s+ACCESS\s+ACCESS COUNT\s*$', line):
            in_acl = True
            awaiting_value = None
            continue

        if in_acl:
            if re.match(r'^[-\s]+$', line):  # separator line
                continue
            m = re.match(r'^(\S+)\s+(NONE|READ|UPDATE|CONTROL|ALTER)\s+\d+', line)
            if m:
                current["acl"].append({"user": m.group(1), "access": m.group(2)})
            elif not line.strip():
                in_acl = False

    if current:
        profiles.append(current)

    return profiles


def build_graph(groups, users, surrogat_profiles, unixpriv_profiles, facility_profiles, dataset_profiles, tcicstrn_profiles, gcicstrn_profiles):
    graph = OpenGraph(source_kind="RACF")

    # ── Group nodes ────────────────────────────────────────────────────────────
    for g in groups:
        p = Properties()
        p.set_property("name",     g["name"])
        p.set_property("objectid", g["name"])
        if g["owner"]:
            p.set_property("owner", g["owner"])
        if g["created"]:
            p.set_property("created", g["created"])
        if g["superior"]:
            p.set_property("superior_group", g["superior"])
        graph.add_node_without_validation(Node(id=g["name"], kinds=["RACF_Group", "Base"], properties=p))

    # Superior groups that have no own record
    for g in groups:
        if g["superior"]:
            _ensure_group(graph, g["superior"])

    # ── User nodes (enriched from USER file) ───────────────────────────────────
    for u in users:
        p = Properties()
        p.set_property("name",     u["name"])
        p.set_property("objectid", u["name"])
        if u["fullname"]:
            p.set_property("displayname", u["fullname"])
        if u["owner"]:
            p.set_property("owner", u["owner"])
        if u["created"]:
            p.set_property("created", u["created"])
        if u["default_group"]:
            p.set_property("default_group", u["default_group"])
        if u["attributes"]:
            p.set_property("attributes", u["attributes"])
        if u["last_access"]:
            p.set_property("last_access", u["last_access"])
        p.set_property("revoked", u["revoked"])
        if u["pass_interval"]:
            p.set_property("pass_interval", u["pass_interval"])

        node = Node(id=u["name"], kinds=["RACF_User", "Base"], properties=p)
        # Overwrite stub nodes created from the group file
        graph.nodes[u["name"]] = node

    # ── User->Group edges from GROUP file ──────────────────────────────────────
    for g in groups:
        for u in g["users"]:
            _ensure_user(graph, u["name"])
            ep = Properties()
            ep.set_property("access", u["access"])
            ep.set_property("uacc",   u["uacc"])
            graph.add_edge_without_validation(
                Edge(start_node=u["name"], end_node=g["name"], kind="RACF_MemberOf", properties=ep)
            )

    # ── SubGroup->ParentGroup edges ────────────────────────────────────────────
    for g in groups:
        for sg in g["subgroups"]:
            _ensure_group(graph, sg)
            graph.add_edge_without_validation(
                Edge(start_node=sg, end_node=g["name"], kind="RACF_SubGroupOf")
            )

    # ── SURROGAT profiles: Resource nodes + HasPermission edges ───────────────
    for sp in surrogat_profiles:
        pid = f"SURROGAT:{sp['profile']}"
        p = Properties()
        p.set_property("name",        sp["profile"])
        p.set_property("objectid",    pid)
        p.set_property("class",       "SURROGAT")
        if sp["owner"]:
            p.set_property("owner",   sp["owner"])
        if sp["uacc"]:
            p.set_property("uacc",    sp["uacc"])
        if sp["warning"] is not None:
            p.set_property("warning", sp["warning"])
        if sp["auditing"]:
            p.set_property("auditing", sp["auditing"])
        if sp["installation_data"]:
            p.set_property("installation_data", sp["installation_data"])
        graph.add_node_without_validation(
            Node(id=pid, kinds=["RACF_Resource", "Base"], properties=p)
        )
        for entry in sp["acl"]:
            _ensure_user(graph, entry["user"])
            ep = Properties()
            ep.set_property("access", entry["access"])
            graph.add_edge_without_validation(
                Edge(start_node=entry["user"], end_node=pid, kind="RACF_HasPermission", properties=ep)
            )
        # Edge to the user the profile targets (e.g. MF101SK.SUBMIT -> MF101SK)
        target_uid = sp["profile"].split(".")[0]
        _ensure_user(graph, target_uid)
        graph.add_edge_without_validation(
            Edge(start_node=pid, end_node=target_uid, kind="RACF_TargetsUser")
        )

    # ── UNIXPRIV profiles: Resource nodes + HasPermission edges ───────────────
    for up in unixpriv_profiles:
        pid = f"UNIXPRIV:{up['profile']}"
        p = Properties()
        p.set_property("name",     up["profile"])
        p.set_property("objectid", pid)
        p.set_property("class",    "UNIXPRIV")
        if up["owner"]:
            p.set_property("owner", up["owner"])
        if up["uacc"]:
            p.set_property("uacc",  up["uacc"])
        if up["warning"] is not None:
            p.set_property("warning", up["warning"])
        if up["auditing"]:
            p.set_property("auditing", up["auditing"])
        if up["installation_data"]:
            p.set_property("installation_data", up["installation_data"])
        graph.add_node_without_validation(
            Node(id=pid, kinds=["RACF_Resource", "Base"], properties=p)
        )
        for entry in up["acl"]:
            _ensure_user(graph, entry["user"])
            ep = Properties()
            ep.set_property("access", entry["access"])
            graph.add_edge_without_validation(
                Edge(start_node=entry["user"], end_node=pid, kind="RACF_HasPermission", properties=ep)
            )
        # Edge to the user the profile targets (e.g. MF101SK.SUBMIT -> MF101SK)
        target_uid = up["profile"].split(".")[0]
        _ensure_user(graph, target_uid)
        graph.add_edge_without_validation(
            Edge(start_node=pid, end_node=target_uid, kind="RACF_TargetsUser")
        )

    # ── FACILITY profiles: Resource nodes + HasPermission edges ───────────────
    for fp in facility_profiles:
        pid = f"FACILITY:{fp['profile']}"
        p = Properties()
        p.set_property("name",     fp["profile"])
        p.set_property("objectid", pid)
        p.set_property("class",    "FACILITY")
        if fp["owner"]:
            p.set_property("owner", fp["owner"])
        if fp["uacc"]:
            p.set_property("uacc",  fp["uacc"])
        if fp["warning"] is not None:
            p.set_property("warning", fp["warning"])
        if fp["auditing"]:
            p.set_property("auditing", fp["auditing"])
        if fp["installation_data"]:
            p.set_property("installation_data", fp["installation_data"])
        graph.add_node_without_validation(
            Node(id=pid, kinds=["RACF_Resource", "Base"], properties=p)
        )
        for entry in fp["acl"]:
            _ensure_user(graph, entry["user"])
            ep = Properties()
            ep.set_property("access", entry["access"])
            graph.add_edge_without_validation(
                Edge(start_node=entry["user"], end_node=pid, kind="RACF_HasPermission", properties=ep)
            )

    # ── TCICSTRN profiles: Resource nodes + HasPermission edges ──────────────
    for tp in tcicstrn_profiles:
        pid = f"TCICSTRN:{tp['profile']}"
        p = Properties()
        p.set_property("name",     tp["profile"])
        p.set_property("objectid", pid)
        p.set_property("class",    "TCICSTRN")
        if tp["owner"]:
            p.set_property("owner", tp["owner"])
        if tp["uacc"]:
            p.set_property("uacc",  tp["uacc"])
        if tp["warning"] is not None:
            p.set_property("warning", tp["warning"])
        if tp["auditing"]:
            p.set_property("auditing", tp["auditing"])
        if tp["installation_data"]:
            p.set_property("installation_data", tp["installation_data"])
        graph.add_node_without_validation(
            Node(id=pid, kinds=["RACF_Resource", "Base"], properties=p)
        )
        for entry in tp["acl"]:
            _ensure_user(graph, entry["user"])
            ep = Properties()
            ep.set_property("access", entry["access"])
            graph.add_edge_without_validation(
                Edge(start_node=entry["user"], end_node=pid, kind="RACF_HasPermission", properties=ep)
            )

    # ── GCICSTRN profiles: Resource nodes + HasPermission + ContainsMember edges
    for gp in gcicstrn_profiles:
        pid = f"GCICSTRN:{gp['profile']}"
        p = Properties()
        p.set_property("name",     gp["profile"])
        p.set_property("objectid", pid)
        p.set_property("class",    "GCICSTRN")
        if gp["owner"]:
            p.set_property("owner", gp["owner"])
        if gp["uacc"]:
            p.set_property("uacc",  gp["uacc"])
        if gp.get("member_class"):
            p.set_property("member_class", gp["member_class"])
        if gp["warning"] is not None:
            p.set_property("warning", gp["warning"])
        if gp["auditing"]:
            p.set_property("auditing", gp["auditing"])
        if gp["installation_data"]:
            p.set_property("installation_data", gp["installation_data"])
        graph.add_node_without_validation(
            Node(id=pid, kinds=["RACF_Resource", "Base"], properties=p)
        )
        for entry in gp["acl"]:
            _ensure_user(graph, entry["user"])
            ep = Properties()
            ep.set_property("access", entry["access"])
            graph.add_edge_without_validation(
                Edge(start_node=entry["user"], end_node=pid, kind="RACF_HasPermission", properties=ep)
            )
        # Link the group to each member TCICSTRN profile it contains
        member_class = gp.get("member_class") or "TCICSTRN"
        for member_name in gp.get("members", []):
            member_pid = f"{member_class}:{member_name}"
            graph.add_edge_without_validation(
                Edge(start_node=pid, end_node=member_pid, kind="RACF_ContainsMember")
            )

    # ── Dataset profiles: Dataset nodes + HasDatasetAccess edges ──────────────
    for dp in dataset_profiles:
        did = f"DATASET:{dp['profile']}"
        p = Properties()
        p.set_property("name",     dp["profile"])
        p.set_property("objectid", did)
        p.set_property("class",    "DATASET")
        if dp["owner"]:
            p.set_property("owner", dp["owner"])
        if dp["uacc"]:
            p.set_property("uacc",  dp["uacc"])
        if dp["warning"] is not None:
            p.set_property("warning", dp["warning"])
        if dp["auditing"]:
            p.set_property("auditing", dp["auditing"])
        if dp["installation_data"]:
            p.set_property("installation_data", dp["installation_data"])
        graph.add_node_without_validation(
            Node(id=did, kinds=["RACF_Dataset", "Base"], properties=p)
        )
        for entry in dp["acl"]:
            _ensure_user(graph, entry["user"])
            ep = Properties()
            ep.set_property("access", entry["access"])
            graph.add_edge_without_validation(
                Edge(start_node=entry["user"], end_node=did, kind="RACF_HasDatasetAccess", properties=ep)
            )
        # Owner implicitly has ALTER access to their dataset profile
        if dp["owner"] and dp["owner"] not in {e["user"] for e in dp["acl"]}:
            _ensure_user(graph, dp["owner"])
            ep = Properties()
            ep.set_property("access", "ALTER")
            ep.set_property("source", "OWNER")
            graph.add_edge_without_validation(
                Edge(start_node=dp["owner"], end_node=did, kind="RACF_HasDatasetAccess", properties=ep)
            )

    # ── UACC edges: universal access applies to every user ────────────────────
    # Do this after all user nodes exist so we don't miss late-added stubs.
    all_user_ids = [nid for nid, node in graph.nodes.items() if "RACF_User" in node.kinds]

    for profiles, class_name, edge_kind in [
        (surrogat_profiles,  "SURROGAT",  "HasPermission"),
        (unixpriv_profiles,  "UNIXPRIV",  "HasPermission"),
        (facility_profiles,  "FACILITY",  "HasPermission"),
        (tcicstrn_profiles,  "TCICSTRN",  "HasPermission"),
        (gcicstrn_profiles,  "GCICSTRN",  "HasPermission"),
        (dataset_profiles,   "DATASET",   "HasDatasetAccess"),
    ]:
        for profile in profiles:
            if not profile["uacc"] or profile["uacc"] == "NONE":
                continue
            pid = f"{class_name}:{profile['profile']}"
            explicit = {entry["user"] for entry in profile["acl"]}
            for uid in all_user_ids:
                if uid in explicit:
                    continue
                ep = Properties()
                ep.set_property("access", profile["uacc"])
                ep.set_property("source", "UACC")
                graph.add_edge_without_validation(
                    Edge(start_node=uid, end_node=pid, kind=edge_kind, properties=ep)
                )

    return graph


# ── Entry point ────────────────────────────────────────────────────────────────

def read(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def main():
    groups             = parse_groups(read(GROUP_FILE))
    users              = parse_users(read(USER_FILE))
    surrogat_profiles  = parse_rlist(read(SURROGAT_FILE), "SURROGAT")
    unixpriv_profiles  = parse_rlist(read(UNIXPRIV_FILE), "UNIXPRIV")
    facility_profiles  = parse_rlist(read(FACILITY_FILE), "FACILITY")
    dataset_profiles   = parse_datasets(read(DATASET_FILE))
    tcicstrn_profiles  = parse_rlist(read(TCICSTRN_FILE), "TCICSTRN")
    gcicstrn_profiles  = parse_gcicstrn(read(GCICSTRN_FILE))

    print(f"Parsed: {len(groups)} groups, {len(users)} users, "
          f"{len(surrogat_profiles)} surrogat profiles, "
          f"{len(unixpriv_profiles)} unixpriv profiles, "
          f"{len(facility_profiles)} facility profiles, "
          f"{len(dataset_profiles)} dataset profiles, "
          f"{len(tcicstrn_profiles)} tcicstrn profiles, "
          f"{len(gcicstrn_profiles)} gcicstrn profiles.")

    graph = build_graph(groups, users, surrogat_profiles, unixpriv_profiles, facility_profiles, dataset_profiles, tcicstrn_profiles, gcicstrn_profiles)
    print(f"Graph:  {graph.get_node_count()} nodes, {graph.get_edge_count()} edges.")

    graph.export_to_file(OUTPUT_FILE, indent=2)
    print(f"Saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
