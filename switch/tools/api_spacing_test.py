from pathlib import Path

xml_path = Path("switch/romfs/xml/activity/main.xml")
xml = xml_path.read_text()

for button_id in ("api-source-miruro", "api-source-animepahe", "api-source-gogoanime"):
    marker = f'<brls:Button id="{button_id}"'
    pos = xml.find(marker)
    if pos == -1:
        raise SystemExit(f"Missing {button_id}")
    end = xml.find(" />", pos)
    if end == -1:
        raise SystemExit(f"Malformed {button_id}")
    block = xml[pos:end]
    if "marginTop=" not in block:
        block += ' marginTop="10"'
        xml = xml[:pos] + block + xml[end:]

xml_path.write_text(xml)
print("API source button spacing applied")
