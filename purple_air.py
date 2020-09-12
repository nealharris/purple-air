import os
from datetime import datetime
from urllib.request import Request, urlopen
import json
from enum import Enum
import boto3

PURPLE_AIR_URL_PREFIX = 'https://www.purpleair.com/json?show='

SENSOR_ID = os.environ['sensor_id']
BUCKET_NAME = os.environ['bucket_name']
FILENAME = os.environ['filename']
TOPIC_ARN = os.environ['topic_arn']
MIN_COLOR_NOTIF_THRESHOLD = int(os.environ['min_color_notif_threshold'])
COUNTER_STRATEGY = os.environ['counter'] # 'a' -> Counter 0, 'b' -> Counter 1, 'both' -> average of both
CONVERSION_METHOD = os.environ['conversion']
CORRECTION_FACTOR = os.environ['correction']

s3 = boto3.client('s3')
sns = boto3.client('sns')

class Color(Enum):
    green        = 1
    yellow       = 2
    orange       = 3
    red          = 4
    purple       = 5
    maroon       = 6
    hella_maroon = 7


# Source: https://aqicn.org/faq/2013-09-09/revised-pm25-aqi-breakpoints/
def current_color(pm_2_5_value):
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


def get_sensor_data():
    print("Attempting to open "+ PURPLE_AIR_URL_PREFIX + str(SENSOR_ID))
    return json.load(urlopen(PURPLE_AIR_URL_PREFIX + str(SENSOR_ID)))


def pm_2_5_average(data):
    # Correction factor is discussed at https://cfpub.epa.gov/si/si_public_file_download.cfm?p_download_id=540979&Lab=CEMM
    if CORRECTION_FACTOR == '1':
        pm_2_5_reading_a = data["results"][0]["pm2_5_cf_1"]
        pm_2_5_reading_b = data["results"][1]["pm2_5_cf_1"]
    else:
        pm_2_5_reading_a = data["results"][0]["pm2_5_atm"]
        pm_2_5_reading_b = data["results"][1]["pm2_5_atm"]

    humidity_reading_a = data["results"][0]["humidity"]
    humidity_reading_b = data["results"][1]["humidity"]

    if COUNTER_STRATEGY == "a":
        pm_2_5_reading = pm_2_5_reading_a
        humidity_reading = humidity_reading_a
    elif COUNTER_STRATEGY == "b":
        humidity_reading_a = humidity_reading_b
        pm_2_5_reading = pm_2_5_reading_b
    else:
        pm_2_5_reading = (pm_2_5_reading_a + pm_2_5_reading_b)/2.
        humidity_reading = (humidity_reading_a + humidity_reading_b)/2.

    # we only consider the lrapa conversion for now, though there are others.
    if CONVERSION_METHOD == "lrapa":
        # see https://www.lrapa.org/DocumentCenter/View/4147/PurpleAir-Correction-Summary
        return pm_2_5_reading * 0.5 - 0.66
    elif CONVERSION_METHOD == "epa":
        # see https://cfpub.epa.gov/si/si_public_file_download.cfm?p_download_id=540979&Lab=CEMM , slide 8
        return 0.52 * pm_2_5_reading - 0.085 * humidity_reading + 5.71
    else:
        return pm_2_5_reading

def get_last_color():
    response = s3.get_object(Bucket=BUCKET_NAME, Key=FILENAME)
    color_name = response['Body'].read().decode('utf-8').strip()
    return Color[color_name]


def update_color(color):
    s3.put_object(Bucket=BUCKET_NAME, Key=FILENAME, Body=color.name)


def notify_color_change(old_color, new_color):
    if old_color.value < new_color.value:
        print("degraded")
        message = "The air has degraded from " + old_color.name + " to " + new_color.name
    else:
        print("improved")
        message = "The air has improved from " + old_color.name + " to " + new_color.name
    print("About to send notification of change")
    sns.publish(TopicArn=TOPIC_ARN,Message=message)


def should_notify_color_change(old_color, new_color):
    return max(old_color.value, new_color.value) >= MIN_COLOR_NOTIF_THRESHOLD


def lambda_handler(event, context):
    print('Checking on sensor {} at {}...'.format(SENSOR_ID, event['time']))
    try:
        current_data = get_sensor_data()
        current_pm_2_5 = pm_2_5_average(current_data)

        print("current pm2.5 reading is: " +  str(current_pm_2_5))

        new_color = current_color(current_pm_2_5)
        last_color = get_last_color()

        if not new_color == last_color:
            print("new color!")
            update_color(new_color)
            if should_notify_color_change(last_color, new_color):
                print("sending color change notification")
                notify_color_change(last_color, new_color)
            else:
                print("change below notification threshold")
        else:
            print("no change in color (still " + new_color.name + ")")
    except:
        print('Check failed!')
        raise
    else:
        print('Check succeeded!')
        return event['time']
    finally:
        print('Check complete at {}'.format(str(datetime.now())))
