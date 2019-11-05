""" provides an class for uploading to the PVOutput API """

name = "pvoutput"

import requests
import re
from datetime import datetime, date, timedelta, time

from .parameters import *

# TODO: log? like, at all?


class DonationRequired(Exception):
    def __init__(self, message):
        # Call the base class constructor with the parameters it needs
        super().__init__(message)


class PVOutput(object):
    def __init__(
        self,
        apikey: str,
        systemid: int,
        donation_made: bool = False,
        stats_period: int = 5,
    ):
        """ interacts with the PVOutput API 
        apikey: str             API key (read or write)
        systemid: int           system ID
        donation_mode: bool     Whether to use the donation-required fields
        
        """
        if not isinstance(systemid, int):
            raise TypeError("systemid should be int")
        if not isinstance(apikey, str):
            raise TypeError("apikey should be str")
        self.apikey = apikey
        self.systemid = systemid
        self.donation_made = donation_made
        self.stats_period = stats_period

    def _headers(self):
        """ returns a base dict of headers for calls to the API 
        Documentation: https://pvoutput.org/help.html#api-spec
        """
        headers = {
            "X-Pvoutput-Apikey": self.apikey,
            "X-Pvoutput-SystemId": str(self.systemid),
        }
        return headers

    def _call(
        self, endpoint, data=None, params=None, headers=False, method=requests.post
    ):
        """ makes a call to a URL endpoint with the data/headers/method you require
        specify headers if you need to set additional ones, otherwise it'll use self._headers() which is the standard API key / systemid set (eg, self.check_rate_limit)
        specify a method if you want to use something other than requests.post
        """
        # always need the base headers
        if not headers:
            headers = self._headers()
        # TODO: type checking on call
        if method == requests.post and data and type(data) != dict:
            raise TypeError(f"data should be a dict, got {str(type(data))}")
        elif method == requests.get and params and type(params) != dict:
            raise TypeError(f"params should be a dict, got {str(type(params))}")
        if headers and type(headers) != dict:
            raise TypeError(f"headers should be a dict, got {str(type(headers))}")
        # TODO: learn if I can dynamically send thing, is that **args?
        if method == requests.get:
            response = method(endpoint, data=data, headers=headers, params=params)
        else:
            response = method(endpoint, data=data, headers=headers)

        if response.status_code == 200:
            return response
        elif response.status_code == 400:
            # TODO: work out how to get the specific response and provide useful answers
            raise ValueError(f"HTTP400: {response.text.strip()}")
        else:
            response.raise_for_status()
        # other possible errors
        # Method Not Allowed 405: POST or GET only 	 - if we get that, wtf?
        # Data must be sent via the HTTP POST or GET method

        # Unauthorized 401: Invalid System ID
        # # The required parameter X-Pvoutput-SystemId or sid is missing from the request. The sid is a number which identifies a system. The sid can be obtained from the Settings page under Registered Systems.

        # Unauthorized 401: Invalid API Key
        # The API key is missing in the header request or the API key is invalid.

        # Unauthorized 401: Disabled API Key
        # The API key has not been enabled in the Settings.

        # Forbidden 403: Read only key
        # The API key provided is a read only key and cannot access the requested service which updates system data, use the standard key to update system data.

        # Unauthorized 401: Missing, invalid or inactive api key information (X-Pvoutput-Apikey)
        # The sid and key combination is invalid

        # Forbidden 403: Exceeded number requests per hour
        # The maximum number of requests per hour has been reached for the API key. Wait till the next hour before making further requests.

        # Forbidden 403: Donation Mode
        # Request is only available in donation mode.

    def check_rate_limit(self):
        headers = self._headers()
        headers["X-Rate-Limit"] = "1"
        url = "https://pvoutput.org/service/r2/getstatus.jsp"
        response = self._call(url, {}, headers=headers)
        retval = {}
        for key in response.headers.keys():
            if key.startswith("X-Rate-Limit"):
                retval[key] = response.headers[key]
        return retval

    def addstatus(self, data: dict):
        """ The Add Status service accepts live output data at the status interval (5 to 15 minutes) configured for the system.
        API Spec: https://pvoutput.org/help.html#api-addstatus
        """
        if not data.get("d", False):
            # if you don't set a date, make it now
            data["d"] = date.today().strftime("%Y%m%d")
        if not data.get("t", False):
            # if you don't set a time, set it to now
            hour = int(datetime.now().strftime("%H"))
            minute = int(
                self.stats_period
                * round(int(datetime.now().strftime("%M")) / self.stats_period)
            )
            data["t"] = time(hour=hour, minute=minute).strftime("%H:%M")
        self.validate_data(data, ADDSTATUS_PARAMETERS)

        return self._call(
            endpoint="https://pvoutput.org/service/r2/addstatus.jsp", data=data
        )

    def addoutput(self, data: dict):
        """ The Add Output service uploads end of day output information. It allows all of the information provided on the Add Output page to be uploaded. 
        API Spec: https://pvoutput.org/help.html#api-addoutput """
        return NotImplementedError("Haven't Implemented pvoutput.addoutput() yet.")
        # self.validate_data(data, ADDOUTPUT_PARAMETERS)
        # self._call(endpoint="https://pvoutput.org/service/r2/addoutput.jsp", data=data)

    def delete_status(self, date_val: datetime.date, time_val=None):
        """ deletes a given status, based on the provided parameters 
            needs a datetime() object
            set the hours/minutes to non-zero to delete a specific time

            returns a requests.post response object
        """
        if not isinstance(date_val, date):
            raise ValueError(
                f"date_val should be of type datetime.datetime, not {type(date_val)}"
            )
        if time_val and not isinstance(time_val, time):
            raise ValueError(
                f"time_val should be of time datetime.time, not {type(time_val)}"
            )
        yesterday = date.today() - timedelta(1)
        tomorrow = date.today() + timedelta(1)
        # you can't delete back past yesterday
        if date_val < yesterday:
            raise ValueError(
                f"date_val can only be yesterday or today, you provided {date_val}"
            )
        # you can't delete forward of today
        if date_val >= tomorrow:
            raise ValueError(
                f"date_val can only be yesterday or today, you provided {date_val}"
            )
        data = {"d": date_val.strftime("%Y%m%d")}
        if time_val:
            data["t"] = time_val.strftime("%H:%M")
        response = self._call(
            endpoint="https://pvoutput.org/service/r2/deletestatus.jsp", data=data
        )
        return response

    def getstatus(self):
        """ returns a dict of the last updated data 
        TODO: extend this, you can do history searches and all sorts with this endpoint
        """
        url = "https://pvoutput.org/service/r2/getstatus.jsp"
        data = {}
        if self.donation_made:
            url = f"{url}?ext=1&sid={self.systemid}"
        response = self._call(endpoint=url, data=data, method=requests.get)
        response.raise_for_status()
        # grab all the things
        d, t, v1, v2, v3, v4, v5, v6, normalised_output, *extras = response.text.split(
            ","
        )

        # if there's no data, you get "NaN". Here we change that to NoneType
        responsedata = {
            "d": d,
            "t": t,
            "timestamp": datetime.strptime(f"{d} {t}", "%Y%m%d %H:%M"),
            "v1": None if v1 == "NaN" else float(v1),
            "v2": None if v2 == "NaN" else float(v2),
            "v3": None if v3 == "NaN" else float(v3),
            "v4": None if v4 == "NaN" else float(v4),
            "v5": None if v5 == "NaN" else float(v5),
            "v6": None if v6 == "NaN" else float(v6),
            "normalised_output": float(normalised_output),
        }
        # if we're fancy, we get more data
        if extras:
            for i in range(1, 7):
                responsedata[f"v{i+6}"] = (
                    None if extras[i - 1] == "NaN" else float(extras[i - 1])
                )
        return responsedata

    def register_notification(self, appid: str, url: str, alerttype: int):
        """
        The Register Notification Service allows a third party application to receive PVOutput alert callbacks via a HTTP end point.
        TODO: Find out if HTTPS is supported

        All parameters are mandatory
        Parameter       Field                   Max Length  Variable Type           Example
        appid           Application ID          100         str                     example.app.id
        url             Callback URL            150         str                     http://example.com/api/
        type            Alert Type              n           int                     See list below

        https://pvoutput.org/help.html#api-registernotification

        type list:
        0 All Notifications
        1 Private Message
        3 Joined Team
        4 Added Favourite
        5 High Consumption Alert 6 System Idle Alert
        8 Low Generation Alert
        11 Performance Alert
        14 Standby Cost Alert
        15 Extended Data V7 Alert 
        16 Extended Data V8 Alert 
        17 Extended Data V9 Alert 
        18 Extended Data V10 Alert 
        19 Extended Data V11 Alert 
        20 Extended Data V12 Alert 
        23 High Net Power Alert
        24 Low Net Power Alert
        """
        # TODO: validation of types, is this the best way?
        # validation of inputs
        if type(appid) != str:
            raise TypeError(f"appid needs to be a string, got: {str(type(appid))}")
        if type(url) != str:
            raise TypeError(f"url needs to be a string, got: {str(type(url))}")
        if len(url) > 150:
            raise ValueError(
                f"Length of url can't be longer than 150 chars - was {len(url)}"
            )
        if len(appid) > 100:
            raise ValueError(
                f"Length of appid can't be longer than 150 chars - was {len(appid)}"
            )

        if type(alerttype) != int:
            raise TypeError(
                f"alerttype needs to be an int, got: {str(type(alerttype))}"
            )
        # TODO: urlencode the callback URL

        call_url = f"https://pvoutput.org/service/r2/registernotification.jsp?appid={appid}&type={alerttype}&url={url}"
        response = self._call(endpoint=call_url, method=requests.get)
        return response

    def validate_data(self, data, apiset):
        """ does a super-simple validation based on the api def raises errors if it's wrong, returns True if it's OK
            WARNING: will only raise an error on the first error it finds
            eg: pvoutput.PVOutput.validate_data(data, pvoutput.ADDSTATUS_PARAMETERS)
        """
        # if you set a 'required_oneof' key in apiset, validation will require at least one of those keys to be set
        if "required_oneof" in apiset.keys() and (
            len(
                [
                    key
                    for key in data.keys()
                    if key in apiset["required_oneof"]["keys"]
                ]
            )
            == 0
            ): raise ValueError(f"one of {','.join(apiset['required_oneof']['keys'])} MUST be set")
        for key in apiset:
            # check that that required values are set
            if apiset[key].get("required", False) and key not in data.keys():
                raise ValueError(f"key {key} required in data")
        # check there's no extras
        for key in data.keys():
            if key not in apiset.keys():
                raise ValueError(f"key {key} isn't valid in the API spec")
            if apiset[key].get("type", False) and not isinstance(data[key], apiset[key]["type"]):
                raise TypeError(
                    f"data[{key}] type ({type(data[key])} is invalid - should be {str(type(apiset[key]['type']))})"
                )
        # TODO: check format, 'format' should be a regex
        for format_string in [apiset[key].get("format") for key in apiset.keys()]:
            print(format_string)

        # TODO: 'd' can't be more than 14 days ago, if a donator, goes out to 90
        # check if donation_mode == True and age of thing
        # if self.donation_made:
        #     # check if more than 90 days ago
        # else:
        #     # check if more than 14 days ago

        # check for donation-only keys
        if not self.donation_made:
            donation_required_keys = [
                key
                for key in data.keys()
                if apiset[key].get("donation_required", False)
            ]
            for key in data.keys():
                if key in donation_required_keys:
                    raise DonationRequired(
                        f"key {key} requires an account which has donated"
                    )
        if int(data.get("v3", 0)) > 200000:
            raise ValueError(f"v3 cannot be higher than 200000, is {data['v3']}")
        if int(data.get("v4", 0)) > 100000:
            raise ValueError(f"v4 cannot be higher than 100000, is {data['v4']}")

        return True
