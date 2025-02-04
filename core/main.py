from downloaders.arome001_downloader import arome001_downloader

# Create AROME001 downloader
downloader = arome001_downloader("settings/model_settings.json", "settings/user_settings.json")

# Use downloader
print(f"Status: "+downloader.get_status())

print(f"Available data types : "+str(downloader.get_available_datas()))

latest_run_time = downloader.get_last_run("rain")
print(f"Last run time for rain : "+str(latest_run_time))

downloader.download_run("rain", latest_run_time, "grib_files")