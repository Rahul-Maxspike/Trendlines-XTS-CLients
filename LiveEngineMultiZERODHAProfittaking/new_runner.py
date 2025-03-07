import subprocess
import tkinter as tk
import os

# List of instance names
# instances= ["AXISBANK"]
# instances = ["HDFCBANK", "SBIN", "INFY", "DLF", "TITAN", "JSWSTEEL", "ASIANPAINT", "TATAMOTORS", "RELIANCE", "BAJFINANCE"]
instances = ["HDFCBANK", "AXISBANK", "INDUSINDBK", "SBIN", "INFY", "TCS","BAJFINANCE", "DLF", "LT", "TITAN", "MARUTI", "JSWSTEEL", "HINDALCO", "ASIANPAINT","BHARTIARTL", "SUNPHARMA","TATAMOTORS","RELIANCE","ULTRACEMCO","BAJAJ-AUTO"]
# Set paths

os.chdir(r"D:/ALGO/Soham/Equities/Endovia/LiveEngineMulti/")
venv_activate_script = r"D:/ALGO/Soham/Equities/Endovia/.venv/Scripts/Activate.ps1"
instance_path = r"main.py"
instance_path1 = r"order_placer_main.py"

# Dictionary to keep track of running processes
running_instances = {}
import subprocess

# Function to start a PowerShell process in a new window and assign it a title
def run_command(command, title):
    # Construct the command that will be passed to 'start' to open a new PowerShell window
    powershell_command = f'powershell -NoExit -Command "$Host.UI.RawUI.WindowTitle = \'{title}\'; {command}"'
    
    # Use 'start' to open a new window
    full_command = f'start "{title}" {powershell_command}'
    
    # Use subprocess to run the full command
    process = subprocess.Popen(full_command, shell=True)
    
    # Track the running process by its PID
    running_instances[process.pid] = command

# Function to start the main instances with {instance}main as the title
def start_instances():
    for instance in instances:
        # Command to activate virtual environment and run the main script
        command = f'. "{venv_activate_script}"; python "{instance_path}" {instance}'
        title = f"{instance}_Main"
        print(f"Starting instance: {title}")
        run_command(command, title)

# Function to start the order placer instances with {instance}order_placer as the title
def start_order_placer_instances():
    for instance in instances:
        # Command to activate virtual environment and run the order placer script
        command = f'. "{venv_activate_script}"; python "{instance_path1}" {instance}'
        title = f"{instance}_order_placer"
        print(f"Starting order placer instance: {title}")
        run_command(command, title)

# Function to stop a specific instance by its PID
def stop_instance(pid):
    command = running_instances.get(pid)
    if command:
        print(f"Stopping instance with PID {pid}: {command}")
        try:
            subprocess.run(["taskkill", "/F", "/PID", str(pid)], shell=True)
            del running_instances[pid]
        except Exception as e:
            print(f"Failed to stop instance with PID {pid}: {e}")
    else:
        print(f"No instance found with PID {pid}")

# Function to stop all running instances
def stop_instances():
    if running_instances:
        for pid in list(running_instances.keys()):
            try:
                subprocess.run(["taskkill", "/F", "/PID", str(pid)], shell=True)
                print(f"Terminated instance with PID: {pid}")
                del running_instances[pid]
            except Exception as e:
                print(f"Failed to terminate process with PID {pid}: {e}")
    else:
        print("No running instances to stop.")

# Function to update the listbox with the running PIDs
def update_instances_listbox():
    instances_listbox.delete(0, tk.END)
    for pid in running_instances.keys():
        instances_listbox.insert(tk.END, pid)

# Setup the GUI
root = tk.Tk()
root.title("Instance Manager")

# Set background color
root.configure(bg="lightgray")

# Buttons for starting/stopping instances
start_button = tk.Button(root, text="Start Instances", command=start_instances, bg="green", fg="white")
start_button.pack()

start_order_placer_button = tk.Button(root, text="Start Order Placer Instances", command=start_order_placer_instances, bg="blue", fg="white")
start_order_placer_button.pack()

stop_all_button = tk.Button(root, text="Stop All Instances", command=stop_instances, bg="red", fg="white")
stop_all_button.pack()

# Label and Listbox for displaying running instances
instances_label = tk.Label(root, text="Running Instances:", bg="lightgray")
instances_label.pack()

instances_listbox = tk.Listbox(root)
instances_listbox.pack()

# Button to stop a selected instance
stop_selected_button = tk.Button(root, text="Stop Selected Instance", command=lambda: stop_instance(int(instances_listbox.get(tk.ACTIVE))), bg="orange", fg="white")
stop_selected_button.pack()

# Function to periodically update the listbox with running instance PIDs
def update_listbox_periodically():
    update_instances_listbox()
    root.after(1000, update_listbox_periodically)

# Start the periodic update of the listbox
update_listbox_periodically()

# Start the GUI event loop
root.mainloop()
