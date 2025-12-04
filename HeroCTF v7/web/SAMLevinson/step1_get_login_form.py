import requests
import re

SP_URL = "http://web.heroctf.fr:8080"
sess = requests.Session()

print("[*] Accessing SP /flag...")
r1 = sess.get(f"{SP_URL}/flag")

saml_req_match = re.search(r'name="SAMLRequest" value="([^"]+)"', r1.text)
relay_state_match = re.search(r'name="RelayState" value="([^"]+)"', r1.text)
action_match = re.search(r'action="([^"]+)"', r1.text)

if not saml_req_match:
    print("[-] Failed to find SAMLRequest")
    print(r1.text)
    exit(1)

saml_request = saml_req_match.group(1)
relay_state = relay_state_match.group(1) if relay_state_match else ""
idp_endpoint = action_match.group(1)

print(f"[+] Post to IDP: {idp_endpoint}")

# Post to IDP
payload = {
    "SAMLRequest": saml_request,
    "RelayState": relay_state
}
r2 = sess.post(idp_endpoint, data=payload)

print("[-] IDP Response Code:", r2.status_code)
print("[-] IDP Response Body Preview:")
print(r2.text[:2000])
