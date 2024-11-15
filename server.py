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
rec_seqn = 0    # global receive sequence number that counts and labels received encoded frames
dec_seqn = 0    # global decoded sequence number that counts and labels decoded frames
send_seqn = 0   # global send sequence number that counts how the acknowledgment packets

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
    
    if data == 'decoder_sink':
        rec_dict = {'dec_sink_ts': current_time, 'dec_src_ts': 0, 'buf_s': buffer.get_size()}
        global rec_seqn
        shared_dict[rec_seqn] = rec_dict
        rec_seqn += 1
    elif data == 'decoder_src':
        global dec_seqn
        rec_dict = shared_dict[dec_seqn]
        rec_dict['dec_src_ts'] = current_time
        dec_seqn += 1
    if False:
        print(f"{data} buffer_size: {buffer.get_size()} bytes, time: {current_time}")
    
    return Gst.PadProbeReturn.OK

def stop_pipeline(mainloop, pipeline):
    print("Stopping pipeline...")
    pipeline.set_state(Gst.State.NULL)
    mainloop.quit()

def on_new_frame(sink):
    # Retrieve the buffer from appsink
    sample = sink.emit('pull-sample')
    time.sleep(0/1000) # sleep to simulate sample processing

    # Send an acknowledgment packet when a new frame is received
    send_ts = time.perf_counter()

    # Retrieve the corresponding timestamps and buffer size
    global send_seqn
    rec_dict = shared_dict[send_seqn]
    dec_sink_ts = rec_dict['dec_sink_ts']
    dec_src_ts = rec_dict['dec_src_ts']
    buf_s = rec_dict['buf_s']

    # Calculate server latencies in milliseconds
    dec_lat_ms = 1000 * (dec_src_ts - dec_sink_ts)
    proc_lat_ms = 1000 * (send_ts - dec_src_ts)

    # Create the acknowledgment message
    ack_message = f"{send_seqn},{dec_lat_ms:.3f},{proc_lat_ms:.3f},{buf_s}"

    # Increment the send counter
    send_seqn += 1

    # Send the acknowledgment message to the client
    ack_sock.sendto(ack_message.encode(), client_address)

    # Calculate and log the send delay
    current_time = time.perf_counter()
    send_delay_ms = 1000 * (current_time - send_ts)

    # print status
    global rec_seqn
<<<<<<< HEAD
    global dec_seqn
    print(f"rec_seqn: {rec_seqn}\ndec_seqn: {dec_seqn}\nsend_seqn: {send_seqn - 1}, dec_lat_ms: {dec_lat_ms:.3f}, proc_lat_ms: {proc_lat_ms:.3f}\n")
=======
    print(f"send_seqn: {send_seqn - 1}, dec_lat_ms: {dec_lat_ms:.3f}, proc_lat_ms: {proc_lat_ms:.3f}")
>>>>>>> c169b65 (more verbose server output)
    #print(f"sended: {current_time:.6f}, send_delay: {send_delay_ms:.3f} ms, rec_seq_num: {rec_seqn}, send_seq_num: {send_seqn - 1}\n")

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
    t. ! queue ! appsink name=server_sink emit-signals=true sync=false drop=true
    t. ! queue ! videoconvert ! autovideosink
    """)

    # Get the encoder and payloader elements
    udp_src = pipeline.get_by_name("udp_src")
    decoder = pipeline.get_by_name("avdec_h264")
    paydeloader = pipeline.get_by_name("rtph264depay")
    server_sink = pipeline.get_by_name("server_sink")

    if not udp_src:
        print("udp_src not found.")
        sys.exit(1)

    if not decoder:
        print("decoder not found.")
        sys.exit(1)

    if not paydeloader:
        print("paydeloader not found.")
        sys.exit(1)

    if not server_sink:
        print("server_sink not found.")
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
    mainloop = GLib.MainLoop()

    # wait for initial message from client
    print("Waiting for initial Client message")
    global client_address
    init_message, client_address = ack_sock.recvfrom(1024)
    if init_message.decode() == 'init':
        print(f"Init message from client {client_address} successfully received, sent back ack message and start GStreamer pipeline...")
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