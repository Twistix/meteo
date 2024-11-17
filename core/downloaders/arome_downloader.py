import os
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

class AromeDownloader:
    def __init__(self, model_settings, user_settings, resolution):
        """
        Initialize the downloader with model-specific settings for a given resolution.
        :param model_settings: Dict containing AROME model settings.
        :param user_settings: Dict containing user-specific settings.
        :param resolution: Resolution to use (e.g., "0.01" or "0.025").
        """
        self.settings = model_settings["AROME"][resolution]
        self.api_key = user_settings["api_keys"].get("AROME")
        self.resolution = resolution

    def get_latest_run(self, data_type):
        """
        Fetch the most recent reference time for the specified data type.
        :param data_type: The user-friendly data type (e.g., "rain").
        :return: The most recent timestamp as a string.
        """
        # Map data type to API's coverage name
        api_data_type_pattern = self.settings["data_type_mapping"].get(data_type)
        if not api_data_type_pattern:
            raise ValueError(f"Unsupported data type '{data_type}' for AROME {self.resolution}")

        # Split the pattern into prefix and suffix for better matching
        pattern_prefix, pattern_suffix = api_data_type_pattern.split("{reference_time}")

        # Step 1: Construct the GetCapabilities request URL
        url = f"{self.settings['base_url']}/wcs/MF-NWP-HIGHRES-AROME-001-FRANCE-WCS/GetCapabilities"
        params = {
            "service": "WCS",
            "version": "2.0.1",
            "language": "eng"
        }
        headers = {"apikey": str(self.api_key)} if self.api_key else {}

        # Step 2: Make the HTTP request
        try:
            response = requests.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
        except requests.exceptions.Timeout:
            raise Exception(f"Request to {url} timed out.")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to download WCS file: {e}")

        # Step 3: Parse XML content
        root = ET.fromstring(response.content)
        namespace = {
            "wcs": "http://www.opengis.net/wcs/2.0",
            "ows": "http://www.opengis.net/ows/2.0",
        }
        coverage_summaries = root.findall(".//wcs:CoverageSummary", namespace)

        # Step 4: Extract CoverageIds for the given data_type
        latest_time = None

        for summary in coverage_summaries:
            coverage_id = summary.find("wcs:CoverageId", namespace).text

            # Match both the prefix and suffix
            if coverage_id.startswith(pattern_prefix) and coverage_id.endswith(pattern_suffix):
                reference_time = coverage_id[len(pattern_prefix): -len(pattern_suffix)]
                if not latest_time or reference_time > latest_time:
                    latest_time = reference_time

        if not latest_time:
            raise Exception(f"Could not find latest reference time for data type '{data_type}'.")

        return latest_time

    def get_coverage_time_range(self, coverage_id):
        """
        Fetch the time range available for a given coverage ID.
        :param coverage_id: The coverage ID (e.g., "TOTAL_PRECIPITATION__GROUND_OR_WATER_SURFACE___2024-11-17T15.00.00Z_PT1H").
        :param timeout: Timeout for the HTTP request.
        :return: A tuple containing the start and stop times as strings in ISO8601 format.
        """
        # Step 1: Construct the DescribeCoverage request URL
        url = f"{self.settings['base_url']}/wcs/MF-NWP-HIGHRES-AROME-001-FRANCE-WCS/DescribeCoverage"
        params = {
            "service": "WCS",
            "version": "2.0.1",
            "coverageID": coverage_id
        }
        headers = {"apikey": str(self.api_key)} if self.api_key else {}

        # Step 2: Make the HTTP request
        try:
            response = requests.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
        except requests.exceptions.Timeout:
            raise Exception(f"Request to {url} timed out.")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to fetch coverage description: {e}")

        # Step 3: Parse the XML response
        root = ET.fromstring(response.content)
        namespace = {
            "gml": "http://www.opengis.net/gml/3.2",
        }
        envelope = root.find(".//gml:EnvelopeWithTimePeriod", namespace)
        if not envelope:
            raise Exception(f"Could not find time period information in the coverage description.")

        begin_position = envelope.find("gml:beginPosition", namespace).text
        end_position = envelope.find("gml:endPosition", namespace).text

        return begin_position, end_position

    def download_last_run(self, data_type, reference_time, output_dir):
        """
        Download all available data for the latest run of the specified data type.
        :param data_type: User-friendly data type (e.g., "rain").
        :param reference_time: Reference time in ISO8601 format (e.g., "2024-11-17T15:00:00Z").
        :param output_dir: Directory where the GRIB files will be saved.
        :param timeout: Timeout for the HTTP request.
        """
        # Step 1: Map the data type to the API's coverage name
        api_data_type_pattern = self.settings["data_type_mapping"].get(data_type)
        if not api_data_type_pattern:
            raise ValueError(f"Unsupported data type '{data_type}' for AROME {self.resolution}")

        coverage_id = api_data_type_pattern.format(reference_time=reference_time)

        # Step 2: Fetch the valid time range for the coverage
        start_time, stop_time = self.get_coverage_time_range(coverage_id)
        start_datetime = datetime.strptime(start_time, "%Y-%m-%dT%H:%M:%SZ")
        stop_datetime = datetime.strptime(stop_time, "%Y-%m-%dT%H:%M:%SZ")

        # Step 3: Loop through all available subset times in the range
        current_time = start_datetime
        while current_time <= stop_datetime:
            subset_time = current_time.strftime("%Y-%m-%dT%H:%M:%SZ")
            
            # Step 4: Construct the request URL for each subset time
            url = f"{self.settings['base_url']}/wcs/MF-NWP-HIGHRES-AROME-001-FRANCE-WCS/GetCoverage"
            params = {
                "service": "WCS",
                "version": "2.0.1",
                "coverageid": coverage_id,
                "subset": f"time({subset_time})",
                "format": "application/wmo-grib",
            }
            headers = {"apikey": str(self.api_key)} if self.api_key else {}

            # Step 5: Make the HTTP request for the current subset time
            try:
                response = requests.get(url, params=params, headers=headers, timeout=10)
                response.raise_for_status()  # Raise an exception for HTTP errors
            except requests.exceptions.Timeout:
                raise Exception(f"Request to {url} timed out.")
            except requests.exceptions.RequestException as e:
                raise Exception(f"Failed to download GRIB file for {subset_time}: {e}")

            # Step 6: Save the file to the output directory
            output_path = os.path.join(output_dir, f"{data_type}_{reference_time}_{subset_time}.grib")
            os.makedirs(output_dir, exist_ok=True)
            
            with open(output_path, "wb") as f:
                f.write(response.content)
            
            print(f"File downloaded successfully: {output_path}")

            # Move to the next time step (e.g., 1 hour later for hourly data)
            current_time += timedelta(hours=1)  # Adjust based on your data type (e.g., hourly)