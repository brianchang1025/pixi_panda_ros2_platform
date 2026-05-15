#!/usr/bin/env python3

import subprocess
import time
import os
import sys
import shlex
import logging
import yaml
from pathlib import Path

LOGGER = logging.getLogger(__name__)

class TmuxManager:
    def __init__(self, cwd: Path):
        self.cwd = cwd
        self.session_name = None
        self.window_name = None
    
    def launch_tmux(self):
        """
        Opens a new GNOME terminal and runs tmuxp inside it using an absolute path.
        """
        UTILS_DIR = os.path.dirname(os.path.abspath(__file__))
        # 1. Resolve the absolute path to the YAML file
        layout_name = "tmux_layout.yaml"
        abs_path = os.path.abspath(os.path.join(UTILS_DIR, layout_name))
        
        # 2. Check if the file actually exists before launching
        if not os.path.exists(abs_path):
            LOGGER.error(f"Error: Configuration file not found at {abs_path}")
            return
        
        with open(abs_path, 'r') as f:
            config = yaml.safe_load(f)
            
        # Extract names from the YAML structure
        self.session_name = config.get('session_name', 'default_session')
        
        # Windows is a list, so we get the name from the first window
        if 'windows' in config and len(config['windows']) > 0:
            self.window_name = config['windows'][0].get('window_name', 'default_window')

        # 3. Construct the gnome-terminal command
        # bash -c: executes the string as a command
        # exec bash: keeps the window open if tmux exits or fails
        cmd = [
        "gnome-terminal", 
        "--geometry=140x40",
        "--window", 
        "--", 
        "bash", "-c", f"cd {shlex.quote(str(self.cwd))} && tmuxp load {abs_path}"
        ]
        
        LOGGER.info(f"Launching GNOME Terminal with tmuxp layout: {layout_name}")
        subprocess.Popen(cmd)
        
    def send_command_to_pane(self, pane_index: int, command: str):
        """
        Sends a command to a specific tmux pane and executes it.
        """
        # Address format: session:window.pane_index
        target = f"{self.session_name}:{self.window_name}.{pane_index}"
        
        # send-keys sends the text
        # 'C-m' is the tmux way of saying "Press Enter"
        cmd = ["tmux", "send-keys", "-t", target, command, "C-m"]
        
        try:
            subprocess.run(cmd, check=True)
            LOGGER.info(f"✅ Sent '{command}' to Pane {pane_index}")
        except subprocess.CalledProcessError:
            LOGGER.error(f"❌ Error: Could not find Pane {pane_index} in session {self.session_name}")
    
    def send_interupt_to_pane(self, pane_index: int):
        """
        Sends a Ctrl+C interrupt to a specific tmux pane.
        """
        target = f"{self.session_name}:{self.window_name}.{pane_index}"
        cmd = ["tmux", "send-keys", "-t", target, "C-c"]
        
        try:
            subprocess.run(cmd, check=True)
            LOGGER.info(f"✅ Sent Ctrl+C to Pane {pane_index}")
        except subprocess.CalledProcessError:
            LOGGER.error(f"❌ Error: Could not find Pane {pane_index} in session {self.session_name}")
    
    def kill_tmux_session(self):
        """
        Kills the specified tmux session.
        """
        cmd = ["tmux", "kill-session", "-t", self.session_name]
        try:
            subprocess.run(cmd, check=True)
            LOGGER.info(f"✅ Killed tmux session: {self.session_name}")
        except subprocess.CalledProcessError:
            LOGGER.warning(f"⚠️  No tmux session named '{self.session_name}' found to kill.")
            

def main():
    # 1. Setup Logging so we can see the outputs
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    # 2. Define path (Using current directory for testing)
    test_cwd = Path(os.getcwd())
    
    # 3. Initialize Manager (Change "dual" to "single" depending on your files)
    manager = TmuxManager(mode="single", cwd=test_cwd)

    print("\n--- Phase 1: Launching Tmux ---")
    manager.launch_tmux()
    
    # Wait for tmuxp to finish loading the panes
    print("Waiting 5 seconds for tmuxp to initialize...")
    time.sleep(5)

    print("\n--- Phase 2: Sending Commands ---")
    # We send 'top' because it's a persistent process we can interrupt later
    manager.send_command_to_pane(0, "top")
    time.sleep(2)
    
    manager.send_command_to_pane(1, "echo 'Hello from Python!'")
    time.sleep(2)

    print("\n--- Phase 3: Sending Interrupt (Ctrl+C) ---")
    # This should stop the 'top' command in Pane 0
    manager.send_interupt_to_pane(0)
    time.sleep(2)

    print("\n--- Phase 4: Killing Session ---")
    input("Press Enter to kill the session and close the terminal...")
    manager.kill_tmux_session()

if __name__ == "__main__":
    main()

   