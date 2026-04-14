import requests
import json
import urllib3
import sys

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def bloodhound_get_token(url, username, password):
    login_url = url + "/api/v2/login"
    payload = {
            "login_method": "secret",
            "username": "" % username,
            "password": "" % password
    }
    print(f"Username: {username}, Password: {password}")
    try:
        response = requests.post(login_url, json=payload, timeout=30, verify=False)
        if response.status_code == 200:
            data = response.json()
            token = data['data']['session_token']
            print("Login successful, retrieving JWT token")
            return token
        else:
            print(f"Login failed: {response.status_code}")
            sys.exit(1)
    except Exception as e:
        print(f"Login error: {e}")
        sys.exit(1)



def define_icon(url, token, icon_type, icon_name, icon_color):
    payload = {
        "custom_types": {
            icon_type: {
                "icon": {
                    "type": "font-awesome",
                    "name": icon_name,
                    "color": icon_color
                }
            }
        }
    }

    headers = {
        "Authorization": "Bearer %s" % token ,
        "Content-Type": "application/json"
    }

    response = requests.post(
        url,
        headers=headers,
        json=payload,
        verify=False  # Disables SSL verification
    )

    print(f"🔹 Sent icon for: {icon_type}")
    print("Status Code:", response.status_code)
    print("Response Body:", response.text)
    print("---")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("[!] Missing arguments.", file=sys.stderr)
        print("[?] Usage: load-icons.py <bloodhound-url> <bloodhound-username> <bloodhound-password>", file=sys.stderr)
        print("[?] Example: load_icons.py http://127.0.0.1:8080 USERNAME PASSWORD", file=sys.stderr)
        sys.exit(1)

    CUSTOM_NODE_ENDPOINT = "/api/v2/custom-nodes"
    url = sys.argv[1]
    username = sys.argv[2]
    password = sys.argv[3]

    token = bloodhound_get_token(url, username, password)

    icon_url = url + CUSTOM_NODE_ENDPOINT

    # Call function for each icon type you want to send
    define_icon(icon_url, token, "RACF_Group", "user-group", "#FFFF60")
    define_icon(icon_url, token, "RACF_User", "user", "#60FF60")
    define_icon(icon_url, token, "RACF_Resource", "list-ul", "#6060FF")
    define_icon(icon_url, token, "RACF_Dataset", "file", "#FF6060")
