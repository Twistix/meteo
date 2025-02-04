import os
import time
import json
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta


class arome001_downloader:
    def __init__(self, model_settings, user_settings):
        # Init model from model settings and user settings JSON files
        with open(model_settings, "r") as file:
            data = json.load(file)
            self.settings = data["arome001"]
        with open(user_settings, "r") as file:
            data = json.load(file)
            self.api_key = data["api_keys"]["arome001"]


    def get_status(self):
        # Try a request to the API to see if its working
        url = self.settings["server"]+self.settings["capabilities_path"]
        params = {
            "service": "WCS",
            "version": "2.0.1",
            "language": "eng"
        }
        headers = {
            "apikey": self.api_key
        }
        response = requests.get(url, params=params, headers=headers, timeout=5)
        if response.status_code == 200:
            return "online"
        else:
            return "offline"


    def get_available_datas(self):
        # Return the list of data types in the model settings JSON
        return list(self.settings["data_types"].keys())


    def get_last_run(self, data_type):
        latest_run_time = None

        # Check if the requested data type is present in this model
        data_type_params = self.settings["data_types"].get(data_type)
        if (data_type_params == None):
            return None

        # Get patterns to be searched in the capabilities XML file
        pattern_prefix, pattern_suffix = data_type_params["coverage_id"].split("{run_time}")

        # Construct the request URL to download model capabilities XML file
        url = self.settings["server"]+self.settings["capabilities_path"]
        params = {
            "service": "WCS",
            "version": "2.0.1",
            "language": "eng"
        }
        headers = {
            "apikey": self.api_key
        }

        # Make the HTTP request and retry when time out
        while True:
            try:
                response = requests.get(url, params=params, headers=headers, timeout=5)
                response.raise_for_status()
                break
            except requests.exceptions.Timeout:
                time.sleep(2)
            except requests.exceptions.RequestException:
                return None

        # Parse the XML capabilities file
        root = ET.fromstring(response.text)

        # Find all CoverageId elements
        namespace = {'wcs': 'http://www.opengis.net/wcs/2.0', 'ows': 'http://www.opengis.net/ows/2.0'}
        coverage_ids = root.findall(".//wcs:CoverageSummary/wcs:CoverageId", namespaces=namespace)

        # Find in all CoverageId elements the data type pattern
        for coverage_id in coverage_ids:
            # Match both the prefix and suffix
            if coverage_id.text.startswith(pattern_prefix) and coverage_id.text.endswith(pattern_suffix):
                # Get the run time
                run_time = datetime.strptime(coverage_id.text[len(pattern_prefix): -len(pattern_suffix)], "%Y-%m-%dT%H.%M.%SZ")
                # Check if this run time is more recent than the previous one
                if not latest_run_time or run_time > latest_run_time:
                    latest_run_time = run_time

        # Return the latest run time
        if not latest_run_time:
            return None
        else:
            return latest_run_time.strftime("%Y-%m-%dT%H.%M.%SZ")


    def download_run(self, data_type, run_time, output_dir):
        # Check if the requested data type is present in this model
        data_type_params = self.settings["data_types"].get(data_type)
        if (data_type_params == None):
            return None

        # Form the CoverageId field
        coverage_id = data_type_params["coverage_id"].format(run_time=run_time)

        # Calculate start and stop time from run_time and time_range
        start_time = datetime.strptime(run_time, "%Y-%m-%dT%H.%M.%SZ") + timedelta(hours=data_type_params["time_range"][0])
        stop_time = datetime.strptime(run_time, "%Y-%m-%dT%H.%M.%SZ") + timedelta(hours=data_type_params["time_range"][1])

        # Loop through all available subset times in the range
        current_time = start_time
        while current_time <= stop_time:
            subset_time = current_time.strftime("%Y-%m-%dT%H:%M:%SZ")

            # Construct the request URL to download coverage for each subset time
            url = self.settings["server"]+self.settings["coverage_path"]
            params = {
                "service": "WCS",
                "version": "2.0.1",
                "coverageid": coverage_id,
                "subset": f"time({subset_time})",
                "format": "application/wmo-grib"
            }
            headers = {
                "apikey": self.api_key
            }

            # Make the HTTP request and retry when time out
            while True:
                try:
                    response = requests.get(url, params=params, headers=headers, timeout=5)
                    response.raise_for_status()
                    break
                except requests.exceptions.Timeout:
                    time.sleep(2)
                except requests.exceptions.RequestException:
                    return None

            # Save the file to the output directory
            output_path = os.path.join(output_dir, f"{data_type}_{run_time}_{subset_time}.grib")
            os.makedirs(output_dir, exist_ok=True)
            
            with open(output_path, "wb") as f:
                f.write(response.content)
            
            print(f"File downloaded successfully: {output_path}")

            # Increment current time by 1h
            current_time += timedelta(hours=1)