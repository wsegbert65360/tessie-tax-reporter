import argparse
import os
import pandas as pd
import csv
from datetime import datetime, timedelta
import calendar
from collections import Counter
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
from tessie_api import TessieClient
import math
from place_lookup import lookup_business_at_coords

def haversine(lat1, lon1, lat2, lon2):
    """Calculates the distance in feet between two GPS points."""
    if lat1 is None or lon1 is None or lat2 is None or lon2 is None: return float('inf')
    R = 20902231  # Radius of Earth in feet
    dLat = math.radians(lat2 - lat1)
    dLon = math.radians(lon2 - lon1)
    a = (math.sin(dLat / 2) * math.sin(dLat / 2) +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dLon / 2) * math.sin(dLon / 2))
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def get_date_range():
    print("\nSelect Report Time Frame:")
    print("1. Last Month")
    print("2. This Year (YTD)")
    print("3. Last Year")
    print("4. All Time (Default)")
    print("5. Last 7 Days")
    print("6. Custom Range")
    
    choice = input("Enter choice (1-6): ").strip()
    
    now = datetime.now()
    start_ts = None
    end_ts = None
    
    if choice == '1': # Last Month
        first_day_this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_day_last_month = first_day_this_month - timedelta(days=1)
        first_day_last_month = last_day_last_month.replace(day=1)
        start_ts = int(first_day_last_month.timestamp())
        end_ts = int(first_day_this_month.timestamp())
    elif choice == '2': # This Year
        start_ts = int(now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0).timestamp())
    elif choice == '3': # Last Year
        start_ts = int(datetime(now.year - 1, 1, 1).timestamp())
        end_ts = int(datetime(now.year - 1, 12, 31, 23, 59, 59).timestamp())
    elif choice == '5': # Last 7 Days
        end_ts = int(now.timestamp())
        start_ts = int((now - timedelta(days=7)).timestamp())
    elif choice == '6': # Custom
        s = input("Enter Start Date (YYYY-MM-DD): ")
        e = input("Enter End Date (YYYY-MM-DD): ")
        try:
            start_ts = int(datetime.strptime(s, "%Y-%m-%d").timestamp())
            end_ts = int(datetime.strptime(e, "%Y-%m-%d").timestamp()) + 86400
        except ValueError:
            print("Invalid format. Using All Time.")

    return start_ts, end_ts, choice

def get_poi_name(address, rules_text, lat=None, lon=None):
    """Returns the user-defined name for an address (GPS check first, then Name)."""
    target = clean_address(address)
    
    for line in rules_text.split('\n'):
        line = line.strip()
        if not line: continue
        # PIPE: Type | Name | Address | Lat,Lon
        if '|' in line:
            parts = [p.strip() for p in line.split('|')]
            if len(parts) >= 3:
                # 1. GPS Match (Priority)
                if len(parts) >= 4 and lat and lon and parts[3].strip():
                    try:
                        r_lat, r_lon = map(float, parts[3].split(','))
                        if haversine(lat, lon, r_lat, r_lon) <= 1000:
                            return parts[1]
                    except: pass
                # 2. Address Match
                rule_addr = clean_address(parts[2])
                if rule_addr and target and (rule_addr == target or rule_addr in target or target in rule_addr):
                    return parts[1]
    return None

def get_farm_hq_address(rules_text):
    """Robustly extracts Farm HQ address (Supports HQ type or name)."""
    for line in rules_text.split('\n'):
        if '|' in line:
            parts = [p.strip() for p in line.split('|')]
            if len(parts) >= 3 and (parts[0] == 'HQ' or parts[1] == 'HQ' or 'Farm HQ' in parts[1]):
                return parts[2]
    return "11713 NE Highway Oo, Windsor MO 65360"

