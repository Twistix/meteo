# ================================ Imports =====================================
import sys
import os
import argparse
import shutil
from datetime import datetime, timedelta
import math
import eccodes
import numpy as np
import matplotlib as mpl
from PIL import Image
import gc
import json
import subprocess


# ================================ Constants =====================================


# ============================= Useful functions =============================
def time_format_iso8601(time):
    return "{:04d}".format(time.year)+"-"+"{:02d}".format(time.month)+"-"+"{:02d}".format(time.day)+"T"+"{:02d}".format(time.hour)+":00:00Z"


# =============================== Functions =======================================
def parse_inputs(available_data_types):
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--mlat", type=float, help="Minimum latitude (in deg)")
    parser.add_argument("--Mlat", type=float, help="Maximum latitude (in deg)")
    parser.add_argument("--mlon", type=float, help="Minimum longitude (in deg)")
    parser.add_argument("--Mlon", type=float, help="Maximum longitude (in deg)")
    parser.add_argument('-p', "--projection", type=str, default="EPSG:4326", help="Projection code")
    parser.add_argument('-d', "--data_types", type=str, default=available_data_types, nargs='+', choices=available_data_types, help="Metrics wanted")

    return parser.parse_args()


def create_image(min_lat, max_lat, min_lon, max_lon, data_type, current_time, data_type_info):
    #Process grib file
    print("Processing grib file for "+str(data_type)+" at hour H+"+"{:02d}".format(i))
    f = open("raw_data/"+str(data_type)+"/grib_"+str(data_type)+"_"+time_format_iso8601(current_time)+".grib2", "rb")
    gid = eccodes.codes_grib_new_from_file(f)
    Ni = eccodes.codes_get(gid, "Ni")   #Number of points allong a parallel or x axis
    Nj = eccodes.codes_get(gid, "Nj")   #Number of points allong a meridian or y axis
    values = eccodes.codes_get_array(gid, "values", float)
    lats = eccodes.codes_get_array(gid, "latitudes", float)
    lons = eccodes.codes_get_array(gid, "longitudes", float)
    grib_min_lat = np.min(lats)
    grib_max_lat = np.max(lats)
    grib_min_lon = np.min(lons)
    grib_max_lon = np.max(lons)
    values = np.reshape(values, (Nj, Ni))
    lats = np.reshape(lats, (Nj, Ni))
    lons = np.reshape(lons, (Nj, Ni))
    eccodes.codes_release(gid)
    f.close()

    #Crop numpy array to the region selected by user
    min_x_index = int(Ni * ((min_lon - grib_min_lon) / (grib_max_lon - grib_min_lon)))
    max_x_index = math.ceil(Ni * ((max_lon - grib_min_lon) / (grib_max_lon - grib_min_lon)))
    min_y_index = int(Nj * ((min_lat - grib_min_lat) / (grib_max_lat - grib_min_lat)))
    max_y_index = math.ceil(Nj * ((max_lat - grib_min_lat) / (grib_max_lat - grib_min_lat)))
    values = values[Nj-max_y_index:Nj-min_y_index,min_x_index:max_x_index]
    lats = lats[Nj-max_y_index:Nj-min_y_index,min_x_index:max_x_index]
    lons = lons[Nj-max_y_index:Nj-min_y_index,min_x_index:max_x_index]

    #Filter missing values
    values[values>9998] = 0

    #Apply data_type operation
    values = eval("values"+data_type_info["operation"])

    #Filter transparent values
    values = np.ma.masked_array(values, eval("values"+data_type_info["filter"]))

    #Nomalize values
    min_val = float(data_type_info["range_min"])
    max_val = float(data_type_info["range_max"])
    values = (values - min_val) / (max_val - min_val)

    #Create image
    cmap = mpl.colormaps[data_type_info["cmap"]]
    im = Image.fromarray(np.uint8(cmap(values)*255))

    return im


if __name__ == "__main__":
    # Opening Model Settings JSON file
    f = open("model_settings.json")
    json_data = json.load(f)
    # Closing file
    f.close()

    #Get modele informations
    modele_info = json_data["modeles"]["arome"]

    #Find available data types
    available_data_types = []
    for data_type in modele_info["data_types"]:
        available_data_types.append(data_type)

    #Parse user inputs
    args = parse_inputs(available_data_types)
    mlat = args.mlat
    Mlat = args.Mlat
    mlon = args.mlon
    Mlon = args.Mlon
    projection = args.projection
    data_types = args.data_types

    for data_type in data_types:
        #Initializing directory
        current_dir = os.getcwd()
        path = current_dir+"/weather_outputs/"+str(data_type)
        if os.path.exists(path):
            shutil.rmtree(path)
        os.makedirs(path)

        #Init properties
        image_properties = {}

        #Get current time from where we generate 24h outputs
        current_time = datetime.now()

        for i in range(0, 24):
            image = create_image(mlat, Mlat, mlon, Mlon, data_type, current_time, modele_info["data_types"][data_type])

            #Save image before conversion
            image.save("weather_outputs/"+str(data_type)+"/tmp.png")

            #Add ground control points (GCP) to image corners
            subprocess.run(["gdal_translate",
                            "-gcp", str(0), str(0), str(mlon), str(Mlat),                           #Top left
                            "-gcp", str(image.size[0]), str(0), str(Mlon), str(Mlat),               #Top right
                            "-gcp", str(0), str(image.size[1]), str(mlon), str(mlat),               #Bottom left
                            "-gcp", str(image.size[0]), str(image.size[1]), str(Mlon), str(mlat),   #Bottom right
                            "-q",
                            "weather_outputs/"+str(data_type)+"/tmp.png",
                            "weather_outputs/"+str(data_type)+"/intermediate.png"])
            
            #Change image projection and save output
            subprocess.run(["gdalwarp",
                            "-s_srs", modele_info["projection"],
                            "-t_srs", projection,
                            "-q",
                            "-nomd",
                            "weather_outputs/"+str(data_type)+"/intermediate.png",
                            "weather_outputs/"+str(data_type)+"/image_"+str(i)+".png"])

            #Update properties
            image_properties["image_"+str(i)+".png"] = {
                "time" : time_format_iso8601(current_time),
                "projection" : projection
            }

            #Increment current time
            current_time = current_time + timedelta(hours=1)

        #Write properties to file
        f = open("weather_outputs/"+str(data_type)+"/image_properties.json", "w", encoding="utf-8")
        json.dump(image_properties, f, ensure_ascii=False, indent=4)
        f.close()

        #Collect garbage
        gc.collect()