from pathlib import Path

source_path = Path("switch/source/main.cpp")
xml_path = Path("switch/romfs/xml/activity/main.xml")

source = source_path.read_text()
xml = xml_path.read_text()

# Diagnostic implementation: the selector is deliberately XML-only. No
# runtime callbacks, persistence, or additional TabFrame APIs are involved.
selector_xml = '''    <brls:Tab label="Settings">
        <brls:Box width="auto" height="auto" axis="column" paddingTop="40" paddingLeft="50" paddingRight="50">
            <brls:Label width="auto" height="auto" text="Settings" fontSize="36" />
            <brls:Label width="auto" height="auto" text="API Source" fontSize="30" marginTop="24" />
            <brls:Button width="auto" height="auto" text="Miruro" marginTop="18" />
            <brls:Button width="auto" height="auto" text="AnimePahe" marginTop="6" />
            <brls:Button width="auto" height="auto" text="Gogoanime" marginTop="6" />
        </brls:Box>
    </brls:Tab>'''

start = xml.find('    <brls:Tab label="Settings">')
if start == -1:
    raise SystemExit("Could not locate Settings XML block")
end = xml.find('    </brls:Tab>', start)
if end == -1:
    raise SystemExit("Could not locate end of Settings XML block")
end += len('    </brls:Tab>')
xml = xml[:start] + selector_xml + xml[end:]
xml_path.write_text(xml)

# The checked-in main.cpp stays untouched by this diagnostic selector.
for token in ("g_apiSource", "bind_api_settings_actions", "getActiveTab"):
    if token in source:
        raise SystemExit(f"Unexpected selector runtime token already in main.cpp: {token}")

print("Static API selector XML applied")
