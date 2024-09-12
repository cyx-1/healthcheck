import util

__version__ = "1.0.3"


def perform_healthcheck():
    '''
    Read YAML files residing on a healthcheck folder that has similar content as ./status.yml and ./healthcheck.yml
    status.yml contains information from the previous run and each run updates the status.yml with new content
    healthcheck.yml contains the configuration information such as ignore_list to tune out some processes as noises
    '''
    ignore_list, current_timestamp, current_timestamp_str, status_file_name = util.retrieve_initial_settings()

    print('retrieve information from status file')
    status = util.retrieve_dictionary_content_from_yaml(status_file_name)
    status["application_version"] = __version__
    status["activity_last_check_timestamp"] = current_timestamp_str

    print('retrieve information from top CPU processes')
    top_processes = util.get_top_cpu_processes(ignore_list)
    util.handle_process_information(status, top_processes)

    print('process activity information')
    status = util.handle_computer_activity_information(status, current_timestamp_str, current_timestamp)
    status = util.handle_process_activity_information(status, current_timestamp_str, current_timestamp, top_processes)

    print('save content into status file')
    util.save_dictionary_content_into_yaml(status_file_name, status)


if __name__ == "__main__":
    perform_healthcheck()
