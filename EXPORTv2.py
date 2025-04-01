from fireREST import FMC
import csv, json
from colors import red, green, blue, yellow, magenta, cyan
from getpass import getpass
import logging
import pandas as pd
import os

logging.basicConfig(filename='FMCObjectExport.log', level=logging.INFO)

h1 = """
################################################################################################

Cisco Firepower Managment Console API Object Exporter

!!! ENSURE API ACCESS IS ENABLED IN THE FMC @: SYSTEM > CONFIGURATION > REST API PREFERENCES !!!

Author: Dan Parr / @GraniteDan
Created: August 7 2023
Version: 1.0

This Script Relies on a number of Python Libraries (fireREST, csv, ansicolors, pandas, openpyxl)
################################################################################################

"""

print(yellow(h1))
filename = 'protoports.csv'
Groups = []
CSVData = []

ip = input("Enter your FMC Management IP/Hostname: ")
user = input("Enter FMC Username: ")
pwd = getpass()
fmc = FMC(hostname=ip, username=user, password=pwd, domain='Global')
pwd = None

objdata = ['host', 'network', 'networkgroup']
output_data = []

# Step 1: Download and save objects
for o in objdata:
    fn = o + '.json'
    try:
        data = getattr(fmc.object, o).get()
        with open(fn, 'w', encoding='utf-8') as jfile:
            json.dump(data, jfile, ensure_ascii=False, indent=2)
    except Exception as e:
        print(red(f"Failed to get or save data for {o}: {e}"))
        continue

    items = data.get('items') if isinstance(data, dict) else data
    if not isinstance(items, list):
        print(red(f"Unexpected format for {o}. Skipping..."))
        continue

    # Step 2: Process basic host/network entries
    if o in ['host', 'network']:
        for item in items:
            output_data.append({
                'Value': item.get('value'),
                'Name': item.get('name'),
                'Type': item.get('type')
            })

# Step 3: Load host object map for resolving Host references in groups
host_value_map = {}
try:
    with open('host.json', 'r', encoding='utf-8') as f:
        host_data = json.load(f)
        host_items = host_data.get('items') if isinstance(host_data, dict) else host_data
        for h in host_items:
            host_value_map[h.get('id')] = h.get('value')
except Exception as e:
    print(red(f"Failed to load host.json: {e}"))

# Step 4: Reprocess networkgroup.json with filtering and enrichment
try:
    with open('networkgroup.json', 'r', encoding='utf-8') as f:
        ng_data = json.load(f)
        groups = ng_data.get('items') if isinstance(ng_data, dict) else ng_data

        for group in groups:
            group_name = group.get('name')
            group_type = group.get('type')

            # Skip FQDN-only groups
            if 'objects' in group:
                if all(obj.get('type') == 'FQDN' for obj in group['objects']):
                    continue

            # Skip groups with 0.0.0.0/0 or ::/0 literals
            if 'literals' in group:
                skip_values = {'0.0.0.0/0', '::/0'}
                if any(lit.get('value') in skip_values for lit in group['literals']):
                    continue

            # Process valid literals
            for lit in group.get('literals', []):
                output_data.append({
                    'Value': lit.get('value'),
                    'Name': group_name,
                    'Type': group_type
                })

            # Process valid object references
            for obj in group.get('objects', []):
                if obj.get('type') == 'Host':
                    host_id = obj.get('id')
                    resolved_value = host_value_map.get(host_id)
                    if resolved_value:
                        output_data.append({
                            'Value': resolved_value,
                            'Name': group_name,
                            'Type': group_type
                        })

except Exception as e:
    print(red(f"Failed to process networkgroup.json: {e}"))

# Step 5: Save to Excel
df = pd.DataFrame(output_data)
excel_file = 'FMC_Object_Export.xlsx'
try:
    df.to_excel(excel_file, index=False)
    print(green(f"\nExport complete! Data saved to {excel_file}\n"))
except Exception as e:
    print(red(f"Failed to save Excel file: {e}"))
