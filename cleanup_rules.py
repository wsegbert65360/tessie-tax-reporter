import os

def clean_name(name):
    n = name.strip()
    # If the name is generic, treat it as lower priority
    generic_names = ["n/a", "??", "not applicable", "unknown", "unknown business", "not applicable", "none"]
    is_generic = n.lower() in generic_names
    return n, is_generic

def clean_addr_text(addr):
    # Normalize address for grouping
    return addr.strip().replace(", United States", "").replace(", USA", "").replace(".", "").lower()

def deduplicate_rules(filepath):
    if not os.path.exists(filepath):
        print(f"File {filepath} not found.")
        return

    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    header = []
    poi_lines = []
    in_poi_section = False

    for line in lines:
        if "POI LIST" in line:
            in_poi_section = True
            header.append(line)
            continue
        
        if not in_poi_section:
            header.append(line)
        else:
            if "|" in line:
                poi_lines.append(line.strip())

    # Map: Normalized Address -> Best POI Data
    addr_map = {}
    
    # Priority for Types
    TYPE_PRIORITY = {'HQ': 3, 'F': 2, 'P': 1, 'U': 0}

    for line in poi_lines:
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 3:
            p_type = parts[0]
            p_name, p_is_generic = clean_name(parts[1])
            p_addr_raw = parts[2]
            p_addr_norm = clean_addr_text(p_addr_raw)
            p_coords = parts[3].strip() if len(parts) >= 4 else ""
            
            p_priority = TYPE_PRIORITY.get(p_type, 0)
            
            if p_addr_norm not in addr_map:
                addr_map[p_addr_norm] = {
                    'type': p_type,
                    'priority': p_priority,
                    'name': p_name,
                    'is_generic': p_is_generic,
                    'addr': p_addr_raw,
                    'coords': p_coords
                }
            else:
                existing = addr_map[p_addr_norm]
                
                # CONFLICT RESOLUTION LOGIC:
                # 1. Favor higher type priority (HQ > F > P)
                # 2. If same priority, favor non-generic names
                # 3. Always keep coordinates if they exist
                
                change_reason = None
                
                if p_priority > existing['priority']:
                    change_reason = "Higher Priority Type"
                elif p_priority == existing['priority'] and existing['is_generic'] and not p_is_generic:
                    change_reason = "Better Name"
                
                if change_reason:
                    existing['type'] = p_type
                    existing['priority'] = p_priority
                    existing['name'] = p_name
                    existing['is_generic'] = p_is_generic
                    # Keep the more detailed address string if possible
                    if len(p_addr_raw) > len(existing['addr']):
                        existing['addr'] = p_addr_raw
                
                # Coordinate preservation: always merge coordinates if found
                if not existing['coords'] and p_coords:
                    existing['coords'] = p_coords

    # Reconstruct the file
    new_lines = header[:]
    if not new_lines[-1].endswith("\n"):
        new_lines.append("\n")
    
    # Separate into F/HQ and P
    farm_pois = [v for v in addr_map.values() if v['type'] in ['F', 'HQ']]
    pers_pois = [v for v in addr_map.values() if v['type'] == 'P']
    
    # Sort
    farm_pois.sort(key=lambda x: (x['type'] != 'HQ', x['name'].lower()))
    pers_pois.sort(key=lambda x: x['name'].lower())

    # Write Farm/HQ
    for poi in farm_pois:
        line_str = f"{poi['type']} | {poi['name']} | {poi['addr']}"
        if poi['coords']:
            line_str += f" | {poi['coords']}"
        new_lines.append(line_str + "\n")
    
    new_lines.append("\n--------------------------------\n\n")
    
    # Write Personal
    for poi in pers_pois:
        line_str = f"{poi['type']} | {poi['name']} | {poi['addr']}"
        if poi['coords']:
            line_str += f" | {poi['coords']}"
        new_lines.append(line_str + "\n")

    with open(filepath, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

if __name__ == "__main__":
    deduplicate_rules("rules.txt")
    print("Conflict-aware cleanup complete.")
