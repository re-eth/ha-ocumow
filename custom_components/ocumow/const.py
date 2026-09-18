"""Constants for the OcuMow integration."""

from datetime import timedelta

DOMAIN = "ocumow"
PLATFORMS = ["lawn_mower", "sensor"]

CONF_DEVICE_ID = "device_id"
CONF_DEVICE_NAME = "device_name"

DEFAULT_API_BASE_URL = "https://api.clevarobot.com/v2"
DEFAULT_DEVICE_NAME = "OcuMow"
DEFAULT_SCAN_INTERVAL = timedelta(seconds=30)

API_LOGIN_PATH = "/enduser/app/user/emailPwdLogin"
API_REFRESH_PATH = "/enduser/app/user/refreshToken"
API_DEVICE_INFO_PATH = "/enduser/deviceInfo"

SENSITIVE_KEYS = {
    "Access-Token",
    "Authorization",
    "PinCode",
    "accessToken",
    "accesstoken",
    "access_token",
    "authorization",
    "password",
    "pincode",
    "pin",
    "refreshToken",
    "refreshtoken",
    "refresh_token",
    "secret",
    "token",
}
