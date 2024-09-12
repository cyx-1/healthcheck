import yaml
import psutil
import copy
from datetime import datetime
import time
import sys
import os
from pynput.mouse import Controller


def handle_computer_activity_information(status, current_timestamp_str, current_timestamp):
    computer_activity_list = setup_dictionary_in_dictionary_if_necessary(status, 'computer_activity_history')
    active_activity = None
    mouse = Controller()
    if mouse.position is None:
        return

    for activity in computer_activity_list:
        if 'TBD' in activity['duration']:
            active_activity = activity
    if active_activity is None:
        active_activity = {}
        active_activity['start'] = current_timestamp_str
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
            duration = (current_timestamp - activity_start_timestamp) / 60
            active_activity['duration'] = f'{duration:.2f} minutes'
            active_activity['end'] = current_timestamp_str
            active_activity.pop('last_mouse_location')
    return status


def handle_process_activity_information(status, current_timestamp_str, current_timestamp, top_processes):
    process_activity_history = setup_dictionary_in_dictionary_if_necessary(status, 'process_activity_history')
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
            active_activity['start'] = current_timestamp_str
            active_activity['duration'] = 'TBD'
            active_activity['last_cpu_busy_timestamp'] = current_timestamp_str
            proc_activity_list.append(active_activity)
        else:
            active_activity['last_cpu_busy_timestamp'] = current_timestamp_str

    handle_process_activity_termination(process_activity_history, current_timestamp_str, current_timestamp)
    return status


def handle_process_activity_termination(process_activity_history, current_timestamp_str, current_timestamp):
    for key in process_activity_history:
        proc_activity_list = process_activity_history[key]
        for activity in proc_activity_list:
            if 'TBD' in activity['duration'] and current_timestamp_str != activity['last_cpu_busy_timestamp']:
                activity['end'] = current_timestamp_str
                activity_start_timestamp = int(datetime.strptime(activity['start'], "%Y-%m-%d %H:%M:%S").timestamp())
                duration = (current_timestamp - activity_start_timestamp) / 60
                activity['duration'] = f'{duration:.2f} minutes'


def setup_dictionary_in_dictionary_if_necessary(status, dict_name):
    if dict_name not in status:
        status[dict_name] = {}
    return status[dict_name]


def retrieve_initial_settings():
    ignore_list = retrieve_dictionary_content_from_yaml(sys.argv[1])['ignore_list']
    now = datetime.now()
    current_timestamp = now.timestamp()
    current_timestamp_str = now.strftime('%Y-%m-%d %H:%M:%S')
    today_date = now.strftime('%Y-%m-%d')
    one_drive_path = os.environ.get('OneDrive')
    computer_name = os.environ.get('COMPUTERNAME')
    status_file_name = f"{one_drive_path}/healthcheck/{computer_name}_{today_date}.yaml"
    return ignore_list, current_timestamp, current_timestamp_str, status_file_name


def retrieve_dictionary_content_from_yaml(file_name):
    status = {}
    try:
        with open(file_name, 'r') as file:
            status = yaml.safe_load(file)
    except FileNotFoundError:
        pass
    return status


def save_dictionary_content_into_yaml(file_name, status):
    with open(file_name, 'w') as yaml_file:
        yaml.dump(status, yaml_file, default_flow_style=False)


def get_top_cpu_processes(ignore_list, num_processes=10):
    """
    Get the list of top 10 currently running processes sorted with most CPU intensive process on top
    """
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


def handle_process_information(status, top_processes):
    """
    Store process information retrieved from psutil and store into the status data structure
    """
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
