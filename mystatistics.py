import statistics as stat

class MyStatistics:
    def __init__(self, frame_latency_dict):
        self.frame_latency_dict = frame_latency_dict

    def clean_uncomplete_entries(self):
        cleaned_frame_latency_list = list()
        uncomplete_counter = 0
        for key in self.frame_latency_dict.keys():
            frame_lat_entry = self.frame_latency_dict[key]
            if frame_lat_entry.complete:
                cleaned_frame_latency_list.append(frame_lat_entry)
            else:
                uncomplete_counter += 1

        return cleaned_frame_latency_list, uncomplete_counter

    def print_statistics(self):
        frame_latency_list, uncomplete_counter = self.clean_uncomplete_entries()
        enc_buf_s_list = list()
        server_dec_ms_list = list()
        server_proc_ms_list = list()
        encoding_lat_ms_list = list()
        network_rtt_ms_list = list()
        full_rtt_ms_list = list()

        for frame_lat in frame_latency_list:
            enc_buf_s_list.append(frame_lat.enc_buf_s)
            server_dec_ms_list.append(frame_lat.server_dec_lat_ms)
            encoding_lat_ms_list.append(frame_lat.encoding_lat_ms())
            network_rtt_ms_list.append(frame_lat.network_lat_ms())
            full_rtt_ms_list.append(frame_lat.full_lat_ms())

        print(f"""
encoded size:
\tmin:\t{min(enc_buf_s_list)} bytes
\tmean:\t{stat.mean(enc_buf_s_list)} bytes
\tmedian:\t{stat.median(enc_buf_s_list)} bytes
\tmax:\t{max(enc_buf_s_list)} bytes
        """)

        print(f"""
client encoding latency:
\tmin:\t{min(encoding_lat_ms_list)} ms
\tmean:\t{stat.mean(encoding_lat_ms_list)} ms
\tmedian:\t{stat.median(encoding_lat_ms_list)} ms
\tmax:\t{max(encoding_lat_ms_list)} ms
        """)
        
        print(f"""
server decoding latency:
\tmin:\t{min(server_dec_ms_list)} ms
\tmean:\t{stat.mean(server_dec_ms_list)} ms
\tmedian:\t{stat.median(server_dec_ms_list)} ms
\tmax:\t{max(server_dec_ms_list)} ms
        """)

        print(f"""
5G Round Trip Time:
\tmin:\t{min(network_rtt_ms_list)} ms
\tmean:\t{stat.mean(network_rtt_ms_list)} ms
\tmedian:\t{stat.median(network_rtt_ms_list)} ms
\tmax:\t{max(network_rtt_ms_list)} ms
        """)

        print(f"""
Full Round Trip Time:
\tmin:\t{min(full_rtt_ms_list)} ms
\tmean:\t{stat.mean(full_rtt_ms_list)} ms
\tmedian:\t{stat.median(full_rtt_ms_list)} ms
\tmax:\t{max(full_rtt_ms_list)} ms
        """)