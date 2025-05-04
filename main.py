from __future__ import annotations

from Components.Edit import crop_video
from Components.Edit import extractAudio
from Components.FaceCrop import combine_videos
from Components.FaceCrop import crop_to_vertical
from Components.LanguageTasks import GetHighlight
from Components.Transcription import transcribeAudio
from Components.VideoHandler import VideoHandler
from Components.VideoHandler import VideoSource


def input_handler():
    values_list = VideoSource.list_values()
    names_list = VideoSource.list_names()
    test = '\n'.join(
        [f"{names_list[i]} - {values_list[i]}" for i in range(
            len(names_list))],
    )
    input_string = f"Chose Video Source ID:\n{test}"

    video_source = ''
    while not VideoSource.has_value(video_source):
        video_source = int(input(input_string))

    if video_source == VideoSource.YOU_TUBE.value:
        source_string = input('Enter YouTube video URL: ')
    else:
        source_string = input('Enter path on local disk to video: ')
    return source_string, video_source


if __name__ == '__main__':
    source_string, video_source_id = input_handler()
    vido_path = VideoHandler(video_source_id).extract_video(source_string)

    Audio = extractAudio(vido_path)
    if Audio is None:
        raise ValueError('No audio file found')

    transcriptions = transcribeAudio(Audio)
    if len(transcriptions) <= 0:
        raise ValueError('No transcriptions found')

    TransText = ''

    for text, start, end in transcriptions:
        TransText += (f"{start} - {end}: {text}")

    start, stop = GetHighlight(TransText)
    if start == 0 and stop == 0:
        raise ValueError('Error in getting highlight')
    print(f"Start: {start} , End: {stop}")

    Output = 'Out.mp4'

    crop_video(vido_path, Output, start, stop)
    croped = 'croped.mp4'

    crop_to_vertical('Out.mp4', croped)
    combine_videos('Out.mp4', croped, 'Final.mp4')
