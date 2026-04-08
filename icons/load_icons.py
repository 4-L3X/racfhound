import requests
import json
import urllib3
import sys

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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
    if len(sys.argv) != 3:
        print("[!] Missing arguments.", file=sys.stderr)
        print("[?] Usage: load-icons.py <bloodhound-url> <jwt-token>", file=sys.stderr)
        print("[?] Example: load_icons.py http://127.0.0.1:8080 ey[...]", file=sys.stderr)
        sys.exit(1)

    CUSTOM_NODE_ENDPOINT = "/api/v2/custom-nodes"
    url = sys.argv[1] + CUSTOM_NODE_ENDPOINT
    token = sys.argv[2]

    # Call function for each icon type you want to send
    define_icon(url, token, "RACF_Group", "user-group", "#00FF00")
    define_icon(url, token, "RACF_User", "user", "#FF0000")
    define_icon(url, token, "RACF_Resource", "list-ul", "#FFFF00")
    define_icon(url, token, "RACF_Dataset", "file", "#0000FF")
