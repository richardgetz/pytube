# -*- coding: utf-8 -*-
"""Module for interacting with a user's youtube channel."""
import json
import logging
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from pytube import Playlist, extract, request
from pytube.helpers import uniqueify
from pytube.innertube import InnerTube

logger = logging.getLogger(__name__)


class Channel(Playlist):
    def __init__(
        self,
        url: str,
        proxies: Optional[Dict[str, str]] = None,
        use_oauth: bool = False,
        allow_oauth_cache: bool = True,
        innertube=None,
    ):
        """Construct a :class:`Channel <Channel>`.

        :param str url:
            A valid YouTube channel URL.
        :param proxies:
            (Optional) A dictionary of proxies to use for web requests.
        """
        super().__init__(url, proxies)

        self.channel_uri = extract.channel_name(url)

        self.channel_url = f"https://www.youtube.com{self.channel_uri}"

        self.videos_url = self.channel_url + "/videos"
        self.playlists_url = self.channel_url + "/playlists"
        self.community_url = self.channel_url + "/community"
        self.featured_channels_url = self.channel_url + "/channels"
        self.about_url = self.channel_url + "/about"
        self.shorts_url = self.channel_url + "/shorts"

        # Possible future additions
        self._playlists_html = None
        self._community_html = None
        self._featured_channels_html = None
        self._about_html = None
        self._subscriber_count = None
        self._shorts_html = None

        self._about_json = None
        self._videos_json = None
        self._shorts_json = None
        self._about_metadata_json = None
        self.use_oauth = use_oauth
        self.allow_oauth_cache = allow_oauth_cache
        self.innertube = innertube

    @property
    def channel_name(self):
        """Get the name of the YouTube channel.

        :rtype: str
        """
        return self.initial_data["metadata"]["channelMetadataRenderer"]["title"]

    @property
    def channel_id(self):
        """Get the ID of the YouTube channel.

        This will return the underlying ID, not the vanity URL.

        :rtype: str
        """
        return self.initial_data["metadata"]["channelMetadataRenderer"]["externalId"]

    @property
    def vanity_url(self):
        """Get the vanity URL of the YouTube channel.

        Returns None if it doesn't exist.

        :rtype: str
        """
        return self.initial_data["metadata"]["channelMetadataRenderer"].get(
            "vanityChannelUrl", None
        )  # noqa:E501

    @property
    def about_metadata_json(self):
        """Get the json for the /about page.

        :rtype: str
        """
        if self._about_metadata_json:
            return self._about_metadata_json
        else:
            if self.about_json.get("onResponseReceivedEndpoints"):
                try:
                    self._about_metadata_json = self.about_json[
                        "onResponseReceivedEndpoints"
                    ][0]["showEngagementPanelEndpoint"]["engagementPanel"][
                        "engagementPanelSectionListRenderer"
                    ][
                        "content"
                    ][
                        "sectionListRenderer"
                    ][
                        "contents"
                    ][
                        0
                    ][
                        "itemSectionRenderer"
                    ][
                        "contents"
                    ][
                        0
                    ][
                        "aboutChannelRenderer"
                    ][
                        "metadata"
                    ][
                        "aboutChannelViewModel"
                    ]
                    return self._about_metadata_json
                except Exception as e:
                    print(e)
                    return None
            elif self.about_json.get("metadata"):
                self._about_metadata_json = self.about_json["metadata"][
                    "channelMetadataRenderer"
                ]
                return self._about_metadata_json

    @property
    def description(self):
        """Get the description for the channel.

        :rtype: str
        """
        return self.about_metadata_json["description"]

    @property
    def total_view_count(self):
        """Get the total view count for the channel.

        :rtype: str
        """
        return int(
            self.about_metadata_json["viewCountText"]
            .split(" views")[0]
            .replace(",", "")
        )

    @property
    def date_joined(self):
        """Get the date the channel was created.

        :rtype: datetime object
        """
        try:
            date_obj = datetime.strptime(
                self.about_metadata_json["joinedDateText"]["content"].split("Joined ")[
                    -1
                ],
                "%b %d, %Y",
            )
            return date_obj
        except Exception as e:
            print(e)
            return None

    @property
    def html(self):
        """Get the html for the /videos page.

        :rtype: str
        """
        if self._html:
            return self._html
        self._html = request.get(self.videos_url)
        return self._html

    @property
    def playlists_html(self):
        """Get the html for the /playlists page.

        Currently unused for any functionality.

        :rtype: str
        """
        if self._playlists_html:
            return self._playlists_html
        else:
            self._playlists_html = request.get(self.playlists_url)
            return self._playlists_html

    @property
    def community_html(self):
        """Get the html for the /community page.

        Currently unused for any functionality.

        :rtype: str
        """
        if self._community_html:
            return self._community_html
        else:
            self._community_html = request.get(self.community_url)
            return self._community_html

    @property
    def featured_channels_html(self):
        """Get the html for the /channels page.

        Currently unused for any functionality.

        :rtype: str
        """
        if self._featured_channels_html:
            return self._featured_channels_html
        else:
            self._featured_channels_html = request.get(self.featured_channels_url)
            return self._featured_channels_html

    @property
    def about_json(self):
        """Get the json for the /about page.

        :rtype: str
        """

        if self._about_json:
            return self._about_json
        else:
            self._about_json = self.extract_yt_initial_data(self.about_html)
            return self._about_json

    @property
    def shorts_json(self):
        """Get the json for the /shorts page.

        :rtype: str
        """

        if self._shorts_json:
            return self._shorts_json
        else:
            self._shorts_json = self.extract_yt_initial_data(self.shorts_html)
            return self._shorts_json

    @property
    def videos_json(self):
        """Get the json for the /videos page page.

        :rtype: str
        """

        if self._videos_json:
            return self._videos_json
        else:
            self._videos_json = self.extract_yt_initial_data(self.html)
            return self._videos_json

    def _find_content_list(self, data):
        if data.get("contents"):
            for tab in data["contents"]["twoColumnBrowseResultsRenderer"]["tabs"]:
                if tab.get("tabRenderer", {}).get("content"):

                    if (
                        tab["tabRenderer"]["content"]
                        .get("richGridRenderer", {})
                        .get("contents")
                    ):
                        return tab["tabRenderer"]["content"]["richGridRenderer"][
                            "contents"
                        ]
                    if (
                        tab["tabRenderer"]["content"]
                        .get("sectionListRenderer", {})
                        .get("contents")
                    ):
                        return tab["tabRenderer"]["content"]["sectionListRenderer"][
                            "contents"
                        ]

        return None

    def _find_searched_content_list(self, data):
        if data.get("contents"):
            for tab in data["contents"]["twoColumnBrowseResultsRenderer"]["tabs"]:
                if not tab.get("expandableTabRenderer"):
                    continue
                return tab["expandableTabRenderer"]["content"]["sectionListRenderer"][
                    "contents"
                ]
        elif data.get("onResponseReceivedActions"):
            if data["onResponseReceivedActions"]:
                return data["onResponseReceivedActions"][0][
                    "appendContinuationItemsAction"
                ].get("continuationItems")
        return None

    def time_to_seconds(self, time_str):
        parts = time_str.split(":")
        parts = [int(part) for part in parts]

        if len(parts) == 2:
            minutes, seconds = parts
            hours = 0
        elif len(parts) == 3:
            hours, minutes, seconds = parts
        else:
            raise ValueError(
                "Invalid time format. Please use HH:MM:SS or MM:SS format."
            )

        total_seconds = hours * 3600 + minutes * 60 + seconds
        return total_seconds

    def _parse_contents(self, contents):
        new_contents = []
        continuation_token = None
        for content in contents:
            sub_content = {}
            if content.get("richItemRenderer"):
                rich_item = content["richItemRenderer"]["content"]
                if rich_item.get("videoRenderer"):
                    renderer_type = "videoRenderer"
                elif rich_item.get("reelItemRenderer"):
                    renderer_type = "reelItemRenderer"
                print(renderer_type)
                if not renderer_type:
                    continue

                item = rich_item[renderer_type]
                sub_content["video_id"] = item["videoId"]
                if item.get("title"):
                    sub_content["title"] = " ".join(
                        [run["text"] for run in item["title"]["runs"]]
                    )
                elif item.get("headline", {}).get("simpleText"):
                    sub_content["title"] = item["headline"]["simpleText"]
                try:
                    if item.get("viewCountText", {}).get("simpleText"):
                        sub_content["views"] = (
                            item["viewCountText"]["simpleText"]
                            .split(" ")[0]
                            .replace(",", "")
                        )

                except:
                    sub_content["views"] = None

                try:
                    if item.get("lengthText", {}).get("simpleText"):
                        sub_content["duration"] = self.time_to_seconds(
                            item["lengthText"]["simpleText"]
                        )

                except:
                    sub_content["duration"] = None
                try:
                    if item.get("descriptionSnippet", {}).get("runs", []):
                        sub_content["description"] = " ".join(
                            [run["text"] for run in item["descriptionSnippet"]["runs"]]
                        )
                except:
                    sub_content["description"] = None
                new_contents.append(sub_content)
            elif content.get("itemSectionRenderer"):
                if content["itemSectionRenderer"]["contents"][0].get("videoRenderer"):
                    video_renderer = content["itemSectionRenderer"]["contents"][0][
                        "videoRenderer"
                    ]
                    sub_content["video_id"] = video_renderer["videoId"]
                    sub_content["title"] = " ".join(
                        [run["text"] for run in video_renderer["title"]["runs"]]
                    )
                    try:
                        sub_content["description"] = " ".join(
                            [
                                run["text"]
                                for run in video_renderer["descriptionSnippet"]["runs"]
                            ]
                        )
                    except:
                        sub_content["description"] = None
                    try:
                        sub_content["views"] = int(
                            video_renderer["viewCountText"]["simpleText"]
                            .split(" ")[0]
                            .replace(",", "")
                        )
                    except:
                        sub_content["views"] = None
                new_contents.append(sub_content)
            elif content.get("continuationItemRenderer"):
                try:
                    continuation_token = content["continuationItemRenderer"][
                        "continuationEndpoint"
                    ]["continuationCommand"]["token"]
                except:
                    pass
        return new_contents, continuation_token

    @property
    def recent_videos(self):
        contents = self._find_content_list(self.videos_json)
        if contents:
            updated_contents, _ = self._parse_contents(contents)
            return updated_contents

        return None

    @property
    def recent_shorts(self):
        contents = self._find_content_list(self.shorts_json)
        if contents:
            updated_contents, _ = self._parse_contents(contents)
            return updated_contents

        return None

    @property
    def about_html(self):
        """Get the html for the /about page.

        Currently unused for any functionality.

        :rtype: str
        """
        if self._about_html:
            return self._about_html
        else:
            self._about_html = request.get(self.about_url)
            return self._about_html

    @property
    def shorts_html(self):
        """Get the html for the /shorts page.

        Currently unused for any functionality.

        :rtype: str
        """
        if self._shorts_html:
            return self._shorts_html
        else:
            self._shorts_html = request.get(self.shorts_url)
            return self._shorts_html

    def search_videos(self, query, continuation_token=None):
        if not self.innertube:
            self.innertube = InnerTube(
                client="WEB",
                use_oauth=self.use_oauth,
                allow_cache=self.allow_oauth_cache,
            )
        response = self.innertube.browse(
            self.channel_id, query=query, continuation_token=continuation_token
        )
        if response:
            contents = self._find_searched_content_list(response)
            if contents:
                updated_contents, continuation_token = self._parse_contents(contents)
                return updated_contents, continuation_token
        return None, None

    def text_to_number(self, text):
        # Define a dictionary mapping suffixes to their multiplication factors
        suffixes = {"K": 1e3, "M": 1e6, "B": 1e9, "T": 1e12}

        # Check if the last character of the input text is one of the suffixes
        if text[-1] in suffixes:
            # Extract the number part and the suffix
            number, suffix = text[:-1], text[-1]

            # Try converting the number part to float and multiply by the corresponding factor
            try:
                return float(number) * suffixes[suffix]
            except ValueError:
                # Return an error message if conversion fails
                return "Error: The number part could not be converted to float."
        else:
            # If there's no suffix, try converting the text directly to float
            try:
                return float(text)
            except ValueError:
                # Return an error message if conversion fails
                return "Error: The input could not be converted to float."

    @property
    def subscriber_count(self):
        """Get the subscriber count for the channel.

        :rtype: str
        """
        try:
            return self.text_to_number(
                self.about_metadata_json["subscriberCountText"].split(" ")[0]
            )

        except:
            return None

    @property
    def country(self):
        """Get the video count for the channel.

        :rtype: str
        """
        try:
            return self.about_metadata_json["country"]

        except:
            return None

    @property
    def video_count(self):
        """Get the video count for the channel.

        :rtype: str
        """
        try:
            return int(
                self.about_metadata_json["videoCountText"]
                .split(" videos")[0]
                .replace(",", "")
            )
        except:
            return None

    def extract_ytcfg_json(self, html):
        """
        Extracts the JSON object from a script tag that contains 'ytcfg.set(' in a given HTML string using regular expressions.

        Args:
        html (str): The HTML string to parse.

        Returns:
        dict: The extracted JSON object, or None if no matching script tag is found.
        """
        # Define a regex pattern to find 'ytcfg.set({<json_here>})'
        pattern = r"ytcfg.set\((\{.*?\})\);"

        # Search for the pattern in the HTML
        match = re.search(pattern, html, re.DOTALL)

        if match:
            # Extract the JSON string
            json_str = match.group(1)

            try:
                # Convert JSON string to a Python dictionary
                json_data = json.loads(json_str)
                return json_data
            except json.JSONDecodeError as e:
                print("Error decoding JSON: ", e)
                return None
        else:
            print("No 'ytcfg.set()' found in the HTML.")
            return None

    # TODO: does this already exist in extract.initial_data??
    def extract_yt_initial_data(self, html):
        """
        Extracts the ytInitialData JSON from HTML content and converts it to a Python dictionary.

        Args:
        html_content (str): The HTML content as a string.

        Returns:
        dict: The extracted JSON data as a Python dictionary or None if the JSON data could not be found.
        """
        if html:
            pattern = r"var ytInitialData = ({.*?});</script>"
            match = re.search(pattern, html, re.DOTALL)
            if not match:
                raise ValueError("ytInitialData not found in the provided HTML.")

            json_data = json.loads(match.group(1))

            return json_data
        return None

    @staticmethod
    def _extract_videos(raw_json: str) -> Tuple[List[str], Optional[str]]:
        """Extracts videos from a raw json page

        :param str raw_json: Input json extracted from the page or the last
            server response
        :rtype: Tuple[List[str], Optional[str]]
        :returns: Tuple containing a list of up to 100 video watch ids and
            a continuation token, if more videos are available
        """
        initial_data = json.loads(raw_json)
        # this is the json tree structure, if the json was extracted from
        # html
        try:
            videos = initial_data["contents"]["twoColumnBrowseResultsRenderer"]["tabs"][
                1
            ]["tabRenderer"]["content"]["sectionListRenderer"]["contents"][0][
                "itemSectionRenderer"
            ][
                "contents"
            ][
                0
            ][
                "gridRenderer"
            ][
                "items"
            ]
        except (KeyError, IndexError, TypeError):
            try:
                # this is the json tree structure, if the json was directly sent
                # by the server in a continuation response
                important_content = initial_data[1]["response"][
                    "onResponseReceivedActions"
                ][0]["appendContinuationItemsAction"]["continuationItems"]
                videos = important_content
            except (KeyError, IndexError, TypeError):
                try:
                    # this is the json tree structure, if the json was directly sent
                    # by the server in a continuation response
                    # no longer a list and no longer has the "response" key
                    important_content = initial_data["onResponseReceivedActions"][0][
                        "appendContinuationItemsAction"
                    ]["continuationItems"]
                    videos = important_content
                except (KeyError, IndexError, TypeError) as p:
                    logger.info(p)
                    return [], None

        try:
            continuation = videos[-1]["continuationItemRenderer"][
                "continuationEndpoint"
            ]["continuationCommand"]["token"]
            videos = videos[:-1]
        except (KeyError, IndexError):
            # if there is an error, no continuation is available
            continuation = None

        # remove duplicates
        return (
            uniqueify(
                list(
                    # only extract the video ids from the video data
                    map(
                        lambda x: (f"/watch?v=" f"{x['gridVideoRenderer']['videoId']}"),
                        videos,
                    )
                ),
            ),
            continuation,
        )