def get_hq_coords(rules_text):
    """Extracts HQ GPS coordinates if available."""
    for line in rules_text.split('\n'):
        if '|' in line and (line.startswith('HQ') or 'Farm HQ' in line):
            parts = [p.strip() for p in line.split('|')]
            if len(parts) >= 4:
                try:
                    return tuple(map(float, parts[3].split(',')))
                except: pass
    return None

def is_farm_poi(address, rules_text, lat=None, lon=None):
    """Checks if an address matches a Farm POI (GPS check first)."""
    target = clean_address(address)
    for line in rules_text.split('\n'):
        if '|' in line:
            parts = [p.strip() for p in line.split('|')]
            if len(parts) >= 3 and parts[0] in ['F', 'HQ']:
                if len(parts) >= 4 and lat and lon and parts[3].strip():
                    try:
                        r_lat, r_lon = map(float, parts[3].split(','))
                        if haversine(lat, lon, r_lat, r_lon) <= 1000: return True
                    except: pass
                rule_addr = clean_address(parts[2])
                if rule_addr and target and (rule_addr == target or rule_addr in target or target in rule_addr):
                    return True
        elif '(Farm POI)' in line or line.strip().startswith('- F:'):
            rule_addr = clean_address(line)
            if rule_addr and target and (rule_addr == target or rule_addr in target or target in rule_addr):
                return True
    return False

def is_personal_poi(address, rules_text, lat=None, lon=None):
    """Checks if an address matches a Personal POI (GPS check first)."""
    target = clean_address(address)
    for line in rules_text.split('\n'):
        if '|' in line:
            parts = [p.strip() for p in line.split('|')]
            if len(parts) >= 3 and parts[0] == 'P':
                if len(parts) >= 4 and lat and lon and parts[3].strip():
                    try:
                        r_lat, r_lon = map(float, parts[3].split(','))
                        if haversine(lat, lon, r_lat, r_lon) <= 1000: return True
                    except: pass
                rule_addr = clean_address(parts[2])
                if rule_addr and target and (rule_addr == target or rule_addr in target or target in rule_addr):
                    return True
        elif '(Personal POI)' in line or line.strip().startswith('- P:'):
            rule_addr = clean_address(line)
            if rule_addr and target and (rule_addr == target or rule_addr in target or target in rule_addr):
                return True
    return False

def group_drives_into_outings(drives, rules_text, gap_seconds=14400):
    """Groups chronological drives into outings based on return-home or time gaps."""
    outings = []
    current_outing = []
    
    farm_hq = get_farm_hq_address(rules_text)
    hq_clean = clean_address(farm_hq)
    hq_coords = get_hq_coords(rules_text)
    
    for i, d in enumerate(drives):
        current_outing.append(d)
        
        is_returned_home = False
        # 1. GPS HQ check
        if hq_coords and d.get('End Lat') and d.get('End Lon'):
            if haversine(d['End Lat'], d['End Lon'], hq_coords[0], hq_coords[1]) <= 1000:
                is_returned_home = True
        # 2. Addr HQ check
        if not is_returned_home:
            is_returned_home = (clean_address(d['End Location']) == hq_clean)
        
        large_gap = False
        if i < len(drives) - 1:
            next_start = drives[i+1]['Started At']
            current_end = d['Ended At'] or (d['Started At'] + 300)
            if (next_start - current_end) > gap_seconds:
                large_gap = True
        
        if is_returned_home or large_gap:
            outings.append(current_outing)
            current_outing = []
    
    if current_outing:
        outings.append(current_outing)
    return outings

def clean_address(addr):
    """Normalizes address for maximum resilience (Handles commas, states, and abbreviations)."""
    if not addr: return ""
    addr = addr.lower().replace(".", "").replace(",", " ").strip()
    for tail in [" united states", " usa"]:
        if addr.endswith(tail): addr = addr[:-len(tail)].strip()
    replacements = {
        " missouri": " mo", " road": " rd", " highway": " hwy",
        " northeast": " ne", " northwest": " nw", " southeast": " se", " southwest": " sw",
        " boulevard": " blvd", " avenue": " ave", " street": " st", " drive": " dr", " lane": " ln",
        " north": " n", " south": " s", " east": " e", " west": " w"
    }
    for old, new in replacements.items(): addr = addr.replace(old, new)
    while "  " in addr: addr = addr.replace("  ", " ")
    return addr.strip()

