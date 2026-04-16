```
    ____             ______  __                      __
   / __ \____ ______/ __/ / / /___  __  ______  ____/ /
  / /_/ / __ `/ ___/ /_/ /_/ / __ \/ / / / __ \/ __  / 
 / _, _/ /_/ / /__/ __/ __  / /_/ / /_/ / / / / /_/ /  
/_/ |_|\__,_/\___/_/ /_/ /_/\____/\__,_/_/ /_/\__,_/
                              Six Degrees of IBMUSER
```

## Intro
In a journey to learn more about the world, I decided to build a Bloodhound ingestor for the RACF database in z/OS. RacfHound, therefore, is a simple RACF to Bloodhound collector and ingestor, written in Python. Enumeration and collection works by running TSO commands from the USS space via SSH. As Bloodhound OpenGraph is yet to support pathfinding etc. querying the data is done through cypher queries, of which I have included several. 

Current supported classes are GROUP, USER, FACILITY, SURROGAT, UNIXPRIV, DATASET, GCICSTRN and TCICSTRN.

## Graph Nodes and Edges
#### Nodes
- `RACF_Group`
- `RACF_User`
- `RACF_Resouce             -- SURROGAT, UNIXPRIV, FACILITY and CICS profiles`
- `RACF_Dataset`
#### Edges
- `RACF_MemberOf            -- User/SubGroup -> Group`
- `RACF_HasPermission       -- User -> Resource`
- `RACF_HasDatasetAccess    -- User -> Dataset`
- `RACF_TargetsUser         -- Resource -> User`

## Requirements:
- `BloodHound > 8.0`
- `Python > 3.13`
- `bhopengraph`
- `paramiko`

## Installation
```bash
# Clone the repo
git clone https://github.com/Alexaruman/racfhound.git
# Install the requirements
cd racfhound
pip install -r requirements.txt
```

## Usage
### rh_collect.py
```bash
python rh_collect.py TARGET/IP USERNAME --password PASSWORD --all
```
Collector script that does the enumeration. Creates ```racfhound_output/``` in working directory where it stores output as .txt files. If SSH is not available the collection could technically be done with JCL, as long as the output is extracted and saved in the proper format (e.g. racfhound_GROUP.txt for groups.)
##### Arguments:
| Pos. argument | Description |
|------|-------------|
| `host` | Target hostname or IP |
| `username` | SSH username |
##### Options:
| Flag | Description |
|------|-------------|
| `--password` | SSH Password |
| `--key` | Path to SSH private key |
| `--port` | SSH port (default: 22) |
| `--delay` | Seconds to wait between commands (default: 0.0) |
| `--all` | Enumerate all classes (default behavior) |
| `--classes` | Classes to enumerate (e.g. GROUP USER SURROGAT) |


### rh_parse.py
```bash
python rh_parse.py
```
Parser script that converts the output of the collector to JSON. Output is placed in `racfhound_output/` as `racfhound.json`, which can then be uploaded to BloodHound.


### rh_icons.py
```bash
python rh_icons.py -s BHSERVERURL -u BHUSERNAME -p BHPASSWORD
```
Tool for uploading custom icons to BloodHound (Credit Fa1zK4r1m and GCP-Hound)
##### Options:
| Flag | Description |
|------|-------------|
| `-s, --server` | BloodHound server URL (e.g.: `http://127.0.0.1:8080`) |
| `-u, --username` | BloodHound usernmae |
| `-p, --password` | BloodHound password |
| `--reset` | Reset any existing custom icons before uploading |
| `--list-existing` | List existing custom icons and exit |


### Cypher queries
The `customqueries` directory contains useful cypher queries that can be imported as saved queries into BloodHound.

## Disclaimer
This tool has only been tested on a z/OS V2R4 mainframe. Given that it (currently) only performs seven, basic, commands on the mainframe, however, it should be rather compatible. Testing  and feedback is much appreciated!
