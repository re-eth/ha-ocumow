"""Constants for the OcuMow integration."""

from datetime import timedelta

DOMAIN = "ocumow"
PLATFORMS = ["binary_sensor", "button", "lawn_mower", "sensor", "switch"]

CONF_DEVICE_ID = "device_id"
CONF_DEVICE_NAME = "device_name"

DEFAULT_API_BASE_URL = "https://api.clevarobot.com/v2"
DEFAULT_WEBSOCKET_URL = "wss://iot-ws.quecteleu.com/ws/v1"
DEFAULT_DEVICE_NAME = "OcuMow"
DEFAULT_SCAN_INTERVAL = timedelta(minutes=1)

API_LOGIN_PATH = "/enduser/app/user/emailPwdLogin"
API_REFRESH_PATH = "/enduser/app/user/refreshToken"
API_DEVICE_LIST_PATH = "/device/enduser/device/listPage"
API_DEVICE_INFO_PATH = "/device/enduser/deviceInfo"
API_DEVICE_PROPERTIES_PATH = "/device/enduser/device/part/properties"
API_SUB_DEVICE_LIST_PATH = "/device/enduser/sub/gateway/device/listPage"

DEVICE_STATISTIC_PROPERTIES = (
    "Schedule",
    "RainSet",
    "WorkingTime",
    "RunningTime",
    "BladeTime",
    "Distance",
    "TraveledDistance",
    "MainBoardTemp",
    "BatteryTemp",
    "DeviceStoped",
    "AllFirmwareVer",
)

DEVICE_LIVE_PROPERTIES = (
    "PinCode",
    "Soc",
    "Status",
    "Area",
    "SignalQuality",
    "Fault",
    "ConnectStationStates",
    "BatteryStates",
    "Mode",
)

COMMAND_PAUSE = "0"
COMMAND_START = "1"
COMMAND_DOCK = "2"
RESET_DATA_MESSAGE_ID = 1001
SCHEDULE_MODE_MESSAGE_ID = 1000

COMMAND_MESSAGE_IDS = {
    COMMAND_PAUSE: 1012,
    COMMAND_START: 1013,
    COMMAND_DOCK: 1014,
}

# Values applied by OcuMow Android 1.3.15 after selecting Europe and used to
# sign email logins. The app currently applies this same pair to both entries
# in its region selector.
API_USER_DOMAIN = "E.DM.4294968778.2"
API_USER_DOMAIN_SECRET = "4VEMeZKzqMdvbea6DVgytQtvSLZyB9QkGPva3qSWv8vr"

SENSITIVE_KEYS = {
    "Access-Token",
    "Authorization",
    "PinCode",
    "accessToken",
    "accesstoken",
    "access_token",
    "authorization",
    "authCode",
    "authKey",
    "deviceKey",
    "email",
    "password",
    "pincode",
    "pin",
    "refreshToken",
    "refreshtoken",
    "refresh_token",
    "secret",
    "token",
}