def process_business_logic(outings, rules_text):
    """Tier 4 (High-Precision) Audit logic with GPS awareness."""
    hq_addr = get_farm_hq_address(rules_text)
    hq_clean = clean_address(hq_addr)
    hq_coords = get_hq_coords(rules_text)

    for outing in outings:
        total_m = sum(m['Miles'] for m in outing)
        has_f = any(is_farm_poi(m['End Location'], rules_text, m.get('End Lat'), m.get('End Lon')) for m in outing)
        biz_legs = [m for m in outing if m['Class'] == 'Business']
        biz_m = sum(m['Miles'] for m in biz_legs)
        is_proportional = total_m <= 40 or biz_m >= (total_m * 0.25)
        
        outing_has_purpose = len(biz_legs) > 0
        main_purpose = biz_legs[0].get('Business purpose', "Farm Business") if biz_legs else ""
        main_cat = biz_legs[0].get('MissionCategory', "Operational Support") if biz_legs else ""

        if not has_f:
            for m in outing:
                m['Class'] = 'Personal'
            continue

        saw_farm_poi_this_trip = False
        for i, m in enumerate(outing):
            if m['Miles'] == 0:
                m['Class'] = 'Personal'
                continue

            from_loc, to_loc = m['Start Location'], m['End Location']
            from_lat, from_lon = m.get('Start Lat'), m.get('Start Lon')
            to_lat, to_lon = m.get('End Lat'), m.get('End Lon')
            
            is_f = is_farm_poi(to_loc, rules_text, to_lat, to_lon)
            is_p_start = is_personal_poi(from_loc, rules_text, from_lat, from_lon)
            is_p_end = is_personal_poi(to_loc, rules_text, to_lat, to_lon)
            
            # HQ check with GPS
            is_hq_end = False
            if hq_coords and to_lat and to_lon:
                if haversine(to_lat, to_lon, hq_coords[0], hq_coords[1]) <= 1000:
                    is_hq_end = True
            if not is_hq_end:
                is_hq_end = (clean_address(to_loc) == hq_clean)

            is_u_start = not (is_f or is_p_start or clean_address(from_loc) == hq_clean)
            is_u_end = not (is_f or is_p_end or is_hq_end)

            notes_lower = m.get('Notes', '').lower()
            if any(term in notes_lower for term in ["no farm", "personal only", "not farm related"]) or (is_p_start and is_p_end) or (is_u_start and is_u_end):
                m['Class'] = 'Personal'
                m['Business purpose'] = ''
                continue

            if is_f: saw_farm_poi_this_trip = True

            if m['Class'] == 'Business':
                if is_p_start and is_f and not m.get('Business purpose'):
                    m['Class'] = 'Personal'
                continue

            # Promotion Logic
            is_internal = (i > 0 and i < len(outing) - 1)
            food_terms = ["sonic", "casey", "mcdonald", "dq", "dairy queen", "wendy", "taco bell", "subway", "starbuck", "gas station", "restaurant", "food", "fuel", "convenience"]
            is_food_fuel = any(term in notes_lower or term in to_loc.lower() for term in food_terms)
            
            should_promote = False
            if is_proportional and outing_has_purpose:
                if is_p_start and is_hq_end and saw_farm_poi_this_trip:
                    should_promote = True
                elif is_internal and is_food_fuel:
                    has_future_f = any(is_farm_poi(later['End Location'], rules_text, later.get('End Lat'), later.get('End Lon')) for later in outing[i+1:])
                    if saw_farm_poi_this_trip or has_future_f:
                        should_promote = True
                elif not (is_p_start or is_p_end):
                    should_promote = True

            if should_promote:
                m['Class'] = 'Business'
                m['Business purpose'] = main_purpose
                m['MissionCategory'] = main_cat
                if "Incidental" not in m['Notes']: m['Notes'] = f"Incidental stop ({m['Notes']})".strip()
            else:
                m['Class'] = 'Personal'

    return outings

