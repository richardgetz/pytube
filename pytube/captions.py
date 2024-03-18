import math
import os
import time
import json
import xml.etree.ElementTree as ElementTree
from html import unescape
from typing import Dict, Optional
import html
from pytube import request
from pytube.helpers import safe_filename, target_directory


class Caption:
    """Container for caption tracks."""

    def __init__(self, caption_track: Dict):
        """Construct a :class:`Caption <Caption>`.

        :param dict caption_track:
            Caption track data extracted from ``watch_html``.
        """
        self.url = caption_track.get("baseUrl")

        # Certain videos have runs instead of simpleText
        #  this handles that edge case
        name_dict = caption_track['name']
        if 'simpleText' in name_dict:
            self.name = name_dict['simpleText']
        else:
            for el in name_dict['runs']:
                if 'text' in el:
                    self.name = el['text']

        # Use "vssId" instead of "languageCode", fix issue #779
        self.code = caption_track["vssId"]
        # Remove preceding '.' for backwards compatibility, e.g.:
        # English -> vssId: .en, languageCode: en
        # English (auto-generated) -> vssId: a.en, languageCode: en
        self.code = self.code.strip('.')

    @property
    def xml_captions(self) -> str:
        """Download the xml caption tracks."""
        return request.get(self.url)

    @property
    def json_captions(self) -> dict:
        """Download and parse the json caption tracks."""
        json_captions_url = self.url.replace('fmt=srv3','fmt=json3')
        text = request.get(json_captions_url)
        parsed = json.loads(text)
        assert parsed['wireMagic'] == 'pb3', 'Unexpected captions format'
        return parsed

    def generate_srt_captions(self) -> str:
        """Generate "SubRip Subtitle" captions.

        Takes the xml captions from :meth:`~pytube.Caption.xml_captions` and
        recompiles them into the "SubRip Subtitle" format.
        """
        return self.xml_caption_to_srt(self.xml_captions)

    @staticmethod
    def float_to_srt_time_format(d: float) -> str:
        """Convert decimal durations into proper srt format.

        :rtype: str
        :returns:
            SubRip Subtitle (str) formatted time duration.

        float_to_srt_time_format(3.89) -> '00:00:03,890'
        """
        fraction, whole = math.modf(d)
        time_fmt = time.strftime("%H:%M:%S,", time.gmtime(whole))
        ms = f"{fraction:.3f}".replace("0.", "")
        return time_fmt + ms
    def convert_time(self, ms):
        """Convert milliseconds to SRT time format."""
        hours = ms // 3600000
        minutes = (ms % 3600000) // 60000
        seconds = (ms % 60000) // 1000
        milliseconds = ms % 1000
        return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"
    def xml_caption_to_srt(self, xml_captions: str) -> str:
        """Convert xml caption tracks to "SubRip Subtitle (srt)".

        :param str xml_captions:
            XML formatted caption tracks.
        """
        segments = []
        root = ElementTree.fromstring(xml_captions)
        try:
            for i, child in enumerate(list(root)):
                text = child.text or ""
                caption = unescape(text.replace("\n", " ").replace("  ", " "),)
                try:
                    duration = float(child.attrib["dur"])
                except KeyError:
                    duration = 0.0
                start = float(child.attrib["start"])
                end = start + duration
                sequence_number = i + 1  # convert from 0-indexed to 1.
                line = "{seq}\n{start} --> {end}\n{text}\n".format(
                    seq=sequence_number,
                    start=self.float_to_srt_time_format(start),
                    end=self.float_to_srt_time_format(end),
                    text=caption,
                )
                segments.append(line)
        except Exception as e:
            print("First pass srt failure", e)
            try:
                srt=[]
                counter = 1
                for p in root.iter('p'):
                    # Initial start time and duration
                    start_time = int(p.attrib['t'])
                    duration = int(p.attrib.get('d', '0'))
                    end_time = start_time + duration
                    
                    # Convert times into SRT format (hours:minutes:seconds,milliseconds)
                    start_srt = self.convert_time(start_time)
                    end_srt = self.convert_time(end_time)
                    
                    # Construct caption text, considering nested <s> tags for segments
                    inner_segments = []
                    for s in p:
                        seg_text = s.text.replace('&#39;', "'")  # Basic HTML entity handling
                        if 't' in s.attrib:  # If segment has its own start time, adjust the base start time
                            seg_start = start_time + int(s.attrib['t'])
                            seg_text = f"{seg_text}"  # Placeholder for potential future formatting
                        inner_segments.append(seg_text)
                    caption_text = ''.join(inner_segments).strip()
                    
                    # Skip empty captions
                    if not caption_text:
                        continue
                    
                    # Append to SRT list
                    srt.append(f"{counter}\n{start_srt} --> {end_srt}\n{caption_text}\n")
                    counter += 1
                if len(srt) >0:
                    return '\n'.join(srt).strip()
                else:
                    srt_content = []

                    for i, p in enumerate(root.find('body'), start=1):
                        start_time = int(p.attrib['t'])
                        duration = int(p.attrib['d'])
                        end_time = start_time + duration
                        start_srt = self.convert_time(start_time)
                        end_srt = self.convert_time(end_time)
                        text = html.unescape(p.text).replace("\n", " ").strip()

                        srt_content.append(f"{i}\n{start_srt} --> {end_srt}\n{text}\n")

                    return "\n".join(srt_content)
            except Exception as e:
                print(e)
                return None
        return "\n".join(segments).strip()

    def download(
        self,
        title: str,
        srt: bool = True,
        output_path: Optional[str] = None,
        filename_prefix: Optional[str] = None,
    ) -> str:
        """Write the media stream to disk.

        :param title:
            Output filename (stem only) for writing media file.
            If one is not specified, the default filename is used.
        :type title: str
        :param srt:
            Set to True to download srt, false to download xml. Defaults to True.
        :type srt bool
        :param output_path:
            (optional) Output path for writing media file. If one is not
            specified, defaults to the current working directory.
        :type output_path: str or None
        :param filename_prefix:
            (optional) A string that will be prepended to the filename.
            For example a number in a playlist or the name of a series.
            If one is not specified, nothing will be prepended
            This is separate from filename so you can use the default
            filename but still add a prefix.
        :type filename_prefix: str or None

        :rtype: str
        """
        if title.endswith(".srt") or title.endswith(".xml"):
            filename = ".".join(title.split(".")[:-1])
        else:
            filename = title

        if filename_prefix:
            filename = f"{safe_filename(filename_prefix)}{filename}"

        filename = safe_filename(filename)

        filename += f" ({self.code})"

        if srt:
            filename += ".srt"
        else:
            filename += ".xml"

        file_path = os.path.join(target_directory(output_path), filename)

        with open(file_path, "w", encoding="utf-8") as file_handle:
            if srt:
                file_handle.write(self.generate_srt_captions())
            else:
                file_handle.write(self.xml_captions)

        return file_path

    def __repr__(self):
        """Printable object representation."""
        return '<Caption lang="{s.name}" code="{s.code}">'.format(s=self)
