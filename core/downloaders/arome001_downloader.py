import os
import shutil
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


    def _get_run_time_range(self, coverage_id):
        # Construct the request URL to download coverage description XML file
        url = self.settings["server"]+self.settings["describe_coverage_path"]
        params = {
            "service": "WCS",
            "version": "2.0.1",
            "coverageID": coverage_id
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

        # Parse the XML coverage description file
        root = ET.fromstring(response.text)

        # Find EnvelopeWithTimePeriod element
        namespace = {"gml": "http://www.opengis.net/gml/3.2"}
        start_time = root.find(".//gml:EnvelopeWithTimePeriod/gml:beginPosition", namespaces=namespace).text
        end_time = root.find(".//gml:EnvelopeWithTimePeriod/gml:endPosition", namespaces=namespace).text

        return start_time,end_time


    def get_status(self):
        # Try a request to the API to see if its working
        url = self.settings["server"]+self.settings["get_capabilities_path"]
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
        url = self.settings["server"]+self.settings["get_capabilities_path"]
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

        # Clear output directory
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir)
        os.makedirs(output_dir)

        # Form the CoverageId field
        coverage_id = data_type_params["coverage_id"].format(run_time=run_time)

        # Retreive start and end time for this coverage
        start_time_str,end_time_str = self._get_run_time_range(coverage_id)
        start_time = datetime.strptime(start_time_str, "%Y-%m-%dT%H:%M:%SZ")
        end_time = datetime.strptime(end_time_str, "%Y-%m-%dT%H:%M:%SZ")

        # Loop through all available subset times in the range
        current_time = start_time
        while current_time <= end_time:
            current_time_str = current_time.strftime("%Y-%m-%dT%H:%M:%SZ")

            # Construct the request URL to download coverage for each subset time
            url = self.settings["server"]+self.settings["get_coverage_path"]
            params = {
                "service": "WCS",
                "version": "2.0.1",
                "coverageid": coverage_id,
                "subset": f"time({current_time_str})",
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
            output_path = os.path.join(output_dir, f"{data_type}_{current_time_str}.grib")
            
            with open(output_path, "wb") as f:
                f.write(response.content)
            
            print(f"File downloaded successfully: {output_path}")

            # Increment current time by 1h
            current_time += timedelta(hours=1)
        
        # Save run_info.json in the output directory
        run_info = {
            "run_time": run_time,
            "start_time": start_time_str,
            "end_time": end_time_str
        }
        run_info_path = os.path.join(output_dir, "run_info.json")

        with open(run_info_path, "w") as f:
            json.dump(run_info, f, indent=4)

        print(f"Run info saved: {run_info_path}")