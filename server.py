#!/usr/bin/python
import gi
import sys
import time
import socket
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
    ack_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client_address = ('127.0.0.1', 5001) # gstreamer udp socket is 127.0.0.1:5000

    def on_new_frame(sink):
        # Send an acknowledgment packet when a new frame is received
        acknowledgment_message = b'Frame received'
        ack_sock.sendto(acknowledgment_message, client_address)
        print('Acknowledgment sent to client\n')

        # Retrieve the buffer from appsink
        sample = sink.emit('pull-sample')
        return Gst.FlowReturn.OK

    # Create the GStreamer pipeline
    pipeline = Gst.parse_launch("""
        udpsrc port=5000 name=udp_src ! application/x-rtp, encoding-name=H264 ! rtph264depay name=rtph264depay ! queue !
        avdec_h264 name=avdec_h264 ! videoconvert ! tee name=t
        t. ! queue ! appsink name=server_sink emit-signals=true
        t. ! queue ! autovideosink
    """)

    # Get the encoder and payloader elements
    udp_src = pipeline.get_by_name("udp_src")
    decoder = pipeline.get_by_name("avdec_h264")
    paydeloader = pipeline.get_by_name("rtph264depay")
    server_sink = pipeline.get_by_name("server_sink")

    if not udp_src or not decoder or not paydeloader or not server_sink:
        print("Elements not found.")
        sys.exit(1)

    # Add buffer probes
    udp_src_pad = udp_src.get_static_pad("src")
    decoder_sink_pad = decoder.get_static_pad("sink")
    decoder_src_pad = decoder.get_static_pad("src")
    paydeloader_sink_pad = paydeloader.get_static_pad("sink")
    paydeloader_src_pad = paydeloader.get_static_pad("src")
    server_sink_pad = server_sink.get_static_pad("sink")

    if udp_src_pad and True:
        udp_src_pad.add_probe(Gst.PadProbeType.BUFFER, buffer_probe, "udp_src")
    if paydeloader_sink_pad and False:
        paydeloader_sink_pad.add_probe(Gst.PadProbeType.BUFFER, buffer_probe, "rtph264depay_sink")
    if paydeloader_src_pad and False:
        paydeloader_src_pad.add_probe(Gst.PadProbeType.BUFFER, buffer_probe, "rtph264depay_src")
    if decoder_sink_pad and True:
        decoder_sink_pad.add_probe(Gst.PadProbeType.BUFFER, buffer_probe, "decoder_sink")
    if decoder_src_pad and True:
        decoder_src_pad.add_probe(Gst.PadProbeType.BUFFER, buffer_probe, "decoder_src")
    if server_sink_pad and True:
        server_sink_pad.add_probe(Gst.PadProbeType.BUFFER, buffer_probe, "server_sink")

    # Add Acknowledgment callback
    server_sink.connect('new-sample', on_new_frame)

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