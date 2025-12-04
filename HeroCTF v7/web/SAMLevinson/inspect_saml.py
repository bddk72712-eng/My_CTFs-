import xml.etree.ElementTree as ET

tree = ET.parse("saml_response.xml")
root = tree.getroot()

ns = {'saml': 'urn:oasis:names:tc:SAML:2.0:assertion'}

for assertion in root.findall('.//saml:Assertion', ns):
    subject = assertion.find('.//saml:Subject/saml:NameID', ns)
    if subject is not None:
        print("Subject:", subject.text)
    
    for attribute in assertion.findall('.//saml:Attribute', ns):
        name = attribute.get('Name')
        value = attribute.find('saml:AttributeValue', ns).text
        print(f"Attribute: {name} = {value}")
