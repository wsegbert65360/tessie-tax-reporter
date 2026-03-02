import openai
import json
import os
import hashlib
import time
import logging

logger = logging.getLogger(__name__)

class DriveClassifier:
    CACHE_FILE = "classification_cache.json"

    def __init__(self, api_key):
        self.client = openai.OpenAI(api_key=api_key)
        self.cache = self._load_cache()

    def _load_cache(self):
        if os.path.exists(self.CACHE_FILE):
            try:
                with open(self.CACHE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load AI cache: {e}")
                return {}
        return {}

    def _save_cache(self):
        try:
            with open(self.CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save AI cache: {e}")

    def _get_cache_key(self, drive_data, rules_text):
        end_loc = drive_data.get('End Location', 'Unknown')
        miles = drive_data.get('Miles', 0)
        rules_hash = hashlib.md5(rules_text.encode()).hexdigest()
        return f"{end_loc}_{miles}_{rules_hash}"

    def classify_drives_batch(self, drives_batch, rules_text):
        """
        Classifies a batch of drives in a single request for efficiency.
        """
        results_map = {}
        to_classify = []
        
        for i, (drive_data, context) in enumerate(drives_batch):
            cache_key = self._get_cache_key(drive_data, rules_text)
            if cache_key in self.cache:
                results_map[i] = self.cache[cache_key]
            else:
                to_classify.append((i, drive_data, context, cache_key))

        if not to_classify:
            return [results_map[i] for i in range(len(drives_batch))]

        # Construct batch prompt
        drives_list_str = ""
        for i, drive_data, context, _ in to_classify:
            ctx_str = f" [Context: Prev Dest: {context['Previous End Location']}, Next Start: {context['Next Start Location']}]" if context else ""
            drives_list_str += f"- ID {i}: {drive_data.get('Date')} | From: {drive_data.get('Start Location')} | To: {drive_data.get('End Location')} | Miles: {drive_data.get('Miles')} | Pre-Identified: {drive_data.get('InferredName', 'None')}{ctx_str}\n"

        prompt = f"""
        You are a specialized tax classification assistant for a farming business.
        Classify the following drives into 'Business' or 'Personal' for an IRS audit summary.

        USER RULES & POIs:
        \"\"\"
        {rules_text}
        \"\"\"

        DRIVES TO CLASSIFY:
        {drives_list_str}

        **REPORTING FORMAT**
        Return a JSON object with a "results" key. 
        Each key in "results" must correspond to the "ID" of the drive.
        Example:
        {{
            "results": {{
                "0": {{
                    "Class": "Business",
                    "MissionCategory": "Livestock Care",
                    "Business purpose": "Check cattle and water",
                    "Reasoning": "Drive to known pasture location for routine livestock check.",
                    "InferredName": "East Pasture",
                    "Notes": "Standard farm route"
                }},
                ...
            }}
        }}

        AUDIT HARDENING:
        - "Reasoning" is CRITICAL. Explain WHY this fits the rules (e.g., 'Matched farm POI in Windsor', 'Completes returning leg of a business outing').
        - "Business purpose" is REQUIRED for all Business trips (3-7 words, Verb + Asset + Why).
        - Retail trips (Sonic, McDonalds, Dollar Store, Gas Stations) DEFAULT to Personal unless the pre-identified name or context strongly suggests a farm supply run.
        """

        max_retries = 3
        retry_delay = 10

        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "You are a specialized tax audit accountant for farm businesses."},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={ "type": "json_object" }
                )
                
                content = response.choices[0].message.content
                batch_res = json.loads(content).get("results", {})
                
                # Verify we got all requested indices
                for i, _, _, cache_key in to_classify:
                    res = batch_res.get(str(i))
                    if res:
                        # Ensure 'Reasoning' exists for audit purposes
                        if 'Reasoning' not in res:
                            res['Reasoning'] = "Classified based on farm-specific rules."
                        self.cache[cache_key] = res
                        results_map[i] = res
                    else:
                        # Fallback if AI missed one
                        fallback = {"Class": "Personal", "Business purpose": "", "MissionCategory": "Personal", "Reasoning": "AI skipped classification", "Notes": ""}
                        results_map[i] = fallback

                self._save_cache()
                break
            except Exception as e:
                logger.error(f"Batch AI Classification error: {e}")
                if "429" in str(e) and attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                # If it failed completely, fill to_classify indices with failure defaults
                for idx, _, _, _ in to_classify:
                    results_map[idx] = {"Class": "Personal", "Business purpose": "", "MissionCategory": "Personal", "Reasoning": f"Error: {e}", "Notes": ""}
                break

        return [results_map[idx] for idx, _, _, _ in sorted([(i, None, None, None) for i in results_map.keys()])]

    def classify_drive(self, drive_data, rules_text, context=None):
        """Legacy single-drive classification wrapper."""
        results = self.classify_drives_batch([(drive_data, context)], rules_text)
        return results[0]