class TaxReporter:
    def __init__(self, api_token, openai_key=None, progress_callback=None):
        self.api_token = api_token
        self.openai_key = openai_key
        self.progress_callback = progress_callback
        self.client = TessieClient(api_token)
        self.classifier = None
        self.rules_text = ""
        self.discovered_locations = []
        self.google_key = os.getenv("GOOGLE_MAPS_API_KEY")
        if openai_key:
            from ai_classifier import DriveClassifier
            self.classifier = DriveClassifier(openai_key)
            try:
                with open("rules.txt", "r", encoding="utf-8") as f:
                    self.rules_text = f.read()
            except:
                self.rules_text = ""

    def run(self, report_choice, start_ts=None, end_ts=None, custom_vin=None):
        try:
            vehicles = self.client.get_vehicles()
            if not vehicles: return "No vehicles found."
            vehicle = next((v for v in vehicles if v.get('vin') == custom_vin), vehicles[0])
            vin = vehicle['vin']
            
            if not start_ts or not end_ts:
                now = datetime.now()
                if report_choice == '1':
                    st = (now.replace(day=1) - timedelta(days=1)).replace(day=1)
                    start_ts, end_ts = int(st.timestamp()), int(now.replace(day=1).timestamp())
                elif report_choice == '2':
                    start_ts = int(now.replace(month=1, day=1).timestamp())
                elif report_choice == '5':
                    start_ts = int((now - timedelta(days=7)).timestamp())
                else:
                    start_ts = 0
                if not end_ts: end_ts = int(now.timestamp())

            drives_data = self.client.get_drives(vin, start_date=start_ts, end_date=end_ts)
            if not drives_data: return "No drives."

            processed_drives = []
            location_counts = Counter()
            for d in drives_data:
                start_dt = datetime.fromtimestamp(d.get('started_at'))
                end_lat, end_lon = d.get('ending_lat'), d.get('ending_lng')
                
                # Check if we already know this POI
                poi_name = get_poi_name(d.get('ending_location', 'Unknown'), self.rules_text, end_lat, end_lon)
                inferred = ""
                
                # If unknown, try automated lookup
                if not poi_name and end_lat and end_lon:
                    inferred = lookup_business_at_coords(end_lat, end_lon, self.google_key)
                    if inferred:
                        print(f"[AUTO DISCOVERY] Identified: {inferred} at {d.get('ending_location')[:30]}...")

                processed_drives.append({
                    'Date': start_dt.strftime('%Y-%m-%d'),
                    'Start Location': d.get('starting_location', 'Unknown'),
                    'End Location': d.get('ending_location', 'Unknown'),
                    'Start Lat': d.get('starting_lat'), 'Start Lon': d.get('starting_lng'),
                    'End Lat': end_lat, 'End Lon': end_lon,
                    'Odometer Start': round(d.get('starting_odometer', 0), 1),
                    'Odometer End': round(d.get('ending_odometer', 0), 1),
                    'Miles': round(d.get('odometer_distance', 0), 2),
                    'Class': 'Personal', 'MissionCategory': 'Personal', 'Business purpose': '', 'Notes': '',
                    'InferredName': inferred, 'Started At': d.get('started_at'), 'Ended At': d.get('ended_at')
                })
                location_counts[d.get('ending_location', 'Unknown')] += 1

            processed_drives.sort(key=lambda x: x['Started At'])

            if self.classifier:
                def run_ai(idx, d, prev=None, nxt=None):
                    ctx = {'Previous End Location': prev['End Location'] if prev else 'None', 'Next Start Location': nxt['Start Location'] if nxt else 'None'}
                    res = self.classifier.classify_drive(d, self.rules_text, context=ctx)
                    d.update({'Class': res.get('Class', 'Personal'), 'MissionCategory': res.get('MissionCategory', 'Personal'), 'Business purpose': res.get('Business purpose', ''), 'InferredName': res.get('InferredName', ''), 'Notes': res.get('Notes', '')})
                    return idx, d

                with ThreadPoolExecutor(max_workers=1) as ex:
                    futures = [ex.submit(run_ai, i, processed_drives[i], processed_drives[i-1] if i > 0 else None, processed_drives[i+1] if i < len(processed_drives)-1 else None) for i in range(len(processed_drives))]
                    for i, f in enumerate(as_completed(futures)):
                        if self.progress_callback: self.progress_callback((i+1)/len(processed_drives))

            self.discovered_locations = [
                {
                    'address': d['End Location'], 
                    'count': location_counts[d['End Location']], 
                    'suggested_name': d['InferredName'], 
                    'lat': d['End Lat'], 
                    'lon': d['End Lon'],
                    'class': d['Class']
                } 
                for d in processed_drives 
                if d['End Location'] != 'Unknown' and not get_poi_name(d['End Location'], self.rules_text, d['End Lat'], d['End Lon'])
            ]
            
            outings = group_drives_into_outings(processed_drives, self.rules_text)
            outings = process_business_logic(outings, self.rules_text)
            
            df = pd.DataFrame(processed_drives)
            log_file = f"drive_log_{vin}.csv"
            df.to_csv(log_file, index=False)
            
            tax_rows = []
            total_biz = total_pers = 0
            for mission in outings:
                m_miles = sum(l['Miles'] for l in mission)
                if m_miles == 0: continue
                if mission[0]['Class'] == 'Business':
                    total_biz += m_miles
                    tax_rows.append({'Date': mission[0]['Date'], 'Mission': mission[0]['Business purpose'], 'Category': mission[0]['MissionCategory'], 'Miles': round(m_miles, 1), 'Start': mission[0]['Start Location'], 'End': mission[-1]['End Location'], 'Visited': ", ".join([get_poi_name(l['End Location'], self.rules_text, l.get('End Lat'), l.get('End Lon')) or l['End Location'] for l in mission])})
                else: total_pers += m_miles
            
            tax_file = f"tax_report_{vin}.csv"
            pd.DataFrame(tax_rows).to_csv(tax_file, index=False)

            # --- AUDIT TIE-OUT ---
            if processed_drives:
                start_odo = processed_drives[0]['Odometer Start']
                end_odo = processed_drives[-1]['Odometer End']
                total_period_miles = round(end_odo - start_odo, 1) if end_odo > start_odo else 0
                
                with open(tax_file, "a", newline='', encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow([])
                    writer.writerow(["--- AUDIT TIE-OUT RECONCILIATION ---"])
                    writer.writerow(["Period Start Odometer", start_odo])
                    writer.writerow(["Period End Odometer", end_odo])
                    writer.writerow(["Total Period Miles", total_period_miles])
                    writer.writerow([])
                    writer.writerow(["Business Miles Total", round(total_biz, 1)])
                    writer.writerow(["Personal Miles Total", round(total_pers, 1)])
                    
                    # Tie-out Verification
                    total_calculated = total_biz + total_pers
                    writer.writerow(["Calculated Log Total", round(total_calculated, 1)])
                    
                    biz_pct = (total_biz / total_period_miles * 100) if total_period_miles > 0 else 0
                    writer.writerow(["Business Percentage", f"{round(biz_pct, 1)}%"])
            
            return {'tax_file': tax_file, 'log_file': log_file, 'total_biz': total_biz, 'biz_pct': (total_biz/(total_biz+total_pers))*100 if (total_biz+total_pers)>0 else 0}
        except Exception as e:
            return str(e)
