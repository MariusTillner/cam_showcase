#!/usr/bin/python
import gi
import sys
import time
import socket
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib


####################################
######### Global Variables #########
####################################
# Initialize GStreamer
Gst.init(None)

# Global sequence numbers
rec_seqn = -1    # global receive sequence number that counts and labels received encoded frames
dec_seqn = -1    # global decoded sequence number that counts and labels decoded frames
local_ack_seqn = -1 # global variable that saves the local counter for function on_new_frame 

# Global timestamps to track periodicity in the pipeline
rec_ts = 0
last_send_ts = 0

# Dict that will save the latencies of received frames, latency data will be saved as dict
shared_dict = {}

# set up acknowledgment socket
ack_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server_address = ("127.0.0.1", 5001)
ack_sock.bind(server_address)
client_address = None # Will be set after receiving the initial message from client
print(f"Server Socket is listening on {server_address}")


#############################
######### FUNCTIONS #########
#############################
def buffer_probe(pad, info, data):
    buffer = info.get_buffer()
    current_time = time.perf_counter()
    
    if data == 'avdec_h264_in':
        global rec_seqn
        rec_seqn += 1
        rec_dict = {'dec_sink_ts': current_time, 'dec_src_ts': 0, 'buf_s': buffer.get_size()}
        shared_dict[rec_seqn] = rec_dict
        global rec_ts
        print(f"""{data}\ttime: {current_time} 
        \ttime_since_last_rec: {1000*(current_time - rec_ts):.3f} ms 
        \trec_seqn: {rec_seqn}
        \tbuffer_size: {buffer.get_size()} bytes\n""")
        rec_ts = current_time
    elif data == 'avdec_h264_out':
        global dec_seqn
        # set decode sequence number to receive seqnum, because high jitter sometimes throws away
        # encoded frames and only the last frame is decoded
        dec_seqn = rec_seqn
        rec_dict = shared_dict[dec_seqn]
        rec_dict['dec_src_ts'] = current_time
        print(f"""{data}\ttime: {current_time} 
        \tdec_seqn: {dec_seqn} 
        \tbuffer_size: {buffer.get_size()} bytes\n""")
    return Gst.PadProbeReturn.OK

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

def add_appsink_callback(pipeline, element_name):
    appsink = pipeline.get_by_name(element_name)
    if not appsink:
        print(f"{element_name} not found.")
        sys.exit(1)
    appsink_pad = appsink.get_static_pad(element_name)
    appsink.connect('new-sample', on_new_frame) # Add Acknowledgment callback

def stop_pipeline(mainloop, pipeline):
    print("Stopping pipeline...")
    pipeline.set_state(Gst.State.NULL)
    mainloop.quit()

def on_new_frame(sink):
    # save acknowledgement sequence number immediately because it can change during the sample processing
    global dec_seqn
    ack_seqn = dec_seqn
    global local_ack_seqn
    local_ack_seqn += 1
    print(f"""on_new_frame\ttime: {time.perf_counter()}
    \t\tack_seqn: {ack_seqn}
    \t\tlocal_ack_seqn: {local_ack_seqn}""")

    # Retrieve the buffer from appsink
    sample = sink.emit('pull-sample')
    time.sleep(0/1000) # sleep to simulate sample processing

    # Send an acknowledgment packet when a new frame is received
    send_ts = time.perf_counter()

    # Retrieve the corresponding timestamps and buffer size
    rec_dict = shared_dict[ack_seqn]
    dec_sink_ts = rec_dict['dec_sink_ts']
    dec_src_ts = rec_dict['dec_src_ts']
    buf_s = rec_dict['buf_s']

    # Calculate server latencies in milliseconds
    dec_lat_ms = 1000 * (dec_src_ts - dec_sink_ts)
    proc_lat_ms = 1000 * (send_ts - dec_src_ts)

    # Create the acknowledgment message
    ack_message = f"{ack_seqn},{dec_lat_ms:.3f},{proc_lat_ms:.3f},{buf_s}"

    # Send the acknowledgment message to the client
    ack_sock.sendto(ack_message.encode(), client_address)

    # Calculate and log the send delay
    current_time = time.perf_counter()
    send_delay_ms = 1000 * (current_time - send_ts)

    # print status
    global rec_seqn
    global last_send_ts
    current_time = time.perf_counter()
    print(f"""
    \t\trec_seqn: {rec_seqn}
    \t\tdec_seqn: {dec_seqn}
    \t\tsend_seqn: {ack_seqn}
    \t\tdec_lat: {dec_lat_ms:.3f} ms
    \t\tproc_lat: {proc_lat_ms:.3f} ms
    \t\ttime_since_last_send: {1000*(current_time - last_send_ts):.3f} ms
    \n""")
    last_send_ts = current_time

    return Gst.FlowReturn.OK

def main():
    # Create the GStreamer pipeline
    pipeline = Gst.parse_launch("""
    udpsrc port=5000 name=udp_src ! 
    application/x-rtp, encoding-name=H264 ! 
    rtph264depay name=rtph264depay ! 
    queue ! 
    avdec_h264 name=avdec_h264 ! 
    queue ! 
    tee name=t
    t. ! queue ! appsink name=appsink emit-signals=true sync=false drop=true
    t. ! queue ! videoconvert ! autovideosink
    """)

    # add all buffer probes for measuring latency and logging infos
    add_buffer_probe(pipeline, "udp_src", sink_pad=False, src_pad=False)
    add_buffer_probe(pipeline, "avdec_h264", sink_pad=True, src_pad=True)
    add_buffer_probe(pipeline, "rtph264depay", sink_pad=False, src_pad=False)
    add_buffer_probe(pipeline, "appsink", sink_pad=False, src_pad=False)

    # connect acknowledgement packet sender to appsink in pipeline
    add_appsink_callback(pipeline, "appsink")

    # Set up the main loop
    mainloop = GLib.MainLoop()

    # wait for initial message from client
    print("Waiting for initial Client message")
    global client_address
    init_message, client_address = ack_sock.recvfrom(1024)
    if init_message.decode() == 'init':
        print(f"Init message from client {client_address} successfully received, sent back ack message and start GStreamer pipeline...\n\n")
        ack_sock.sendto(b'ack', client_address)
    else:
        print(f"Wrong init message {init_message.decode()}, should be \"init\", from {client_address}, abort...")
        return

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