import statistics as stat
import numpy as np

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
            quant1 = np.percentile(enc_buf_s_list, [5, 25, 50, 75, 95])

            server_dec_ms_list.append(frame_lat.server_dec_lat_ms)
            quant2 = np.percentile(server_dec_ms_list, [5, 25, 50, 75, 95])
            
            encoding_lat_ms_list.append(frame_lat.encoding_lat_ms())
            quant3 = np.percentile(encoding_lat_ms_list, [5, 25, 50, 75, 95])
            
            network_rtt_ms_list.append(frame_lat.network_lat_ms())
            quant4 = np.percentile(network_rtt_ms_list, [5, 25, 50, 75, 95])
            
            full_rtt_ms_list.append(frame_lat.full_lat_ms())
            quant5 = np.percentile(full_rtt_ms_list, [5, 25, 50, 75, 95])

        print(f"total frames: {len(self.frame_latency_dict)}, uncompleted frames: {len(uncomplete_counter)}")
        
        print(f"""
encoded size:
\tmin:\t{min(enc_buf_s_list)} bytes
\tmean:\t{stat.mean(enc_buf_s_list):.0f} bytes
\tmedian:\t{stat.median(enc_buf_s_list)} bytes
\tmax:\t{max(enc_buf_s_list)} bytes
\tquantiles:\t{quant1} 
        """)

        print(f"""
client encoding latency:
\tmin:\t{min(encoding_lat_ms_list):.3f} ms
\tmean:\t{stat.mean(encoding_lat_ms_list):.3f} ms
\tmedian:\t{stat.median(encoding_lat_ms_list):.3f} ms
\tmax:\t{max(encoding_lat_ms_list):.3f} ms
\tquantiles:\t{quant2}
        """)
        
        print(f"""
server decoding latency:
\tmin:\t{min(server_dec_ms_list):.3f} ms
\tmean:\t{stat.mean(server_dec_ms_list):.3f} ms
\tmedian:\t{stat.median(server_dec_ms_list):.3f} ms
\tmax:\t{max(server_dec_ms_list):.3f} ms
\tquantiles:\t{quant3}
        """)

        print(f"""
5G Round Trip Time:
\tmin:\t{min(network_rtt_ms_list):.3f} ms
\tmean:\t{stat.mean(network_rtt_ms_list):.3f} ms
\tmedian:\t{stat.median(network_rtt_ms_list):.3f} ms
\tmax:\t{max(network_rtt_ms_list):.3f} ms
\tquantiles:\t{quant4}
        """)

        print(f"""
Full Round Trip Time:
\tmin:\t{min(full_rtt_ms_list):.3f} ms
\tmean:\t{stat.mean(full_rtt_ms_list):.3f} ms
\tmedian:\t{stat.median(full_rtt_ms_list):.3f} ms
\tmax:\t{max(full_rtt_ms_list):.3f} ms
\tquantiles:\t{quant5}
        """)