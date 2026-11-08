#!/usr/bin/env python3
"""
Generate minimal but valid stub includes for skinvariables generator.
These stubs provide enough structure to prevent GetDirectory errors
when the skin loads before the generator runs.
"""

import os
import sys
import json
import xml.etree.ElementTree as ET

SKIN_DIR = "/data/data/com.termux/files/home/kodi-netflix/src/skin.netflixlike"
SHORTCUTS_DIR = os.path.join(SKIN_DIR, "shortcuts")

# Read generator config
with open(os.path.join(SHORTCUTS_DIR, "skinvariables-generator.json")) as f:
    gen = json.load(f)

# Read all templates
def read_template(path):
    full = os.path.join(SHORTCUTS_DIR, path)
    with open(full) as f:
        return f.read()

# Basic template rendering (simplified)
def render_template(template_str, values):
    """Simple template rendering for {key} placeholders."""
    result = template_str
    for k, v in values.items():
        result = result.replace(f"{{{k}}}", str(v))
    return result

# Generate minimal stubs for each includes_name from the genxml
stub_includes = {}

for item in gen["genxml"]:
    datafile = item["datafile"]
    full_path = os.path.join(SHORTCUTS_DIR, datafile)
    if not os.path.exists(full_path):
        continue
    
    with open(full_path) as f:
        data = json.load(f)
    
    template_path = data.get("template", "")
    if not template_path:
        continue
    
    template_str = read_template(template_path)
    includes_name = data.get("includes_name", "")
    if not includes_name:
        continue
    
    # For stub purposes, we just need a valid include structure
    # Create minimal content that won't cause GetDirectory errors
    if "items" in data.get("includes_part", ""):
        # This include generates a list of items - provide minimal items
        stub_includes[includes_name] = f'<include name="{includes_name}"><items></items></include>'
    else:
        stub_includes[includes_name] = f'<include name="{includes_name}"></include>'

# Also add static includes from the generator config
# These are the ones referenced in the skin XML
static_includes = [
    "Hub_Menu_Group",
    "skinvariables-homemenu-customitems",
    "skinvariables-homemenu-spotlight",
    "skinvariables-homemenu-staticitems",
    "skinvariables-homemenu-submenu",
    "skinvariables-homemenu-widgets",
    "skinvariables-homemenu-widgets-listcheck",
    "skinvariables-options-tray-customitems",
    "skinvariables-options-tray-onload",
    "skinvariables-options-tray-spotlight",
    "skinvariables-options-tray-staticitems",
    "skinvariables-options-tray-submenu",
    "skinvariables-options-tray-widgets",
    "skinvariables-options-tray-widgets-listcheck",
    "skinvariables-powermainmenu-customitems",
    "skinvariables-powermainmenu-spotlight",
    "skinvariables-powermainmenu-staticitems",
    "skinvariables-powermainmenu-submenu",
    "skinvariables-powermainmenu-widgets",
    "skinvariables-powermainmenu-widgets-listcheck",
    "skinvariables-searchmenu-customitems",
    "skinvariables-searchmenu-selector",
    "skinvariables-searchmenu-spotlight",
    "skinvariables-searchmenu-staticitems",
    "skinvariables-searchmenu-submenu",
    "skinvariables-searchmenu-widgets",
    "skinvariables-searchmenu-widgets-listcheck",
    "skinvariables-sidemenu-customitems",
    "skinvariables-sidemenu-spotlight",
    "skinvariables-sidemenu-staticitems",
    "skinvariables-sidemenu-submenu",
    "skinvariables-sidemenu-widgets",
    "skinvariables-sidemenu-widgets-listcheck",
    "skinvariables-skinusers",
]

# Write the stub file
output = ['<?xml version="1.0" encoding="UTF-8"?>', '<includes>']
for name in sorted(set(list(stub_includes.keys()) + static_includes)):
    if name in stub_includes:
        output.append(f'    {stub_includes[name]}')
    else:
        # Provide minimal valid structure for item-based includes
        if any(keyword in name for keyword in ["widgets", "items", "staticitems", "customitems", "spotlight", "submenu"]):
            output.append(f'    <include name="{name}"><items></items></include>')
        else:
            output.append(f'    <include name="{name}"></include>')
output.append('</includes>')

stub_file = os.path.join(SKIN_DIR, "1080i", "script-skinvariables-generator-includes-.xml")
with open(stub_file, "w") as f:
    f.write("\n".join(output))

print(f"Generated stub file: {stub_file}")
print(f"Includes: {len(output)-2}")

# Also create skinusers stub
skinusers_file = os.path.join(SKIN_DIR, "1080i", "script-skinvariables-skinusers.xml")
with open(skinusers_file, "w") as f:
    f.write('<?xml version="1.0" encoding="UTF-8"?>\n<includes>\n    <!-- Minimal stub -->\n</includes>')
print(f"Generated skinusers stub: {skinusers_file}")

