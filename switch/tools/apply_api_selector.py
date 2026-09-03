from pathlib import Path

xml_path = Path("switch/romfs/xml/activity/main.xml")
xml = xml_path.read_text()

# Diagnostic-safe implementation: keep the API selector entirely inside the
# normal Settings XML. Do not patch Borealis, do not replace tab content at
# runtime, and do not bind callbacks from the main loop. This isolates any
# Settings crash to the XML/UI itself before we add behavior back incrementally.
old_settings = '''    <brls:Tab label="Settings">
        <brls:Box width="auto" height="auto" axis="column" paddingTop="40" paddingLeft="50" paddingRight="50">
            <brls:Label width="auto" height="auto" text="Settings" fontSize="36" />
            <brls:Label width="auto" height="auto" text="Saikou Switch native port" marginTop="20" />
        </brls:Box>
    </brls:Tab>'''

new_settings = '''    <brls:Tab label="Settings">
        <brls:Box width="auto" height="auto" axis="column" paddingTop="40" paddingLeft="50" paddingRight="50">
            <brls:Label width="auto" height="auto" text="API Source" fontSize="36" />
            <brls:Label width="auto" height="auto" text="Anime API: Miruro" marginTop="20" />
            <brls:Button width="auto" height="auto" text="Miruro" marginTop="10" />
            <brls:Button width="auto" height="auto" text="AnimePahe" marginTop="6" />
            <brls:Button width="auto" height="auto" text="Gogoanime" marginTop="6" />
        </brls:Box>
    </brls:Tab>'''

if old_settings in xml:
    xml = xml.replace(old_settings, new_settings, 1)
elif 'text="Anime API: Miruro"' not in xml:
    raise SystemExit("Could not locate Settings XML block")

xml_path.write_text(xml)
print("Static API selector XML applied")
