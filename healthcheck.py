import psutil
import time
import yaml
import os
from datetime import datetime
import copy
from pynput.mouse import Controller


def get_top_cpu_processes(ignore_list, num_processes=10):
    # Get the list of all currently running processes
    processes = []

    # First pass: collect all processes to initialize CPU percent tracking
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'cmdline']):
        try:
            processes.append(proc.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    # Sleep for a brief period to allow CPU utilization to update
    time.sleep(0.1)

    # Second pass: re-collect CPU usage after allowing for calculation
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'cmdline']):
        try:
            proc_info = copy.deepcopy(proc.info)
            start_timestamp = proc.create_time()
            if start_timestamp != 0:
                start_time_str = datetime.fromtimestamp(start_timestamp).strftime("%Y-%m-%d %H:%M:%S")
            else:
                start_time_str = "Unknown"
            proc_info['process_start_time'] = start_time_str

            cmdline = " ".join(proc_info['cmdline']) if proc_info['cmdline'] else "N/A"
            no_ignore_keyword_in_argument = not any(keyword in cmdline for keyword in ignore_list)
            no_ignore_keyword_in_name = not any(keyword in proc_info['name'] for keyword in ignore_list)
            if no_ignore_keyword_in_argument and no_ignore_keyword_in_name:
                processes.append(proc_info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    active_processes = [process for process in processes if process['cpu_percent'] >= 3]
    processes = sorted(active_processes, key=lambda p: p['cpu_percent'], reverse=True)

    # Return the top N processes
    return processes[:num_processes]


def retrieve_latest_status_from_yaml():
    status = {}
    try:
        with open(file_name, 'r') as file:
            status = yaml.safe_load(file)
    except FileNotFoundError:
        pass
    return status


def handle_process_information(status, top_processes):
    processes = None
    if 'processes' not in status:
        processes = {}
        status['processes'] = processes
    processes = status['processes']
    for proc in top_processes:
        process_info = {}
        cmdline = " ".join(proc['cmdline']) if proc['cmdline'] else "N/A"
        pid = proc['pid']
        process_info["name"] = proc['name']
        process_info['process_start_time'] = proc['process_start_time']
        process_info['argument'] = cmdline
        processes[pid] = process_info

    status['processes'] = processes


'''
Read a YAML file residing on OneDrive folder that looks like this:
last_check:
computer_activity_history:
  - duration: TBD
    last_activity:
    start:
    end:
  - duration: test2
    start:
    end:
process_activity_history:
  - duration:
    start:
    end:
processes:
  - pid:
    process_argument:
'''
if __name__ == "__main__":
    ignore_list = [
        'ctfmon.exe',
        'healthcheck',
        'svchost',
        'mypy',
        'csrss.exe',
        'OneDrive.exe',
        'System Idle Process',
        'MemCompression',
        'dwm.exe',
        'explorer.exe',
        'System',
        'WindowsTerminal.exe',
        'MsMpEng.exe',
    ]
    now = datetime.now()
    current_timestamp = now.strftime('%Y-%m-%d %H:%M:%S')
    today_date = now.strftime('%Y-%m-%d')
    one_drive_path = os.environ.get('OneDrive')
    computer_name = os.environ.get('COMPUTERNAME')
    file_name = f"{one_drive_path}/healthcheck/{computer_name}_{today_date}.yaml"

    status = retrieve_latest_status_from_yaml()
    status["application_version"] = '1.0.2'
    status["activity_last_check_timestamp"] = current_timestamp

    top_processes = get_top_cpu_processes(ignore_list)
    handle_process_information(status, top_processes)

    computer_activity_list = None
    if 'computer_activity_history' not in status:
        status['computer_activity_history'] = []
    computer_activity_list = status['computer_activity_history']
    active_activity = None
    mouse = Controller()
    if mouse.position is not None:
        for activity in computer_activity_list:
            if 'TBD' in activity['duration']:
                active_activity = activity
        if active_activity is None:
            active_activity = {}
            active_activity['start'] = current_timestamp
            active_activity['last_mouse_location'] = f'{mouse.position[0]},{mouse.position[1]}'
            active_activity['duration'] = 'TBD'
            computer_activity_list.append(active_activity)
        else:
            last_mouse_location = tuple(int(num) for num in active_activity['last_mouse_location'].split(','))
            if last_mouse_location != mouse.position:
                active_activity['duration'] = 'TBD - activity started'
                active_activity['last_mouse_location'] = f'{mouse.position[0]},{mouse.position[1]}'
            if last_mouse_location == mouse.position and active_activity['duration'] == 'TBD - activity started':
                activity_start_timestamp = int(datetime.strptime(active_activity['start'], "%Y-%m-%d %H:%M:%S").timestamp())
                duration = (now.timestamp() - activity_start_timestamp) / 60
                active_activity['duration'] = f'{duration:.2f} minutes'
                active_activity['end'] = current_timestamp
                active_activity.pop('last_mouse_location')

    process_activity_history = None
    if 'process_activity_history' not in status:
        status['process_activity_history'] = {}
    process_activity_history = status['process_activity_history']
    for proc in top_processes:
        proc_name = proc['name']
        if proc_name not in process_activity_history:
            process_activity_history[proc_name] = []
        proc_activity_list = process_activity_history[proc_name]
        active_activity = None
        for activity in proc_activity_list:
            if 'TBD' in activity['duration']:
                active_activity = activity
        if active_activity is None:
            active_activity = {}
            active_activity['start'] = current_timestamp
            active_activity['duration'] = 'TBD'
            active_activity['last_cpu_busy_timestamp'] = current_timestamp
            proc_activity_list.append(active_activity)
        else:
            active_activity['last_cpu_busy_timestamp'] = current_timestamp

    for key in process_activity_history:
        proc_activity_list = process_activity_history[key]
        for activity in proc_activity_list:
            if 'TBD' in activity['duration'] and current_timestamp != activity['last_cpu_busy_timestamp']:
                activity['end'] = current_timestamp
                activity_start_timestamp = int(datetime.strptime(activity['start'], "%Y-%m-%d %H:%M:%S").timestamp())
                duration = (now.timestamp() - activity_start_timestamp) / 60
                activity['duration'] = f'{duration:.2f} minutes'

    with open(file_name, 'w') as yaml_file:
        yaml.dump(status, yaml_file, default_flow_style=False)
