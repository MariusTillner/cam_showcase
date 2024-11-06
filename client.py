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
raw_seqn = -1    # global raw sequence number that counts the appearing raw frames
enc_seqn = -1    # global ecoded sequence number that counts the encoded frames
rec_seqn = -1    # global receive sequence number that counts the receive frames

# global timestamps to track periodicity in the pipeline
raw_ts = 0
rec_ts = 0

# shared dict that will save the FrameLatency instances that will track the different latencies of a frame
shared_dict = {}

# Ack receiver socket
server_address = ('192.168.70.129', 5001)
ack_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


#############################
######### FUNCTIONS #########
#############################
def log_buffer_probe(data, buffer_size):
    if data == 'src_out':
        global raw_ts
        current_time = time.perf_counter()
        print(f"{data}\t\ttime since last call: {1000*(current_time - raw_ts):.3f} ms")
        raw_ts = current_time
    elif data == 'x264enc_in':
        global raw_seqn
        raw_seqn += 1
        frame_latency = FrameLatency(raw_seqn, buffer_size, time.perf_counter())
        shared_dict[raw_seqn] = frame_latency
    elif data == 'x264enc_out':
        global enc_seqn
        enc_seqn += 1
        frame_latency = shared_dict[enc_seqn]
        frame_latency.enc_buf_s = buffer_size
        frame_latency.enc_buf_ts = time.perf_counter()
    else:
        pass

def buffer_probe(pad, info, data):
    buffer = info.get_buffer()
    if False:
        print(f"{data} buffer_size: {buffer.get_size()} bytes, time: {time.perf_counter()}")
    log_buffer_probe(data, buffer.get_size())
    return Gst.PadProbeReturn.OK

def stop_pipeline(mainloop, pipeline):
    print("Stopping pipeline...")
    pipeline.set_state(Gst.State.NULL)
    mainloop.quit()

def add_buffer_probe(pipeline, element_name, sink_pad: bool, src_pad: bool):
    pipeline_element = pipeline.get_by_name(element_name)

    if not pipeline_element:
        print(f"{element_name} not found.")
        sys.exit(1)

    if sink_pad:
        sink_pad = pipeline_element.get_static_pad("sink")
        pad_name = element_name + "_in"
        sink_pad.add_probe(Gst.PadProbeType.BUFFER, buffer_probe, pad_name)
    if src_pad:
        src_pad = pipeline_element.get_static_pad("src")
        pad_name = element_name + "_out"
        src_pad.add_probe(Gst.PadProbeType.BUFFER, buffer_probe, pad_name)

# The UDP receiver function (runs in a separate thread)
def ack_receiver_function():
    while True:
        # Wait to receive data, and then decode it
        data, _ = ack_sock.recvfrom(4096)
        server_rec_seqn, server_dec_lat_ms_str, server_proc_lat_ms_str, buffer_size_str = data.decode().split(",")
        server_rec_seqn = int(server_rec_seqn) # string to int

        # increase local receive sequence number
        global rec_seqn
        rec_seqn += 1

        # print periodicity
        global rec_ts
        current_time = time.perf_counter()
        print(f"ack_rec_fun\ttime since last receive: {1000*(current_time - rec_ts):.3f} ms")
        rec_ts = current_time

        # check if there is a mismatch of received sequence number of server and client sequence number
        if server_rec_seqn != rec_seqn:
            print(f"server_rec_seqn\t{server_rec_seqn} does not match rec_seqn: {rec_seqn}")
            print(f"jumping frame: {', '.join(str(i) for i in range(rec_seqn, server_rec_seqn))}")
        
        # Retrieve the current frame's latency information
        frame_latency = shared_dict[server_rec_seqn]
        
        # Update the acknowledgment timestamp
        frame_latency.ack_ts = time.perf_counter()
        
        # decode the rest of the received data and fill the FrameLatency class with its data
        frame_latency.ack_enc_s = int(buffer_size_str)
        frame_latency.server_proc_lat_ms = float(server_proc_lat_ms_str)
        frame_latency.server_dec_lat_ms = float(server_dec_lat_ms_str)
        
        # Print the frame latency information
        print(f"\n{frame_latency}\n\n")

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

    # add all buffer probes for measuring latency and logging infos
    add_buffer_probe(pipeline, "src", sink_pad=False, src_pad=True)
    add_buffer_probe(pipeline, "x264enc", sink_pad=True, src_pad=True)
    add_buffer_probe(pipeline, "rtph264pay", sink_pad=False, src_pad=False)
    add_buffer_probe(pipeline, "udp", sink_pad=False, src_pad=False)

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