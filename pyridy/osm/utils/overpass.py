from typing import List, Union

from overpy import Overpass as OverpyOverpass, Result
import overpy.exception as exception

import requests
import time


class Overpass(OverpyOverpass):
    """
    Extend overpy.Overpass to use requests. This allows to use requests-cache for caching.
    Based on https://github.com/DinoTools/python-overpy/blob/5343e743e87c117531f1e321a424911ff4cee8cf/overpy/__init__.py (April 2021)
    """
    def __init__(self, *args, session: requests.Session = None, **kwargs):
        """
        Initialise an overpy.Overpass instance and a session
        """
        super().__init__(*args, **kwargs)
        if session is None:
            session = requests.Session()
        self.session = session
    
    def request(self, query: Union[bytes, str]) -> "Result":
        retry_num: int = 0
        retry_exceptions: List[exception.OverPyException] = []
        do_retry: bool = True if self.max_retry_count > 0 else False
        while retry_num <= self.max_retry_count:
            if retry_num > 0:
                time.sleep(self.retry_timeout)
            retry_num += 1
            try:
                r = self.session.get(self.url, data=query)
            except requests.exceptions.RequestException as e:
                current_exception = e
                if not do_retry:
                    raise current_exception
                retry_exceptions.append(current_exception)
                continue

            current_exception: exception.OverPyException
            if r.status_code == 200:
                content_type = r.headers['content-type']

                if content_type in ["application/json", "application/osm3s+xml"]:
                    return content_type, r.text

                current_exception = exception.OverpassUnknownContentType(content_type)
                if not do_retry:
                    raise current_exception
                retry_exceptions.append(current_exception)
                continue

            if r.status_code == 400:
                msgs: List[str] = []
                for msg_raw in self._regex_extract_error_msg.finditer(r.content):
                    msg_clean_bytes = self._regex_remove_tag.sub(b"", msg_raw.group("msg"))
                    try:
                        msg = msg_clean_bytes.decode("utf-8")
                    except UnicodeDecodeError:
                        msg = repr(msg_clean_bytes)
                    msgs.append(msg)

                current_exception = exception.OverpassBadRequest(
                    query,
                    msgs=msgs
                )
                if not do_retry:
                    raise current_exception
                retry_exceptions.append(current_exception)
                continue

            if r.status_code == 429:
                current_exception = exception.OverpassTooManyRequests()
                if not do_retry:
                    raise current_exception
                retry_exceptions.append(current_exception)
                continue

            if r.status_code == 504:
                current_exception = exception.OverpassGatewayTimeout()
                if not do_retry:
                    raise current_exception
                retry_exceptions.append(current_exception)
                continue

            current_exception = exception.OverpassUnknownHTTPStatusCode(r.status_code)
            if not do_retry:
                raise current_exception
            retry_exceptions.append(current_exception)
            continue

        raise exception.MaxRetriesReached(retry_count=retry_num, exceptions=retry_exceptions)

    def parse_response(self, content_type: str, response):
        if content_type == "application/json":
            return self.parse_json(response)

        if content_type == "application/osm3s+xml":
            return self.parse_xml(response)

        raise exception.OverpassUnknownContentType(content_type)

    def query(self, query: Union[bytes, str]) -> "Result":
        """
        Query the Overpass API
        :param query: The query string in Overpass QL
        :return: The parsed result
        """
        content_type, response = self.request(query)
        return self.parse_response(content_type, response)

