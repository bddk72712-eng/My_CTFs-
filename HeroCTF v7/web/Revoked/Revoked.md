This is the story of how we turned a broken-looking login page into a SAML exploit and stole an admin-only flag.

---

## 1. First look at the challenge

The challenge description was short but packed with hints:

- Name: **SAMLevinson**  
- Tags: **2022 – cve – golang – saml**  
- URLs:
  - APP (the Service Provider): `http://web.heroctf.fr:8080`  
  - IDP (the Identity Provider): `http://web.heroctf.fr:8081`  
- IdP credentials: `user / oyJPNYd3HgeBkaE%!rP#dZvqf2z*4$^qcCW4V6WM`

The tag line basically screams: *“There’s a 2022 CVE in a Go SAML library here – go find it and abuse it.”*

So the plan was:

- Figure out how the APP and IDP talk to each other via SAML.  
- Capture a legitimate SAML response.  
- Map the behavior to a known 2022 Go SAML CVE.  
- Forge a SAML response that makes us admin and grab the flag.

---

## 2. Recognizing the vulnerability (CVE-2022-41912)

The hint `2022 - cve - golang - saml` points very quickly to:

- **Library**: `github.com/crewjam/saml` (popular Go SAML library)  
- **CVE**: **CVE-2022-41912**  

Reading about that bug, the core idea is:

- If a SAML **Response** contains **multiple `Assertion` elements**, the library:
  - Properly verifies the signature on the **first** assertion.  
  - But then also uses **other assertions** in the response **without** verifying that they’re signed.  

In other words, if we can:

1. Get a valid SAML response for the normal `user`.  
2. Clone its assertion, modify the clone (e.g. `uid=admin`, group `Administrators`), strip the signature on the clone and append it.  

Then the SP might:

- See a valid signature (on the original assertion).  
- Still trust the attributes from our extra, unsigned assertion.  

That’s the whole exploit: **add a second, malicious assertion behind a valid one.**

---

## 3. Poking at the APP (SP)

We started from the APP URL: `http://web.heroctf.fr:8080`.

- The home page shows a classic login form (username/password) that doesn’t seem to be the key to the challenge.  
- There’s also a button labeled something like **“SSO Login”** that points to `/flag`.

So we went to `/flag` directly.

At `/flag`, instead of a flag, we found an **HTML form** with hidden inputs:

- `SAMLRequest` – big base64 blob.  
- `RelayState` – random-looking token.  
- The form `action` points to the IdP endpoint: `http://web.heroctf.fr:8081/sso`.

This is a classic SP-initiated SAML flow:

1. The APP (SP) generates a `SAMLRequest` when we hit `/flag`.  
2. The browser is supposed to POST this to the IdP at `/sso`.  
3. The IdP authenticates us and returns a `SAMLResponse` back to the APP.

So the first goal became: **automatize exactly what the browser would do** but in Python so we can intercept and edit things.

---

## 4. Automating the SAML flow

We used Python 3 with a few standard libraries:

- `requests` – to simulate the browser.  
- `re` – quick-and-dirty HTML parsing to grab hidden inputs.  
- `base64` – to decode/encode SAML messages.  
- `xml.etree.ElementTree` – to parse and modify XML.  
- `copy` – to clone XML nodes.

To keep things clean, we created a few small scripts in the challenge folder.

### 4.1. Getting the IdP login form (`step1_get_login_form.py`)

We wrote a script to follow the SP → IdP redirection manually:

1. Start a `requests.Session`.  
2. `GET http://web.heroctf.fr:8080/flag`.  
3. Use regex to grab from the HTML:
   - The `SAMLRequest` value.  
   - The `RelayState` value.  
   - The form `action` (IdP URL, which turned out to be `http://web.heroctf.fr:8081/sso`).
4. POST those fields to the IdP `/sso` endpoint.  
5. Print the HTML we got back.

The response was exactly what we expected: the IdP login page, with:

- Text inputs `user` and `password`.  
- Hidden `SAMLRequest` and `RelayState` carried through from the SP.

So the pipeline SP → IdP was clear and we were ready to login with the provided account.

### 4.2. Logging in and catching the SAMLResponse (`step2_get_saml_response.py`)

Next, we wanted a **real SAMLResponse** issued for the given user.

We built another script that:

1. Again requests `/flag` from the SP and extracts `SAMLRequest` + `RelayState`.  
2. POSTs to `http://web.heroctf.fr:8081/sso` but this time with:
   - `user` = `user`  
   - `password` = the long provided password  
   - `SAMLRequest` and `RelayState` from the SP.
3. The IdP answers with an HTML form that would auto-submit back to the SP. In that form is:
   - `SAMLResponse` – a huge base64 string.
4. We use regex again to grab the `SAMLResponse` value.  
5. Instead of dumping the whole XML on the console (where it would be truncated), we base64-decode it and save it into a file called `saml_response.xml`.

Running this script once gave us a **clean, real SAML response** to study offline.

---

## 5. Understanding what the IdP thinks we are

With `saml_response.xml` in hand, we wanted to know: *“Who am I according to this SAML assertion?”*

We quickly wrote `inspect_saml.py`:

- Parse `saml_response.xml` with `ElementTree`.  
- Use the SAML XML namespaces.  
- Find all `saml:Assertion` elements.  
- For each one, print:
  - Subject (NameID) if present.  
  - All `Attribute` names and their `AttributeValue`.

Running this showed something like:

- `uid = user`  
- `eduPersonAffiliation = Users`

On the web UI side, when we completed the normal SAML login flow, the APP greeted us as a **simple user** and explicitly said we were **not** part of the *“Administrators”* group.

So, the situation was now clear:

