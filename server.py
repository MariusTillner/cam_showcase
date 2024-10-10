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
    if data == "decoder_src":
        print() # newline
    return Gst.PadProbeReturn.OK

def stop_pipeline(mainloop, pipeline):
    print("Stopping pipeline...")
    pipeline.set_state(Gst.State.NULL)
    mainloop.quit()

def main():
    # Create the GStreamer pipeline
    pipeline = Gst.parse_launch("""
        udpsrc port=5000 ! application/x-rtp, encoding-name=H264 ! rtph264depay name=rtph264depay ! queue !
        avdec_h264 name=avdec_h264 ! videoconvert ! autovideosink
    """)

    # Get the encoder and payloader elements
    decoder = pipeline.get_by_name("avdec_h264")
    paydeloader = pipeline.get_by_name("rtph264depay")

    if not decoder or not paydeloader:
        print("Elements not found.")
        sys.exit(1)

    # Add buffer probes
    decoder_sink_pad = decoder.get_static_pad("sink")
    decoder_src_pad = decoder.get_static_pad("src")
    paydeloader_sink_pad = paydeloader.get_static_pad("sink")
    paydeloader_src_pad = paydeloader.get_static_pad("src")

    if decoder_sink_pad:
        decoder_sink_pad.add_probe(Gst.PadProbeType.BUFFER, buffer_probe, "decoder_sink")
    if decoder_src_pad:
        decoder_src_pad.add_probe(Gst.PadProbeType.BUFFER, buffer_probe, "decoder_src")
    if paydeloader_sink_pad:
        paydeloader_sink_pad.add_probe(Gst.PadProbeType.BUFFER, buffer_probe, "rtph264depay_sink")
    if paydeloader_src_pad:
        paydeloader_src_pad.add_probe(Gst.PadProbeType.BUFFER, buffer_probe, "rtph264depay_src")

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