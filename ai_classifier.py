import openai
import json
import os
import hashlib
import time

class DriveClassifier:
    CACHE_FILE = "classification_cache.json"

    def __init__(self, api_key):
        self.client = openai.OpenAI(api_key=api_key)
        self.cache = self._load_cache()

    def _load_cache(self):
        if os.path.exists(self.CACHE_FILE):
            try:
                with open(self.CACHE_FILE, "r") as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def _save_cache(self):
        try:
            with open(self.CACHE_FILE, "w") as f:
                json.dump(self.cache, f, indent=4)
        except:
            pass

    def classify_drive(self, drive_data, rules_text, context=None):
        """
        Classifies a drive into Class (Business/Personal), Purpose, and Notes.
        Uses cached results if available to stay within rate limits.
        """
        end_loc = drive_data.get('End Location', 'Unknown')
        miles = drive_data.get('Miles', 0)
        
        # Create a cache key based on Address and Rules
        rules_hash = hashlib.md5(rules_text.encode()).hexdigest()
        cache_key = f"{end_loc}_{miles}_{rules_hash}"
        
        if cache_key in self.cache:
            return self.cache[cache_key]

        context_str = ""
        if context:
            context_str = f"""
            TRIP CONTEXT (MISSION CHAIN):
            - Previous Destination: {context['Previous End Location']}
            - Next Start Point: {context['Next Start Location']}
            """

        prompt = f"""
        You are a specialized tax classification assistant for a farming business.
        Every classification must be OBJECTIVE and defensible for an IRS audit.

        USER RULES & POIs:
        \"\"\"
        {rules_text}
        \"\"\"
        (Note: Rules use 'Type | Name | Address' or legacy format. 'F' is Farm, 'P' is Personal, 'HQ' is HeadQuarters).

        {context_str}

        DRIVE TO CLASSIFY:
        Date: {drive_data.get('Date')}
        Start Location: {drive_data.get('Start Location')}
        End Location: {end_loc}
        Pre-Identified Business: {drive_data.get('InferredName', 'None')}
        Miles: {drive_data.get('Miles')}

        CLASSIFICATION INSTRUCTIONS (AUDIT HARDENING):
        1. "Class": MUST be "Business" or "Personal".
        2. "InferredName": Use the SPECIFIC business name found (either from the Pre-Identified field or your own inference).
        3. "MissionCategory": MUST be one of: [Supply Run, Field Check, Livestock Care, Equipment Repair, Crop Inspection, Operational Support, Financial/Admin].
        4. "Business purpose": REQUIRED IF BUSINESS. 3-7 words. Pattern: **Verb + Asset + Specific Why**.
           - **STRICT ACTION**: NO fluffy or subjective verbs like "Reviewing", "Considering", "Thinking". Use objective verbs: "Inspect", "Repair", "Verify", "Purchase", "Transport".
           - *Examples*: "Inspect south pasture fence line", "Purchase diesel for tractor servicing", "Verify sprayer tip flow rate", "Check moisture in bin four".
           - **BANNED WORDS**: Routine, General, Normal, Check-in, Work, Farm business, Misc, Average, Typical.
        5. "Notes": Objectively mention businesses or entities seen at the destination address.

        RETAIL SAFETY & CONFLICT RULES:
        - **RETAIL SKEPTICISM**: If destination is a Restaurant (Sonic, McD), Dollar Store, Gas Station, Doctor, or Church, DEFAULT to "Personal" UNLESS context proves a farm supply run.
        - **CONFLICT PREVENTION**: NEVER label a trip "Business" if your notes say "No farm purpose" or "Personal stop only".
        - **0-MILE TRIPS**: Classify as "Personal".

        Respond in JSON format:
        {{
            "Class": "Business" or "Personal",
            "InferredName": "Estimated Name of Business/POI",
            "MissionCategory": "Category",
            "Business purpose": "3-7 words (Pick up fuel, Inspect cattle, etc)",
            "Notes": "Objective details"
        }}
        """

        max_retries = 5
        retry_delay = 10 

        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "You are a specialized tax classification assistant for a farming business."},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={ "type": "json_object" }
                )
                
                res = json.loads(response.choices[0].message.content)
                self.cache[cache_key] = res
                self._save_cache()
                return res
            except Exception as e:
                if "429" in str(e) and attempt < max_retries - 1:
                    print(f"Rate limit hit. Retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                
                print(f"AI Classification error: {e}")
                return {"Class": "Personal", "Business purpose": "", "MissionCategory": "Personal", "Notes": f"Error: {e}"}
