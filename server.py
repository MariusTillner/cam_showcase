#!/usr/bin/python
import gi
import sys
import time
import socket
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GObject

# Initialize GStreamer
Gst.init(None)

# save receive and send data
rec_send_dict = {"rec_c": 0, "rec_lst": list(), "send_c": 0}

def buffer_probe(pad, info, data):
    buffer = info.get_buffer()
    current_time = time.perf_counter()
    if data == 'decoder_sink':
        rec_send_dict["rec_lst"].append((time.perf_counter(), buffer.get_size()))
        rec_send_dict["rec_c"] += 1
    print(f"{data} buffer_size: {buffer.get_size()} bytes, time: {current_time}")
    return Gst.PadProbeReturn.OK

def stop_pipeline(mainloop, pipeline):
    print("Stopping pipeline...")
    pipeline.set_state(Gst.State.NULL)
    mainloop.quit()

ack_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
client_address = ('127.0.0.1', 5001) # gstreamer udp socket is 127.0.0.1:5000

def on_new_frame(sink):
    # Send an acknowledgment packet when a new frame is received
    # sleep 20 ms to simulate signal processing
    time.sleep(0/1000)
    send_ts = time.perf_counter()
    send_c = rec_send_dict["send_c"]
    receive = rec_send_dict["rec_lst"][send_c]
    receive_ts = receive[0]
    buf_s = receive[1]
    server_proc_latency_ms = 1000*(send_ts - receive_ts)
    ack_message = f"{server_proc_latency_ms},{buf_s}"
    rec_send_dict["send_c"] += 1
    print(f"send: {send_ts}")
    ack_sock.sendto(ack_message.encode(), client_address)

    # Retrieve the buffer from appsink
    sample = sink.emit('pull-sample')
    print(f"sended: {time.perf_counter()}, send_delay: {1000*(time.perf_counter()-send_ts):.3f} ms, rec_c: {rec_send_dict["rec_c"]}, send_c: {rec_send_dict['send_c']}\n")
    return Gst.FlowReturn.OK

def main():

    # Create the GStreamer pipeline
    pipeline = Gst.parse_launch("""
        udpsrc port=5000 name=udp_src ! application/x-rtp, encoding-name=H264 ! rtph264depay name=rtph264depay ! queue !
        avdec_h264 name=avdec_h264 ! videoconvert ! tee name=t
        t. ! queue ! appsink name=server_sink emit-signals=true
        t. ! queue ! autovideosink sync=false
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
    server_sink_pad = server_sink.get_static_pad("server_sink")

    if udp_src_pad and False:
        udp_src_pad.add_probe(Gst.PadProbeType.BUFFER, buffer_probe, "udp_src")
    if paydeloader_sink_pad and False:
        paydeloader_sink_pad.add_probe(Gst.PadProbeType.BUFFER, buffer_probe, "rtph264depay_sink")
    if paydeloader_src_pad and False:
        paydeloader_src_pad.add_probe(Gst.PadProbeType.BUFFER, buffer_probe, "rtph264depay_src")
    if decoder_sink_pad and True:
        decoder_sink_pad.add_probe(Gst.PadProbeType.BUFFER, buffer_probe, "decoder_sink")
    if decoder_src_pad and True:
        decoder_src_pad.add_probe(Gst.PadProbeType.BUFFER, buffer_probe, "decoder_src")
    if server_sink_pad and False:
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