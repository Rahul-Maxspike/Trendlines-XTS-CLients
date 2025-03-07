import subprocess
import tkinter as tk
import os
import psutil
import signal

# instances = ["HDFCBANK", "AXISBANK", "INDUSINDBK", "SBIN", "INFY", "TCS","BAJFINANCE", "DLF", "LT", "TITAN", "MARUTI", "JSWSTEEL", "HINDALCO", "ASIANPAINT","BHARTIARTL", "SUNPHARMA","TATAMOTORS","RELIANCE","ULTRACEMCO","BAJAJ-AUTO"]
# instances = ["MARUTI","DLF","HDFCBANK","INFY","BAJFINANCE","ULTRACEMCO","RELIANCE","SUNPHARMA","TATAMOTORS"]
#instances=["MARUTI","DLF","JSWSTEEL","HDFCBANK","INFY","NIFTY"]
#instances =["AXISBANK","BAJFINANCE","HDFCBANK","BHARTIARTL","TCS","ULTRACEMCO","DLF","MARUTI","RELIANCE","SUNPHARMA","TATAMOTORS"]
#instances = [ "RELIANCE","AXISBANK","TATAMOTORS","MARUTI","TITAN"]  # Add your instance names here
instances = ["HDFCBANK", "SBIN", "INFY", "DLF", "TITAN", "JSWSTEEL", "ASIANPAINT", "TATAMOTORS", "RELIANCE", "BAJFINANCE"]

# instances = ["AXISBANK"]

os.chdir(f"/home/algolinux/Documents/workspace/GitHub/Endovia/LiveEngineMulti/")  # Update with your actual path
venv_activate_script = r"/home/algolinux/Documents/workspace/GitHub/Endovia/venv3.8/bin/activate"
instance_path = f"main.py"
instance_path1 = f"order_placer_main.py"

running_instances = {}

def run_command(command, title):
    terminal_process = subprocess.Popen(command, shell=True)
    
    # Wait a bit to allow the terminal to start the process
    import time
    time.sleep(1)
    
    # Find the child process (the python script)
    python_pid = None
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        if proc.ppid() == terminal_process.pid and 'python' in proc.info['name']:
            python_pid = proc.pid
            break
    
    if python_pid:
        running_instances[python_pid] = (command, terminal_process.pid)
    else:
        print(f"Failed to capture PID for instance: {title}")

def start_instances():
    for instance in instances:
        command = f"gnome-terminal --title='{instance} Main' -- bash -c 'source {venv_activate_script}; python \"{instance_path}\" {instance}; exec bash'"
        print(f"Starting instance: {instance}")
        run_command(command, instance)

def start_order_placer_instances():
    for instance in instances:
        command = f"gnome-terminal --title='{instance} Order Placer' -- bash -c 'source {venv_activate_script}; python \"{instance_path1}\" {instance}; exec bash'"
        print(f"Starting order placer instance: {instance}")
        run_command(command, instance)


def stop_instance(pid):
    instance_info = running_instances.get(pid)
    if instance_info:
        print(f"Stopping instance with Python PID {pid}")
        os.kill(pid, signal.SIGINT)
        del running_instances[pid]
    else:
        print(f"No instance found with Python PID {pid}")

def stop_instances():
    for pid in list(running_instances.keys()):
        stop_instance(pid)

def stop_all_terminals():
    for pid, (_, terminal_pid) in running_instances.items():
        print(f"Stopping terminal with PID {terminal_pid}")
        subprocess.run(["kill", "-9", str(terminal_pid)], shell=False)
    running_instances.clear()
    update_instances_listbox()  # Update the listbox after killing terminals

def update_instances_listbox():
    instances_listbox.delete(0, tk.END)
    for pid in running_instances.keys():
        instances_listbox.insert(tk.END, f"Python PID: {pid} | Terminal PID: {running_instances[pid][1]}")

root = tk.Tk()
root.title("Instance Manager")

# Set background color
root.configure(bg="lightgray")

start_button = tk.Button(root, text="Start Instances", command=start_instances, bg="green", fg="white")
start_button.pack()

start_order_placer_button = tk.Button(root, text="Start Order Placer Instances", command=start_order_placer_instances, bg="blue", fg="white")
start_order_placer_button.pack()

stop_all_button = tk.Button(root, text="Stop All Instances", command=stop_instances, bg="red", fg="white")
stop_all_button.pack()

stop_all_terminals_button = tk.Button(root, text="Stop All Terminals", command=stop_all_terminals, bg="purple", fg="white")
stop_all_terminals_button.pack()

instances_label = tk.Label(root, text="Running Instances:", bg="lightgray")
instances_label.pack()

instances_listbox = tk.Listbox(root)
instances_listbox.pack()

stop_selected_button = tk.Button(root, text="Stop Selected Instance", command=lambda: stop_instance(int(instances_listbox.get(tk.ACTIVE).split()[2])), bg="orange", fg="white")
stop_selected_button.pack()

def update_listbox_periodically():
    update_instances_listbox()
    root.after(1000, update_listbox_periodically)

update_listbox_periodically()

root.mainloop()
