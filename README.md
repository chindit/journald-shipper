# journald-shipper
Ships journald entries to ElasticSearch

## Requirements
Following packages are required:

* `Python` > 3 (Tested with 3.6)
* `python-pytz` For timezone conversion
* `python-systemd` To access journald
* `python-elasticsearch` To output to ElasticSearch
* `python-daemon` To launch script as a daemon

## Install

1. Clone the repo or download it
2. Make `journald-shipper.py` executable with `# chmod +x journald-shipper.py`
3. Move `journald-shipper.py` to _/usr/bin_ `# mv journald-shipper.py /usr/bin/`
4. Move `journald-shipper.service` to _/usr/lib/systemd/system_
5. Enable script `# systemctl enable journald-shipper.service`
6. Start script for current session `# systemctl start journald-shipper.service`
