```
    ____             ______  __                      __
   / __ \____ ______/ __/ / / /___  __  ______  ____/ /
  / /_/ / __ `/ ___/ /_/ /_/ / __ \/ / / / __ \/ __  / 
 / _, _/ /_/ / /__/ __/ __  / /_/ / /_/ / / / / /_/ /  
/_/ |_|\__,_/\___/_/ /_/ /_/\____/\__,_/_/ /_/\__,_/
                             Six Degrees of IBMUSER
```

## Intro
In a journey to learn more about the world, I decided to build a Bloodhound ingestor for the RACF database in z/OS. RacfHound, therefore, is a simple RACF to Bloodhound collector and ingestor, written in Python. Enumeration and collection works by running TSO commands from the USS space via SSH. Current supported classes are GROUP, USER, FACILITY, SURROGAT, UNIXPRIV, DATASET, GCICSTRN and TCICSTRN.

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


## Disclaimer
This tool has only been tested on a z/OS V2R4 mainframe environment. Given that it (currently) only performs seven, basic, commands on the mainframe, however, it should be rather compatible. Testing  and feedback is much appreciated!
