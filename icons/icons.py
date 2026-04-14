#!/usr/bin/env python3
"""
RacfHound tool to upload custom icons to BloodHound
"""

import argparse
import logging
import requests
import sys
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Icon definitions embedded in script
ICONS = {
    "RACF_Group": {
        "icon": {"type": "font-awesome", "name": "user-group", "color": "#FFFF60"}
    },
    "RACF_User": {
        "icon": {"type": "font-awesome", "name": "user", "color": "#60FF60"}
    },
    "RACF_Resource": {
        "icon": {"type": "font-awesome", "name": "list-ul", "color": "#6060FF"}
    },
    "RACF_Dataset": {
        "icon": {"type": "font-awesome", "name": "file", "color": "#FF6060"}
    }
}


class BloodHoundRegistrar:
    def __init__(self, url, username, password):
        self.url = url.rstrip('/')
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.session.verify = False
        self.token = None

        logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)

    def login(self):
        login_url = self.url + '/api/v2/login'
        payload = {
            "login_method": "secret",
            "username": self.username,
            "secret": self.password
        }
        try:
            response = self.session.post(login_url, json=payload, timeout=30)
            if response.status_code == 200:
                data = response.json()
                self.token = data['data']['session_token']
                self.session.headers.update({'Authorization': f'Bearer {self.token}'})
                self.logger.info("Login successful to BloodHound")
                return True
            else:
                self.logger.error(f"Login failed: {response.status_code}")
                self.logger.error(f"Response: {response.text}")
                return False
        except Exception as e:
            self.logger.error(f"Login error: {e}")
            return False

    def logout(self):
        logout_url = self.url + '/api/v2/logout'
        try:
            self.session.post(logout_url)
            self.logger.info("Logged out from BloodHound")
        except Exception as e:
            self.logger.warning(f"Logout warning: {e}")

    def get_existing_kinds(self):
        try:
            response = self.session.get(self.url + '/api/v2/custom-nodes')
            if response.status_code == 200:
                data = response.json()
                kinds = [item.get('kindName') for item in data.get('data', []) if item.get('kindName')]
                self.logger.info(f"Found {len(kinds)} custom node kinds: {kinds}")
                return kinds
            else:
                self.logger.warning(f"Failed to get kinds: {response.status_code}")
                return []
        except Exception as e:
            self.logger.warning(f"Error fetching existing kinds: {e}")
            return []

    def delete_kind(self, kind):
        try:
            response = self.session.delete(self.url + f'/api/v2/custom-nodes/{kind}')
            if response.status_code == 200:
                self.logger.info(f"Deleted existing kind: {kind}")
                return True
            return False
        except Exception as e:
            self.logger.warning(f"Error deleting kind {kind}: {e}")
            return False

    def reset_all_kinds(self):
        """Reset/delete existing custom node kinds"""
        self.logger.info("Resetting existing custom node kinds...")
        existing_kinds = self.get_existing_kinds()

        if not existing_kinds:
            self.logger.info("No existing custom node kinds found to reset")
            return True

        self.logger.info(f"Found {len(existing_kinds)} kinds to reset: {existing_kinds}")
        for kind in existing_kinds:
            self.delete_kind(kind)
        return True

    def upload_icons(self, icons_data):
        """Upload icons to BloodHound"""
        payload = {"custom_types": {}}
        for type_name, type_config in icons_data.items():
            payload["custom_types"][type_name] = {
                "icon": type_config.get('icon', {}),
                "searchable_properties": type_config.get('searchable_properties', []),
                "display_property": type_config.get('display_property', 'name')
            }

        self.logger.info(f"Uploading {len(icons_data)} icon types...")
        try:
            response = self.session.post(self.url + '/api/v2/custom-nodes', json=payload, timeout=60)
            if response.status_code in [200, 201]:
                self.logger.info(f"Successfully uploaded {len(icons_data)} icon types")
                for type_name in icons_data.keys():
                    self.logger.info(f"-- {type_name} --")
                return True
            elif response.status_code == 409:
                self.logger.info("Icon types already registered")
                return False
            else:
                self.logger.error(f"Upload failed: {response.status_code}")
                self.logger.error(f"Response: {response.text}")
                return False
        except Exception as e:
            self.logger.error(f"Upload error: {e}")
            return False


def main():
    parser = argparse.ArgumentParser(description="Upload RACF custom icons to a BloodHound server")
    parser.add_argument('-s', '--server', required=True, help='BloodHound server URL')
    parser.add_argument('-u', '--username', required=True, help='BloodHound username')
    parser.add_argument('-p', '--password', required=True, help='BloodHound password')
    parser.add_argument('--reset', action='store_true', help='Reset existing custom node kinds before uploading')
    parser.add_argument('--list-existing', action='store_true', help='List existing custom node kinds and exit')

    args = parser.parse_args()

    print("RacfHound Custom Icon Upload")
    print("=" * 60)
    print(f"Icon types to upload: {len(ICONS)}")

    registrar = BloodHoundRegistrar(args.server, args.username, args.password)
    if not registrar.login():
        print("Failed to authenticate to BloodHound")
        sys.exit(1)

    try:
        if args.list_existing:
            existing = registrar.get_existing_kinds()
            print(f"\nExisting custom node kinds ({len(existing)}):")
            for kind in existing:
                print(f"   • {kind}")
            return

        if args.reset:
            if not registrar.reset_all_kinds():
                print("Reset completed with some warnings")

        if registrar.upload_icons(ICONS):
            print("\nRACF icons uploaded successfully")
            print("=" * 60)
        else:
            print("Upload failed")
            sys.exit(1)

    finally:
        registrar.logout()


if __name__ == '__main__':
    main()
