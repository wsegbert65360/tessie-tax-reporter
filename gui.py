import os
import threading
import customtkinter as ctk
from tkinter import messagebox
from dotenv import load_dotenv
from main import TaxReporter
from tessie_api import TessieClient

# Dark mode theme
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class SetupDialog(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("First Time Setup")
        self.geometry("500x450")
        self.attributes("-topmost", True)
        self.grab_set()
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(5, weight=1)
        
        self.label = ctk.CTkLabel(self, text="Welcome to Tesla Tax Reporter!", font=ctk.CTkFont(size=20, weight="bold"))
        self.label.grid(row=0, column=0, padx=20, pady=(20, 10))
        
        self.sub_label = ctk.CTkLabel(self, text="Please enter your API keys to get started.\nThese will be saved locally in a .env file.", font=ctk.CTkFont(size=14))
        self.sub_label.grid(row=1, column=0, padx=20, pady=(0, 20))
        
        # Tessie Token
        self.tessie_entry = self.create_input("Tessie API Token:", "your_tessie_token", 2)
        
        # OpenAI Key
        self.openai_entry = self.create_input("OpenAI API Key:", "sk-...", 3)
        
        # Google Maps Key
        self.google_entry = self.create_input("Google Maps API Key (Optional):", "AIza...", 4)
        
        self.save_btn = ctk.CTkButton(self, text="Save and Continue", command=self.save_keys, height=40, font=ctk.CTkFont(weight="bold"))
        self.save_btn.grid(row=6, column=0, padx=20, pady=20, sticky="ew")

    def create_input(self, label_text, placeholder, row):
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.grid(row=row, column=0, padx=20, pady=10, sticky="ew")
        frame.grid_columnconfigure(0, weight=1)
        
        lbl = ctk.CTkLabel(frame, text=label_text, font=ctk.CTkFont(size=12))
        lbl.grid(row=0, column=0, sticky="w")
        
        entry = ctk.CTkEntry(frame, placeholder_text=placeholder, width=400)
        entry.grid(row=1, column=0, sticky="ew", pady=(2, 0))
        return entry

    def save_keys(self):
        tessie = self.tessie_entry.get().strip()
        openai = self.openai_entry.get().strip()
        google = self.google_entry.get().strip()
        
        if not tessie or not openai:
            messagebox.showerror("Selection Error", "Tessie Token and OpenAI Key are required.")
            return
            
        env_content = f"TESSIE_API_TOKEN={tessie}\nOPENAI_API_KEY={openai}\nGOOGLE_MAPS_API_KEY={google}\n"
        try:
            with open(".env", "w") as f:
                f.write(env_content)
            messagebox.showinfo("Success", "API Keys saved successfully!")
            load_dotenv() # Reload
            self.parent.api_token = tessie
            self.parent.openai_key = openai
            self.parent.fetch_vehicles()
            self.destroy()
        except Exception as e:
            messagebox.showerror("File Error", f"Could not save .env file: {e}")

class TeslaTaxApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        load_dotenv()
        self.api_token = os.getenv("TESSIE_API_TOKEN")
        self.openai_key = os.getenv("OPENAI_API_KEY")
        
        self.title("Tesla Tax Reporter")
        self.geometry("900x600")
        
        if not self.api_token or not self.openai_key:
            self.after(100, lambda: SetupDialog(self))
        
        # Grid layout
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Sidebar
        self.sidebar_frame = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(4, weight=1)
        
        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="TESLA TAX", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))
        
        self.dashboard_btn = ctk.CTkButton(self.sidebar_frame, text="Dashboard", command=self.dummy_cmd, corner_radius=10)
        self.dashboard_btn.grid(row=1, column=0, padx=20, pady=10)
        
        self.rules_btn = ctk.CTkButton(self.sidebar_frame, text="Edit Rules", command=self.open_rules, corner_radius=10)
        self.rules_btn.grid(row=2, column=0, padx=20, pady=10)
        
        self.appearance_mode_label = ctk.CTkLabel(self.sidebar_frame, text="Theme:", anchor="w")
        self.appearance_mode_label.grid(row=5, column=0, padx=20, pady=(10, 0))
        self.appearance_mode_optionemenu = ctk.CTkOptionMenu(self.sidebar_frame, values=["Dark", "Light", "System"], command=self.change_appearance_mode)
        self.appearance_mode_optionemenu.grid(row=6, column=0, padx=20, pady=(10, 20))
        
        # Main View
        self.main_frame = ctk.CTkFrame(self, corner_radius=15, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")
        self.main_frame.grid_columnconfigure(0, weight=1)
        
        self.header_label = ctk.CTkLabel(self.main_frame, text="Generate Tax Report", font=ctk.CTkFont(size=32, weight="bold"))
        self.header_label.grid(row=0, column=0, padx=20, pady=(20, 40), sticky="w")
        
        # Vehicle selection
        self.v_label = ctk.CTkLabel(self.main_frame, text="Select Tesla Vehicle:", font=ctk.CTkFont(size=14))
        self.v_label.grid(row=1, column=0, padx=30, pady=(0, 5), sticky="w")
        
        self.vehicle_var = ctk.StringVar(value="Fetching vehicles...")
        self.vehicle_menu = ctk.CTkOptionMenu(self.main_frame, variable=self.vehicle_var, values=[], width=400, corner_radius=10)
        self.vehicle_menu.grid(row=2, column=0, padx=30, pady=(0, 20), sticky="w")
        
        # Timeframe selection
        self.t_label = ctk.CTkLabel(self.main_frame, text="Select Timeframe:", font=ctk.CTkFont(size=14))
        self.t_label.grid(row=3, column=0, padx=30, pady=(10, 5), sticky="w")
        
        self.timeframe_var = ctk.StringVar(value="1")
        self.radio_1 = ctk.CTkRadioButton(self.main_frame, text="Last Month", variable=self.timeframe_var, value="1")
        self.radio_1.grid(row=4, column=0, padx=40, pady=5, sticky="w")
        self.radio_2 = ctk.CTkRadioButton(self.main_frame, text="This Year (YTD)", variable=self.timeframe_var, value="2")
        self.radio_2.grid(row=5, column=0, padx=40, pady=5, sticky="w")
        self.radio_3 = ctk.CTkRadioButton(self.main_frame, text="Last Year", variable=self.timeframe_var, value="3")
        self.radio_3.grid(row=6, column=0, padx=40, pady=5, sticky="w")
        self.radio_5 = ctk.CTkRadioButton(self.main_frame, text="Last 7 Days", variable=self.timeframe_var, value="5")
        self.radio_5.grid(row=7, column=0, padx=40, pady=5, sticky="w")
        
        # Progress section
        self.progress_bar = ctk.CTkProgressBar(self.main_frame, width=500, corner_radius=10)
        self.progress_bar.grid(row=9, column=0, padx=30, pady=(40, 10), sticky="w")
        self.progress_bar.set(0)
        
        self.status_label = ctk.CTkLabel(self.main_frame, text="Ready", font=ctk.CTkFont(size=12))
        self.status_label.grid(row=10, column=0, padx=30, pady=(0, 20), sticky="w")
        
        self.generate_btn = ctk.CTkButton(self.main_frame, text="Generate Report", command=self.start_reporting, height=50, width=250, font=ctk.CTkFont(size=16, weight="bold"), corner_radius=25)
        self.generate_btn.grid(row=11, column=0, padx=30, pady=20, sticky="w")
        
        self.view_btn = ctk.CTkButton(self.main_frame, text="View Last Report", command=self.view_last_report, height=40, width=200, font=ctk.CTkFont(size=14), corner_radius=20, fg_color="gray", state="disabled")
        self.view_btn.grid(row=12, column=0, padx=30, pady=0, sticky="w")
        
        # Data
        self.vehicles_data = []
        self.last_report_path = None
        self.fetch_vehicles()

    def get_vehicle_display_name(self, v):
        branding = v.get('branding', {})
        model = branding.get('model', branding.get('name', 'Unknown Tesla'))
        vin = v.get('vin', 'UNKNOWN_VIN')
        return f"{model} ({vin[:8]}...)"

    def fetch_vehicles(self):
        if not self.api_token or self.api_token == "your_token_here":
            self.vehicle_var.set("API Token Missing/Invalid")
            return
        
        def run_fetch():
            try:
                client = TessieClient(self.api_token)
                self.vehicles_data = client.get_vehicles()
                names = [self.get_vehicle_display_name(v) for v in self.vehicles_data]
                if names:
                    self.vehicle_menu.configure(values=names)
                    self.vehicle_var.set(names[0])
                else:
                    self.vehicle_var.set("No vehicles found")
            except Exception as e:
                self.vehicle_var.set("Fetch failed (Check Console)")
        
        threading.Thread(target=run_fetch, daemon=True).start()

    def progress_callback(self, value):
        self.progress_bar.set(value)
        self.status_label.configure(text=f"AI Classification: {int(value*100)}%")

    def start_reporting(self):
        selected_name = self.vehicle_var.get()
        vin = next((v.get('vin') for v in self.vehicles_data if self.get_vehicle_display_name(v) == selected_name), None)
        
        if not vin:
            messagebox.showerror("Error", "Could not identify selected vehicle VIN.")
            return

        self.generate_btn.configure(state="disabled")
        self.progress_bar.set(0)
        self.status_label.configure(text="Initializing Pipeline...")
        threading.Thread(target=self.run_reporter_thread, args=(vin,), daemon=True).start()

    def run_reporter_thread(self, vin):
        reporter = TaxReporter(self.api_token, self.openai_key, self.progress_callback)
        self.status_label.configure(text="Fetching drive data from Tessie...")
        
        # Process data
        result = reporter.run(self.timeframe_var.get(), custom_vin=vin)
        
        def finish_gui():
            self.generate_btn.configure(state="normal")
            if isinstance(result, dict):
                # Handle discovered locations (New Pipe Format)
                if hasattr(reporter, 'discovered_locations') and reporter.discovered_locations:
                    auto_saved = []
                    manual_queue = []
                    
                    # First Pass: Auto-Save High Confidence matches
                    for loc in reporter.discovered_locations:
                        suggestion = loc.get('suggested_name')
                        ai_class = loc.get('class', 'Personal')
                        addr = loc['address']
                        
                        if suggestion and suggestion not in ["Unknown", "Unknown Business", ""]:
                            rule_type = 'F' if ai_class == 'Business' else 'P'
                            coords_str = f" | {loc['lat']},{loc['lon']}" if loc.get('lat') and loc.get('lon') else ""
                            rule = f"{rule_type} | {suggestion} | {addr}{coords_str}"
                            with open("rules.txt", "a", encoding="utf-8") as f:
                                f.write(f"\n{rule}")
                            auto_saved.append(f"{suggestion} ({rule_type})")
                        else:
                            manual_queue.append(loc)
                    
                    # Second Pass: Manual Prompts with Counter
                    total_manual = len(manual_queue)
                    for i, loc in enumerate(manual_queue, 1):
                        addr, count = loc['address'], loc['count']
                        # Show Counter in Prompt
                        prompt_text = f"QUESTION {i} OF {total_manual}\n\nNEW UNKNOWN LOCATION\nAddress: {addr}\nVisits: {count}"
                        dialog = ctk.CTkInputDialog(text=f"{prompt_text}\n\nEnter friendly name to save:", title=f"POI Discovery ({i}/{total_manual})")
                        name = dialog.get_input()
                        
                        if name:
                            is_farm = messagebox.askyesno("Audit Shield", f"Is '{name}' a Farm POI?\n\n(Yes = Business, No = Personal)")
                            rule_type = 'F' if is_farm else 'P'
                            coords_str = f" | {loc['lat']},{loc['lon']}" if loc.get('lat') and loc.get('lon') else ""
                            rule = f"{rule_type} | {name} | {addr}{coords_str}"
                            with open("rules.txt", "a", encoding="utf-8") as f:
                                f.write(f"\n{rule}")
                    
                    if auto_saved:
                        messagebox.showinfo("Audit Shield Discovery", f"Automatically identified and saved {len(auto_saved)} locations:\n\n" + "\n".join(auto_saved[:10]) + ("\n..." if len(auto_saved) > 10 else ""))
                
                self.status_label.configure(text="Success: Report Generated")
                self.last_report_path = result['tax_file']
                self.view_btn.configure(state="normal", fg_color=["#3B8ED0", "#1F6AA5"]) 
                
                msg = f"Report Successfully Created!\n\nBusiness Miles: {result['total_biz']:.1f}\nBusiness Usage: {result['biz_pct']:.1f}%\n\nFiles:\n- {result['tax_file']}\n- {result['log_file']}"
                messagebox.showinfo("Success", msg)
                os.startfile('.')
            else:
                self.status_label.configure(text="Error occurred")
                messagebox.showerror("Execution Error", str(result))
        
        self.after(0, finish_gui)

    def view_last_report(self):
        if self.last_report_path and os.path.exists(self.last_report_path):
            os.startfile(self.last_report_path)

    def open_rules(self):
        os.startfile('rules.txt')

    def change_appearance_mode(self, new_mode):
        ctk.set_appearance_mode(new_mode)

    def dummy_cmd(self):
        pass

if __name__ == "__main__":
    app = TeslaTaxApp()
    app.mainloop()
