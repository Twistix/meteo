from utils.settings_manager import SettingsManager
from downloaders.arome_downloader import AromeDownloader

# Initialize SettingsManager
settings_manager = SettingsManager(
    model_settings_path="settings/model_settings.json",
    user_settings_path="settings/user_settings.json"
)

# Load settings
model_settings = settings_manager.get_model_settings()
user_settings = settings_manager.get_user_settings()

# Create AROME downloader for 0.01 resolution
downloader = AromeDownloader(model_settings, user_settings, resolution="0.01")

# Get latest run for rain data
latest_run = downloader.get_latest_run(data_type="rain")
print(f"Latest run for rain: {latest_run}")

# Download all available data for the latest run
downloader.download_last_run(data_type="rain", reference_time=latest_run, output_dir="./grib_files")