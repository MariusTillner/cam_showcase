#!/usr/bin/python
import gi
import sys
import time
import threading
from threading import Lock
import socket
from Latency import Latency
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GObject


# Initialize GStreamer
Gst.init(None)

# Shared dictionary and lock
shared_dict = {"send_count": 0, "receive_count":0, "latency_class": list()}
data_lock = Lock()

def log_buffer_probe(data, buffer_size):
    if data == 'encoder_sink':
        send_c = shared_dict["send_count"]
        new_lat = Latency(send_c, buffer_size, time.perf_counter())
        shared_dict["latency_class"].append(new_lat)
    elif data == 'encoder_src':
        latency = shared_dict["latency_class"][-1]
        latency.enc_buf_s = buffer_size
        latency.enc_buf_ts = time.perf_counter()
        shared_dict["send_count"] += 1 # new image is sent, increase counter
    else:
        pass

def buffer_probe(pad, info, data):
    buffer = info.get_buffer()
    current_time = time.perf_counter()
    if False:
        print(f"{data} buffer_size: {buffer.get_size()} bytes, time: {current_time}")
    log_buffer_probe(data, buffer.get_size())
    return Gst.PadProbeReturn.OK

def stop_pipeline(mainloop, pipeline):
    print("Stopping pipeline...")
    pipeline.set_state(Gst.State.NULL)
    mainloop.quit()

# The UDP receiver function (runs in a separate thread)
def ack_receiver():
    # Create a UDP socket
    ack_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # Bind the socket to the address (IP and port) where the acknowledgment will be sent
    server_address = ('127.0.0.1', 5001)
    ack_sock.bind(server_address)

    print(f"Listening for acknowledgments on {server_address[0]}:{server_address[1]}")

    while True:
        # Wait to receive data
        data, address = ack_sock.recvfrom(4096)
        
        # Read the shared dictionary
        receive_c = shared_dict["receive_count"]
        latency = shared_dict["latency_class"][receive_c]
        latency.ack_ts = time.perf_counter()
        shared_dict["receive_count"] += 1
        print(latency.__str__())
        print()

def main():
    # Create the GStreamer pipeline
    # Speed-preset: ultrafast, superfast, veryfast, faster, fast, medium (default), slow, slower
    # Tune: fastdecode, zerolatency
    pipeline = Gst.parse_launch("""
        videotestsrc pattern=snow name=src ! video/x-raw,width=1920,height=1080,framerate=30/1 ! 
        videoconvert ! x264enc speed-preset=ultrafast tune=zerolatency name=x264enc ! h264parse ! 
        rtph264pay config-interval=1 name=rtph264pay ! udpsink host=127.0.0.1 port=5000 sync=false async=false name=udp
    """)

    # Get the encoder and payloader elements
    src = pipeline.get_by_name("src")
    encoder = pipeline.get_by_name("x264enc")
    payloader = pipeline.get_by_name("rtph264pay")
    udp = pipeline.get_by_name("udp")

    if not src or not encoder or not payloader or not udp:
        print("Elements not found.")
        sys.exit(1)

    # Add buffer probes
    encoder_sink_pad = encoder.get_static_pad("sink")
    encoder_src_pad = encoder.get_static_pad("src")
    payloader_sink_pad = payloader.get_static_pad("sink")
    payloader_src_pad = payloader.get_static_pad("src")
    udp_pad = udp.get_static_pad("sink")
    src_pad = src.get_static_pad("src")

    if src_pad and True:
        src_pad.add_probe(Gst.PadProbeType.BUFFER, buffer_probe, "\nsrc")
    if encoder_sink_pad and True:
        encoder_sink_pad.add_probe(Gst.PadProbeType.BUFFER, buffer_probe, "encoder_sink")
    if encoder_src_pad and True:
        encoder_src_pad.add_probe(Gst.PadProbeType.BUFFER, buffer_probe, "encoder_src")
    if payloader_sink_pad and False:
        payloader_sink_pad.add_probe(Gst.PadProbeType.BUFFER, buffer_probe, "rtph264pay_sink")
    if payloader_src_pad and False:
        payloader_src_pad.add_probe(Gst.PadProbeType.BUFFER, buffer_probe, "rtph264pay_src")
    if udp_pad and True:
        udp_pad.add_probe(Gst.PadProbeType.BUFFER, buffer_probe, "udp")

    # Set up the main loop
    mainloop = GObject.MainLoop()

    # Start UDP ack receiver thread
    receiver_thread = threading.Thread(target=ack_receiver, daemon=True)
    receiver_thread.start()

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