- We had a valid signed SAML assertion for user `user` in group `Users`.  
- We needed to turn that into something an admin would have, without touching the IdP.

Perfect playground for a SAML assertion confusion bug.

---

## 6. Connecting it to CVE-2022-41912

Going back to the CVE:

- Vulnerable behaviour: the SP accepts a **SAML Response with multiple assertions**, verifies the signature on the first one, but still processes the rest as if they were trustworthy.  
- Attack idea: sneak in a second assertion that says *we* are an admin, and let the SP do the wrong thing.

So our plan became:

1. Take the real SAML response we just captured.  
2. Parse it and find the (single) `Assertion` inside.  
3. Clone that assertion.  
4. On the cloned assertion:
   - Remove its `ds:Signature` (because we’re going to tamper with it).  
   - Change the **attributes** to:
     - `uid = admin`  
     - `eduPersonAffiliation = Administrators`  
5. Append this malicious assertion as a **second** assertion inside the same `Response`.  
6. Base64-encode the modified XML and POST it to the SP ACS endpoint, together with the original `RelayState`.

If the challenge really uses the vulnerable `crewjam/saml`, that should be enough to trick it.

---

## 7. Building the exploit script (`solve_exploit.py`)

To avoid doing everything by hand each time, we wrote one final script: `solve_exploit.py`.

### 7.1. Getting a fresh SAMLResponse on demand

Inside that script, the first piece was a helper function, conceptually:

- Start a new HTTP session.  
- Hit `/flag` on the SP to get a **fresh** `SAMLRequest` and `RelayState`.  
- POST to the IdP `/sso` with our known credentials and those values.  
- Extract the resulting `SAMLResponse` from the IdP’s HTML form.  
- Return the base64 SAML response, the associated `RelayState`, and the session.

This kept the whole flow realistic and avoided replaying stale tokens.

### 7.2. Cloning and poisoning the assertion

Once we had the SAMLResponse in memory, we:

1. Base64-decoded it to get the XML string.  
2. Parsed it with `ElementTree`.  
3. Found the first `saml:Assertion` (the signed one).  
4. Used `copy.deepcopy` to create `malicious_assertion` from that valid assertion.

Then came the crucial part.

On the cloned assertion we:

- **Removed the signature** node (`ds:Signature`).  
- Changed its `ID` attribute to a new unique value (so it doesn’t clash with the original assertion).  
- Walked over all `Attribute` elements:
  - When a value was `user`, we changed it to `admin`.  
  - When a value was `Users`, we changed it to `Administrators`.

This effectively created a second assertion that claimed:

- The same subject, but now **uid = admin** and **affiliation = Administrators**.

Finally, we appended this cloned assertion to the SAML `Response`, so the XML now contained:

1. The original, valid, signed assertion for `user` / `Users`.  
2. Our extra, unsigned, malicious assertion giving us admin powers.

### 7.3. Sending the forged response to the SP

With the XML modified, we:

1. Serialized the `Response` back to bytes and base64-encoded it.  
2. Took the ACS URL from the `Destination` attribute of the original response (or defaulted to `/saml/acs` on the APP).  
3. Sent a POST request to the ACS endpoint with form fields:
   - `SAMLResponse` = our modified base64 blob.  
   - `RelayState` = the original `RelayState` we had from the SP.

Time to see what the APP thought about that.

---

## 8. Debugging the first attempt

Our **first try** with the exploit only changed the `uid` from `user` to `admin`, and left the group as `Users`.

The result was interesting:

- The APP still displayed us as a **simple user**.  
- In the “technical details” section, attributes looked like:
  - `uid = user, admin`  
  - `eduPersonAffiliation = Users, Users`

So clearly the APP was merging attributes from **both** assertions (which is already suspicious), but its authorization logic was more strict:

- To see the flag, you needed to be **in the Administrators group**, not just have `uid=admin` somewhere.

This confirmed two things:

1. The server really was combining attributes from multiple assertions.  
2. We needed to also tamper with the **group/affiliation** field, not just the uid.

---

## 9. Final tweak: joining the Administrators

We went back to `solve_exploit.py` and extended the logic on the cloned assertion:

- In addition to changing `uid` from `user` → `admin`, we also changed `eduPersonAffiliation` from `Users` → `Administrators`.

Then we reran the exploit.

This time, the protected page looked very different:

- A clear **“Admin”** tag instead of “Simple user”.  
- A green message telling us access was granted.  
- And, most importantly, a `<pre>` block containing the flag.

The “technical details” now showed:

- `eduPersonAffiliation = Users, Administrators`  
- `uid = user, admin`

Exactly what we expected from merging the two assertions.

At that point, we just grabbed the string in the flag box:

- **Hero{S4ML_3XPL01T_FR0M_CR3J4M}**

Flag captured.

---

## 10. Takeaways

This challenge is a clean, practical demonstration of why SAML (and XML signatures in general) is so tricky:

- Validating *one* signed assertion is not enough if you’re going to also trust *other* assertions in the same response.  
- Libraries and apps must carefully tie what is authorized to what is actually signed.

From a defense point of view, the fix is:

- Use a version of `github.com/crewjam/saml` that includes the fix for CVE-2022-41912.  
- Reject unexpected extra assertions, or ensure that **every assertion** that influences authorization is covered by a valid signature.  
- Be suspicious of “it works if I add another XML block” patterns.

From an attacker / CTF player point of view, the workflow was:

- Read the hint and map it to a real-world CVE.  
- Automate the SAML flow so you can see and modify the raw XML.  
- Confirm your baseline privileges.  
- Craft a second assertion that says what you *want* the server to believe.  
- Let the vulnerable library do the rest for you.

And that’s how the SAMLevinson fan club site leaked its secret flag.
