import requests
import re
import base64

SP_URL = "http://web.heroctf.fr:8080"
IDP_URL_SSO = "http://web.heroctf.fr:8081/sso"
USER = "user"
PASS = "oyJPNYd3HgeBkaE%!rP#dZvqf2z*4$^qcCW4V6WM"

sess = requests.Session()

# 1. Start
print("[*] Accessing SP /flag...")
r1 = sess.get(f"{SP_URL}/flag")
saml_req_match = re.search(r'name="SAMLRequest" value="([^"]+)"', r1.text)
relay_state_match = re.search(r'name="RelayState" value="([^"]+)"', r1.text)

if not saml_req_match:
    print("[-] Failed to find SAMLRequest")
    exit(1)

saml_request = saml_req_match.group(1)
relay_state = relay_state_match.group(1) if relay_state_match else ""

# 2. Login
print("[*] Logging in...")
payload = {
    "user": USER,
    "password": PASS,
    "SAMLRequest": saml_request,
    "RelayState": relay_state
}
r2 = sess.post(IDP_URL_SSO, data=payload)

print("[-] IDP Login Response Code:", r2.status_code)
# r2 should contain the SAMLResponse in a form auto-submit or similar.
saml_resp_match = re.search(r'name="SAMLResponse" value="([^"]+)"', r2.text)
if saml_resp_match:
    saml_response_b64 = saml_resp_match.group(1)
    print("[+] Got SAMLResponse!")
    
    # Decode
    saml_xml = base64.b64decode(saml_response_b64).decode('utf-8')
    with open("saml_response.xml", "w") as f:
        f.write(saml_xml)
    print("[+] Saved saml_response.xml")
else:
    print("[-] Failed to get SAMLResponse")
    print(r2.text[:1000])
