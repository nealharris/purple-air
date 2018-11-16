import json
from urllib.request import urlopen
from enum import Enum
import sys

PURPLE_AIR_URL_PREFIX = 'https://www.purpleair.com/json?show='

class Color(Enum):
    green        = 1
    yellow       = 2
    orange       = 3
    red          = 4
    purple       = 5
    maroon       = 6
    hella_maroon = 7

def pm_2_5_average(sensor_idi):
    data = json.load(urlopen(PURPLE_AIR_URL_PREFIX + str(sensor_id)))
    
    stats0 = json.loads(data["results"][0]["Stats"])
    stats1 = json.loads(data["results"][1]["Stats"])

    return (stats0["v"] + stats1["v"])/2.

# Source: https://aqicn.org/faq/2013-09-09/revised-pm25-aqi-breakpoints/
def aqi_category(pm_2_5_value):
    if pm_2_5_value <= 12.0:
        return Color.green
    elif pm_2_5_value <= 35.4:
        return Color.yellow
    elif pm_2_5_value <= 55.4:
        return Color.orange
    elif pm_2_5_value <= 150.4:
        return Color.red
    elif pm_2_5_value <= 250.4:
        return Color.purple
    elif pm_2_5_value <= 350.4:
        return Color.maroon
    else:
        return Color.hella_maroon #shit


if __name__ == "__main__":
    sensor_id = sys.argv[1]
    pm25 = pm_2_5_average(sensor_id)
    category = aqi_category(pm25)
    print(category.name)
