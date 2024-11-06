#!/usr/bin/python
import gi
import sys
import time
import threading
from threading import Lock
import socket
from FrameLatency import FrameLatency
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib


####################################
######### Global Variables #########
####################################
# Initialize GStreamer
Gst.init(None)

# Global sequence numbers
raw_seqn = 0    # global raw sequence number that counts the appearing raw frames
enc_seqn = 0    # global ecoded sequence number that counts the encoded frames
rec_seqn = 0    # global receive sequence number that counts the receive frames

# shared dict that will save the FrameLatency instances that will track the different latencies of a frame
shared_dict = {}

# Ack receiver socket
server_address = ('192.168.70.129', 5001)
ack_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


#############################
######### FUNCTIONS #########
#############################
def log_buffer_probe(data, buffer_size):
    if data == 'encoder_sink':
        global raw_seqn
        frame_latency = FrameLatency(raw_seqn, buffer_size, time.perf_counter())
        shared_dict[raw_seqn] = frame_latency
        raw_seqn += 1
    elif data == 'encoder_src':
        global enc_seqn
        frame_latency = shared_dict[enc_seqn]
        frame_latency.enc_buf_s = buffer_size
        frame_latency.enc_buf_ts = time.perf_counter()
        enc_seqn += 1
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
def ack_receiver_function():
    while True:
        # Wait to receive data, and then decode it
        data, _ = ack_sock.recvfrom(4096)
        server_rec_seqn, server_dec_lat_ms_str, server_proc_lat_ms_str, buffer_size_str = data.decode().split(",")
        server_rec_seqn = int(server_rec_seqn) # string to int

        # check if there is a mismatch of received sequence number of server and client sequence number
        global rec_seqn
        if server_rec_seqn != rec_seqn:
            print(f"server_rec_seqn: {server_rec_seqn} does not match rec_seqn: {rec_seqn}")
        
        # Retrieve the current frame's latency information
        frame_latency = shared_dict[server_rec_seqn]
        
        # Update the acknowledgment timestamp
        frame_latency.ack_ts = time.perf_counter()
        
        # decode the rest of the received data and fill the FrameLatency class with its data
        frame_latency.ack_enc_s = int(buffer_size_str)
        frame_latency.server_proc_lat_ms = float(server_proc_lat_ms_str)
        frame_latency.server_dec_lat_ms = float(server_dec_lat_ms_str)
        
        # Print the frame latency information
        print(f"{frame_latency}\n")

        # increase local receive sequence number
        rec_seqn += 1

def main():
    # Create the GStreamer pipeline
    # Speed-preset: ultrafast, superfast, veryfast, faster, fast, medium (default), slow, slower
    # Tune: fastdecode, zerolatency
    pipeline = Gst.parse_launch("""
        videotestsrc pattern=snow name=src ! 
        video/x-raw,width=1080,height=720,framerate=30/1 ! 
        queue ! 
        videoconvert ! 
        x264enc speed-preset=ultrafast tune=zerolatency name=x264enc ! 
        h264parse ! 
        rtph264pay config-interval=1 name=rtph264pay ! 
        udpsink host=192.168.70.129 port=5000 sync=false async=false name=udp
    """)

    # Get the encoder and payloader elements
    src = pipeline.get_by_name("src")
    encoder = pipeline.get_by_name("x264enc")
    payloader = pipeline.get_by_name("rtph264pay")
    udp = pipeline.get_by_name("udp")

    if not src:
        print("src not found.")
        sys.exit(1)

    if not encoder:
        print("encoder not found.")
        sys.exit(1)

    if not payloader:
        print("payloader not found.")
        sys.exit(1)

    if not udp:
        print("udp not found.")
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
    mainloop = GLib.MainLoop()

    # send initial message to server, so server knows which ip to answer to
    ack_sock.sendto(b'init', server_address)
    print("Sent initial message to Server")

    # receive initial message acknowledgment, this makes sure the network connection is working
    ack_message, _ = ack_sock.recvfrom(1024)
    print(f"Received ack message from Server ({ack_message.decode()}), Network connection works, start GStreamer pipeline...")

    # Start UDP ack receiver thread
    receiver_thread = threading.Thread(target=ack_receiver_function, daemon=True)
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