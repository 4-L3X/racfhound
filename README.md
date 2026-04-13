```
    ____             ______  __                      __
   / __ \____ ______/ __/ / / /___  __  ______  ____/ /
  / /_/ / __ `/ ___/ /_/ /_/ / __ \/ / / / __ \/ __  / 
 / _, _/ /_/ / /__/ __/ __  / /_/ / /_/ / / / / /_/ /  
/_/ |_|\__,_/\___/_/ /_/ /_/\____/\__,_/_/ /_/\__,_/
                             Six Degrees of IBMUSER
```

## Intro
RacfHound is a simple Bloodhound ingestor for the RACF database in z/OS mainframes, written in Python. Current supported classes are GROUP, USER, FACILITY, SURROGAT, UNIXPRIV, DATASET, GCICSTRN and TCICSTRN.

## Installation
```bash
# Clone the repo
git clone https://github.com/Alexaruman/racfhound.git
# Install the requirements
cd racfhound
pip install -r requirements.txt
```
#### Requirements:
\> Python 3.13
bhopengraph
paramiko

## Usage


