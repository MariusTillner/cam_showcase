#!/usr/bin/python
import gi
import sys
import time
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GObject

# Initialize GStreamer
Gst.init(None)

def buffer_probe(pad, info, data):
    buffer = info.get_buffer()
    current_time = time.perf_counter()
    print(f"{data} buffer_size: {buffer.get_size()} bytes, time: {current_time}")
    return Gst.PadProbeReturn.OK

def stop_pipeline(mainloop, pipeline):
    print("Stopping pipeline...")
    pipeline.set_state(Gst.State.NULL)
    mainloop.quit()

def main():
    # Create the GStreamer pipeline
    pipeline = Gst.parse_launch("""
        videotestsrc pattern=snow name=src ! video/x-raw,width=1920,height=1080,framerate=30/1 ! 
        videoconvert ! x264enc speed-preset=ultrafast tune=zerolatency name=x264enc ! h264parse ! 
        rtph264pay config-interval=1 name=rtph264pay ! udpsink host=127.0.0.1 port=5000 sync=false async=false
    """)

    # Get the encoder and payloader elements
    encoder = pipeline.get_by_name("x264enc")
    payloader = pipeline.get_by_name("rtph264pay")

    if not encoder or not payloader:
        print("Elements not found.")
        sys.exit(1)

    # Add buffer probes
    encoder_sink_pad = encoder.get_static_pad("sink")
    encoder_src_pad = encoder.get_static_pad("src")
    payloader_sink_pad = payloader.get_static_pad("sink")
    payloader_src_pad = payloader.get_static_pad("src")

    if encoder_sink_pad:
        encoder_sink_pad.add_probe(Gst.PadProbeType.BUFFER, buffer_probe, "\nencoder_sink")
    if encoder_src_pad:
        encoder_src_pad.add_probe(Gst.PadProbeType.BUFFER, buffer_probe, "encoder_src")
    if payloader_sink_pad:
        payloader_sink_pad.add_probe(Gst.PadProbeType.BUFFER, buffer_probe, "rtph264pay_sink")
    if payloader_src_pad:
        payloader_src_pad.add_probe(Gst.PadProbeType.BUFFER, buffer_probe, "rtph264pay_src")

    # Set up the main loop
    mainloop = GObject.MainLoop()

    # Set the pipeline to playing
    pipeline.set_state(Gst.State.PLAYING)

    # Start the main loop
    try:
        mainloop.run()
    except:
        stop_pipeline(mainloop, pipeline)
        sys.exit(1)

    # Clean up after main loop exits
    pipeline.set_state(Gst.State.NULL)

if __name__ == '__main__':
    main()