# pokerlab_gui.py
"""
PokerLab GUI - Central interface for launching tournaments and PokerTV
with visual bot selection and settings.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import subprocess
import threading
import os
from pathlib import Path
import sys
import webbrowser

class PokerLabGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("PokerLab - Tournament & PokerTV Launcher")
        self.root.geometry("900x700")
        self.root.configure(bg='#1a1a2e')
        self.root.lift()  # Bring window to front
        self.root.attributes('-topmost', False)  # Don't always stay on top, but bring to front initially
        
        # Style configuration
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('Title.TLabel', font=('Arial', 16, 'bold'), background='#1a1a2e', foreground='white')
        style.configure('Heading.TLabel', font=('Arial', 12, 'bold'), background='#1a1a2e', foreground='#ffd700')
        style.configure('Custom.TCheckbutton', background='#1a1a2e', foreground='white', font=('Arial', 10))
        style.configure('Custom.TButton', font=('Arial', 11, 'bold'))
        
        # Discover bots
        self.bot_files = self.discover_bots()
        self.selected_bots = {}
        self.process = None
        self.last_output_file = None
        
        self.create_widgets()
        
    def discover_bots(self):
        """Discover all bot files in the bots directory."""
        bots_dir = Path("bots")
        if not bots_dir.exists():
            return []
        
        bot_files = []
        for file in bots_dir.iterdir():
            if file.suffix == ".py" and file.name != "template_bot.py":
                bot_files.append(file)
        
        return sorted(bot_files)
    
    def create_widgets(self):
        # Header
        header_frame = tk.Frame(self.root, bg='#667eea', height=60)
        header_frame.pack(fill=tk.X, padx=0, pady=0)
        header_frame.pack_propagate(False)
        
        title = tk.Label(header_frame, text="🎰 PokerLab Control Center", 
                        font=('Arial', 20, 'bold'), bg='#667eea', fg='white')
        title.pack(pady=15)
        
        # Main container
        main_frame = tk.Frame(self.root, bg='#1a1a2e')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Left panel - Bot selection
        left_panel = tk.Frame(main_frame, bg='#0f3460', relief=tk.RAISED, borderwidth=2)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        bot_label = tk.Label(left_panel, text="Select Bots", 
                           font=('Arial', 14, 'bold'), bg='#0f3460', fg='#ffd700')
        bot_label.pack(pady=10)
        
        # Scrollable bot list
        bot_canvas = tk.Canvas(left_panel, bg='#0f3460', highlightthickness=0)
        bot_scrollbar = ttk.Scrollbar(left_panel, orient="vertical", command=bot_canvas.yview)
        bot_scrollable_frame = tk.Frame(bot_canvas, bg='#0f3460')
        
        bot_scrollable_frame.bind(
            "<Configure>",
            lambda e: bot_canvas.configure(scrollregion=bot_canvas.bbox("all"))
        )
        
        bot_canvas.create_window((0, 0), window=bot_scrollable_frame, anchor="nw")
        bot_canvas.configure(yscrollcommand=bot_scrollbar.set)
        
        # Bot checkboxes
        for i, bot_file in enumerate(self.bot_files):
            bot_name = bot_file.stem
            var = tk.BooleanVar(value=False)
            self.selected_bots[bot_name] = var
            
            checkbox = tk.Checkbutton(
                bot_scrollable_frame,
                text=bot_name,
                variable=var,
                bg='#0f3460',
                fg='white',
                selectcolor='#667eea',
                activebackground='#0f3460',
                activeforeground='white',
                font=('Arial', 11),
                anchor='w',
                padx=10,
                pady=5
            )
            checkbox.pack(fill=tk.X, padx=10, pady=2)
        
        bot_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        bot_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Right panel - Settings and controls
        right_panel = tk.Frame(main_frame, bg='#1a1a2e')
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Tournament settings
        tournament_frame = tk.LabelFrame(right_panel, text="Tournament Settings", 
                                       bg='#0f3460', fg='#ffd700', 
                                       font=('Arial', 12, 'bold'), padx=15, pady=15)
        tournament_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Number of matches
        tk.Label(tournament_frame, text="Number of Matches:", 
                bg='#0f3460', fg='white', font=('Arial', 10)).grid(row=0, column=0, sticky='w', pady=5)
        self.tournament_matches = tk.Entry(tournament_frame, width=10, font=('Arial', 10))
        self.tournament_matches.insert(0, "100")
        self.tournament_matches.grid(row=0, column=1, sticky='w', padx=10, pady=5)
        
        # Seed
        tk.Label(tournament_frame, text="Random Seed:", 
                bg='#0f3460', fg='white', font=('Arial', 10)).grid(row=1, column=0, sticky='w', pady=5)
        self.tournament_seed = tk.Entry(tournament_frame, width=10, font=('Arial', 10))
        self.tournament_seed.insert(0, "12345")
        self.tournament_seed.grid(row=1, column=1, sticky='w', padx=10, pady=5)
        
        # Hands cap
        tk.Label(tournament_frame, text="Max Hands per Match:", 
                bg='#0f3460', fg='white', font=('Arial', 10)).grid(row=2, column=0, sticky='w', pady=5)
        self.tournament_hands = tk.Entry(tournament_frame, width=10, font=('Arial', 10))
        self.tournament_hands.insert(0, "2000")
        self.tournament_hands.grid(row=2, column=1, sticky='w', padx=10, pady=5)
        
        # Output file
        tk.Label(tournament_frame, text="Output File:", 
                bg='#0f3460', fg='white', font=('Arial', 10)).grid(row=3, column=0, sticky='w', pady=5)
        output_frame = tk.Frame(tournament_frame, bg='#0f3460')
        output_frame.grid(row=3, column=1, sticky='w', padx=10, pady=5)
        self.tournament_output = tk.Entry(output_frame, width=18, font=('Arial', 10))
        # Set default to results.html
        self.tournament_output.insert(0, "results.html")
        self.tournament_output.pack(side=tk.LEFT, padx=(0, 5))
        # Quick buttons for output file
        def set_html():
            self.tournament_output.delete(0, tk.END)
            self.tournament_output.insert(0, "results.html")
        def set_json():
            self.tournament_output.delete(0, tk.END)
            self.tournament_output.insert(0, "results.json")
        html_btn = tk.Button(output_frame, text="HTML", command=set_html,
                            bg='#2196F3', fg='white', font=('Arial', 8), padx=5, pady=2)
        html_btn.pack(side=tk.LEFT, padx=2)
        json_btn = tk.Button(output_frame, text="JSON", command=set_json,
                            bg='#4CAF50', fg='white', font=('Arial', 8), padx=5, pady=2)
        json_btn.pack(side=tk.LEFT, padx=2)
        
        # Launch tournament button
        tournament_btn = tk.Button(tournament_frame, text="🚀 Launch Tournament", 
                                   command=self.launch_tournament,
                                   bg='#4CAF50', fg='white', font=('Arial', 12, 'bold'),
                                   padx=20, pady=10, relief=tk.RAISED, borderwidth=2)
        tournament_btn.grid(row=4, column=0, columnspan=2, pady=15, sticky='ew')
        
        # View results button (initially disabled)
        self.view_results_btn = tk.Button(tournament_frame, text="📊 View Results", 
                                          command=self.view_results,
                                          bg='#ff9800', fg='white', font=('Arial', 11, 'bold'),
                                          padx=15, pady=8, relief=tk.RAISED, borderwidth=2,
                                          state=tk.DISABLED)
        self.view_results_btn.grid(row=5, column=0, columnspan=2, pady=10, sticky='ew')
        
        # Store last output file
        self.last_output_file = None
        
        # PokerTV settings
        pokertv_frame = tk.LabelFrame(right_panel, text="PokerTV Settings", 
                                     bg='#0f3460', fg='#ffd700', 
                                     font=('Arial', 12, 'bold'), padx=15, pady=15)
        pokertv_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Number of hands
        tk.Label(pokertv_frame, text="Number of Hands:", 
                bg='#0f3460', fg='white', font=('Arial', 10)).grid(row=0, column=0, sticky='w', pady=5)
        self.pokertv_hands = tk.Entry(pokertv_frame, width=10, font=('Arial', 10))
        self.pokertv_hands.insert(0, "10")
        self.pokertv_hands.grid(row=0, column=1, sticky='w', padx=10, pady=5)
        
        # Seed
        tk.Label(pokertv_frame, text="Random Seed:", 
                bg='#0f3460', fg='white', font=('Arial', 10)).grid(row=1, column=0, sticky='w', pady=5)
        self.pokertv_seed = tk.Entry(pokertv_frame, width=10, font=('Arial', 10))
        self.pokertv_seed.insert(0, "42")
        self.pokertv_seed.grid(row=1, column=1, sticky='w', padx=10, pady=5)
        
        # Decision timeout
        tk.Label(pokertv_frame, text="Decision Timeout (ms):", 
                bg='#0f3460', fg='white', font=('Arial', 10)).grid(row=2, column=0, sticky='w', pady=5)
        self.pokertv_timeout = tk.Entry(pokertv_frame, width=10, font=('Arial', 10))
        self.pokertv_timeout.insert(0, "500")
        self.pokertv_timeout.grid(row=2, column=1, sticky='w', padx=10, pady=5)
        
        # Launch PokerTV button
        pokertv_btn = tk.Button(pokertv_frame, text="📺 Launch PokerTV", 
                               command=self.launch_pokertv,
                               bg='#2196F3', fg='white', font=('Arial', 12, 'bold'),
                               padx=20, pady=10, relief=tk.RAISED, borderwidth=2)
        pokertv_btn.grid(row=3, column=0, columnspan=2, pady=15, sticky='ew')
        
        # Status/Output area
        status_frame = tk.LabelFrame(right_panel, text="Status", 
                                    bg='#0f3460', fg='#ffd700', 
                                    font=('Arial', 12, 'bold'), padx=10, pady=10)
        status_frame.pack(fill=tk.BOTH, expand=True)
        
        # Progress bar frame
        progress_frame = tk.Frame(status_frame, bg='#0f3460')
        progress_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.progress_label = tk.Label(progress_frame, text="Ready", 
                                       bg='#0f3460', fg='#ffd700', 
                                       font=('Arial', 10, 'bold'))
        self.progress_label.pack(side=tk.LEFT, padx=5)
        
        self.progress_bar = ttk.Progressbar(progress_frame, mode='indeterminate', length=200)
        self.progress_bar.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        self.status_text = scrolledtext.ScrolledText(status_frame, height=8, 
                                                     bg='#1a1a2e', fg='#00ff00',
                                                     font=('Consolas', 9), wrap=tk.WORD)
        self.status_text.pack(fill=tk.BOTH, expand=True)
        self.status_text.insert('1.0', "PokerLab GUI Ready!\nSelect bots and click Launch Tournament or Launch PokerTV.\n\n")
        self.status_text.config(state=tk.DISABLED)
        
        # Select All / Deselect All buttons
        select_frame = tk.Frame(left_panel, bg='#0f3460')
        select_frame.pack(fill=tk.X, padx=10, pady=10)
        
        select_all_btn = tk.Button(select_frame, text="Select All", 
                                   command=self.select_all_bots,
                                   bg='#667eea', fg='white', font=('Arial', 10),
                                   padx=10, pady=5)
        select_all_btn.pack(side=tk.LEFT, padx=5)
        
        deselect_all_btn = tk.Button(select_frame, text="Deselect All", 
                                     command=self.deselect_all_bots,
                                     bg='#f44336', fg='white', font=('Arial', 10),
                                     padx=10, pady=5)
        deselect_all_btn.pack(side=tk.LEFT, padx=5)
        
        # Add a "Bring to Front" button
        bring_front_btn = tk.Button(select_frame, text="🔝 Bring to Front", 
                                    command=self.bring_to_front,
                                    bg='#ff9800', fg='white', font=('Arial', 10),
                                    padx=10, pady=5)
        bring_front_btn.pack(side=tk.LEFT, padx=5)
    
    def select_all_bots(self):
        """Select all bots."""
        for var in self.selected_bots.values():
            var.set(True)
        self.log_status("All bots selected.")
    
    def deselect_all_bots(self):
        """Deselect all bots."""
        for var in self.selected_bots.values():
            var.set(False)
        self.log_status("All bots deselected.")
    
    def get_selected_bots(self):
        """Get list of selected bot file paths."""
        selected = []
        for bot_file in self.bot_files:
            bot_name = bot_file.stem
            if self.selected_bots[bot_name].get():
                selected.append(str(bot_file))
        return selected
    
    def log_status(self, message):
        """Add message to status text area."""
        self.status_text.config(state=tk.NORMAL)
        self.status_text.insert(tk.END, message + "\n")
        self.status_text.see(tk.END)
        self.status_text.config(state=tk.DISABLED)
    
    def launch_tournament(self):
        """Launch a tournament with selected bots."""
        selected = self.get_selected_bots()
        
        if len(selected) < 2:
            messagebox.showerror("Error", "Please select at least 2 bots for a tournament!")
            return
        
        # Check if a tournament is already running
        if self.process and self.process.poll() is None:
            response = messagebox.askyesno("Tournament Running", 
                                         "A tournament is already running. Do you want to stop it and start a new one?")
            if not response:
                return
            # Terminate the existing process
            try:
                self.process.terminate()
                self.process.wait(timeout=2)
            except:
                try:
                    self.process.kill()
                except:
                    pass
        
        try:
            matches = int(self.tournament_matches.get())
            seed = int(self.tournament_seed.get())
            hands = int(self.tournament_hands.get())
            output = self.tournament_output.get().strip()
            # Debug logging
            self.log_status(f"🔧 DEBUG: Read output field value: '{output}'")
        except ValueError:
            messagebox.showerror("Error", "Please enter valid numbers for tournament settings!")
            return
        
        # Clear status area for new tournament
        self.status_text.config(state=tk.NORMAL)
        self.status_text.delete('1.0', tk.END)
        self.status_text.config(state=tk.DISABLED)
        
        # Disable view results button for new tournament
        if hasattr(self, 'view_results_btn'):
            self.view_results_btn.config(state=tk.DISABLED)
        self.last_output_file = None
        
        # Build command
        cmd = [
            sys.executable, "tournament.py",
            "--bots"] + selected + [
            "--matches", str(matches),
            "--seed", str(seed),
            "--hands_cap", str(hands)
        ]
        
        if output:
            cmd.extend(["--output", output])
        
        self.log_status(f"{'='*60}")
        self.log_status(f"Launching NEW Tournament:")
        self.log_status(f"  Bots: {', '.join([Path(b).stem for b in selected])}")
        self.log_status(f"  Matches: {matches}")
        self.log_status(f"  Seed: {seed}")
        self.log_status(f"  Max Hands: {hands}")
        if output:
            self.log_status(f"  Output: {output}")
        else:
            self.log_status(f"  Output: (none - no file will be saved)")
        self.log_status(f"{'='*60}\n")
        
        # Update progress indicator
        self.progress_label.config(text="Tournament Running...")
        self.progress_bar.start(10)  # Start animated progress bar
        
        # Store output file for use in thread (capture before thread)
        # Make sure we capture the value correctly - empty string means None
        output_file_for_thread = output.strip() if output and output.strip() else None
        self.log_status(f"🔧 Captured output_file_for_thread: {output_file_for_thread}")
        
        # Launch in separate thread
        def run_tournament():
            try:
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True
                )
                self.process = process
                
                total_matches = matches
                matches_completed = 0
                
                # Read output line by line
                while True:
                    line = process.stdout.readline()
                    if not line:
                        break
                    
                    line_stripped = line.strip()
                    if line_stripped:
                        # Check for match completion (e.g., "Match 10/200: uberbot4 wins")
                        if "Match " in line_stripped and "/" in line_stripped:
                            try:
                                # Extract match number from "Match 10/200: ..."
                                match_part = line_stripped.split("Match ")[1].split(":")[0]
                                parts = match_part.split("/")
                                if len(parts) >= 2:
                                    matches_completed = int(parts[0].strip())
                                    total = int(parts[1].strip())
                                    # Update progress
                                    progress_pct = (matches_completed / total) * 100
                                    self.root.after(0, lambda p=progress_pct, m=matches_completed, t=total: 
                                                   self.update_progress(f"Match {m}/{t} ({p:.1f}%)", p))
                            except Exception as e:
                                pass
                        
                        self.log_status(line_stripped)
                    
                    # Force GUI update
                    self.root.update_idletasks()
                
                process.wait()
                
                # Stop progress bar
                self.root.after(0, self.progress_bar.stop)
                
                self.log_status(f"\n🔧 Tournament process finished. Return code: {process.returncode}")
                self.log_status(f"🔧 output_file_for_thread: {output_file_for_thread}")
                
                if process.returncode == 0:
                    self.log_status("\n✅ Tournament completed successfully!")
                    self.root.after(0, lambda: self.progress_label.config(text="✅ Completed!"))
                    # Enable view results button if output file was specified
                    self.log_status(f"🔧 Checking if output file exists: {output_file_for_thread}")
                    if output_file_for_thread:
                        self.log_status(f"🔧 Output file found: {output_file_for_thread}")
                        output_path = Path(output_file_for_thread)
                        # Check if file exists (might be in current directory)
                        if not output_path.is_absolute():
                            output_path = Path.cwd() / output_path
                        final_output_path = str(output_path)
                        # Use exact same pattern as test button that worked
                        self.root.after(0, lambda f=final_output_path: self.enable_view_results(f))
                        self.log_status(f"💡 Scheduled button enable for: {Path(final_output_path).name}")
                    else:
                        self.log_status(f"🔧 No output file - button will remain disabled")
                else:
                    self.log_status(f"\n❌ Tournament ended with code {process.returncode}")
                    self.root.after(0, lambda: self.progress_label.config(text="❌ Failed"))
                self.process = None  # Clear process reference when done
            except Exception as e:
                self.log_status(f"\n❌ Error: {str(e)}")
                self.root.after(0, self.progress_bar.stop)
                self.root.after(0, lambda: self.progress_label.config(text="❌ Error"))
                self.process = None
        
        thread = threading.Thread(target=run_tournament, daemon=True)
        thread.start()
    
    def update_progress(self, text, percentage):
        """Update progress bar and label (called from main thread)."""
        self.progress_label.config(text=text)
        if percentage > 0:
            self.progress_bar.stop()
            self.progress_bar.config(mode='determinate', maximum=100, value=percentage)
        else:
            if not self.progress_bar.cget('mode') == 'indeterminate':
                self.progress_bar.config(mode='indeterminate')
                self.progress_bar.start(10)
    
    def enable_view_results(self, output_file):
        """Enable the view results button and store the output file path."""
        # Exact same code that worked with test button
        self.last_output_file = output_file
        if hasattr(self, 'view_results_btn') and self.view_results_btn:
            self.view_results_btn.config(state=tk.NORMAL)
            self.log_status(f"\n✅ View Results button enabled for: {Path(output_file).name}")
            self.log_status(f"💡 Click 'View Results' to open the results!")
    
    def view_results(self):
        """Open the results HTML file in the default browser."""
        if not self.last_output_file:
            messagebox.showwarning("No Results", "No results file available. Please run a tournament with an output file specified.")
            return
        
        file_path = Path(self.last_output_file)
        if not file_path.exists():
            messagebox.showerror("File Not Found", f"Results file not found:\n{file_path}\n\nMake sure the tournament completed successfully.")
            return
        
        # Open in browser
        try:
            # Convert to absolute path and use file:// URL
            abs_path = file_path.resolve()
            url = f"file:///{abs_path.as_posix()}"
            webbrowser.open(url)
            self.log_status(f"\n🌐 Opened {file_path.name} in your browser!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open results file:\n{str(e)}")
            self.log_status(f"\n❌ Error opening results: {str(e)}")
    
    def launch_pokertv(self):
        """Launch PokerTV with selected bots."""
        selected = self.get_selected_bots()
        
        if len(selected) < 2:
            messagebox.showerror("Error", "Please select at least 2 bots for PokerTV!")
            return
        
        try:
            hands = int(self.pokertv_hands.get())
            seed = int(self.pokertv_seed.get())
            timeout = int(self.pokertv_timeout.get())
        except ValueError:
            messagebox.showerror("Error", "Please enter valid numbers for PokerTV settings!")
            return
        
        # Build command
        cmd = [
            sys.executable, "pokertv.py",
            "--bots"] + selected + [
            "--hands_cap", str(hands),
            "--seed", str(seed),
            "--decision_ms", str(timeout)
        ]
        
        self.log_status(f"\n{'='*60}")
        self.log_status(f"Launching PokerTV:")
        self.log_status(f"  Bots: {', '.join([Path(b).stem for b in selected])}")
        self.log_status(f"  Hands: {hands}")
        self.log_status(f"  Seed: {seed}")
        self.log_status(f"  Timeout: {timeout}ms")
        self.log_status(f"{'='*60}\n")
        self.log_status("PokerTV will open in your browser...\n")
        self.log_status("💡 Tip: This GUI window will stay open. You can minimize it or keep it visible.\n")
        self.log_status("💡 Tip: To return to this GUI, just click on this window or use Alt+Tab.\n")
        
        # Launch in separate process (non-blocking)
        try:
            subprocess.Popen(cmd)
            self.log_status("✅ PokerTV launched!")
            # Bring GUI window to front after launching
            self.root.after(500, self.bring_to_front)
        except Exception as e:
            self.log_status(f"❌ Error launching PokerTV: {str(e)}")
            messagebox.showerror("Error", f"Failed to launch PokerTV:\n{str(e)}")
    
    def bring_to_front(self):
        """Bring the GUI window to the front."""
        self.root.lift()
        self.root.attributes('-topmost', True)
        self.root.after(100, lambda: self.root.attributes('-topmost', False))

def main():
    root = tk.Tk()
    app = PokerLabGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()

