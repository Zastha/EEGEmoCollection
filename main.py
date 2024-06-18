import moviepy.editor as mp
import os
import re
from pylsl import StreamInlet, resolve_stream
import csv
import time
from datetime import datetime
import threading

# Función para recibir datos FFT del stream LSL y escribirlos en un CSV
def receive_eeg_fft_data(label, csv_writer, inlet, stop_event, fft_file):
    while not stop_event.is_set():
        sample, timestamp = inlet.pull_sample(timeout=0.01)
        if sample:
            formatted_timestamp = datetime.now().strftime('%Y/%m/%d %H:%M:%S.%f')[:-3]
            csv_writer.writerow([formatted_timestamp] + sample + [label])
            fft_file.flush()  # Vaciar el búfer para asegurar la escritura inmediata

# Función para recibir datos RAW del stream LSL y escribirlos en un CSV
def receive_eeg_raw_data(label, csv_writer, inlet, stop_event, channel_indices, raw_file):
    while not stop_event.is_set():
        sample, timestamp = inlet.pull_sample(timeout=0.01)
        if sample:
            formatted_timestamp = datetime.now().strftime('%Y/%m/%d %H:%M:%S.%f')[:-3]
            print(f"Datos RAW recibidos: {sample}")  # Mensaje de depuración para verificar los datos recibidos
            if len(sample) >= max(channel_indices) + 1:
                sample_filtered = [sample[i] for i in channel_indices]
                csv_writer.writerow([formatted_timestamp] + sample_filtered + [label])
                raw_file.flush()  # Vaciar el búfer para asegurar la escritura inmediata
                print(f"Escribiendo datos RAW: {[formatted_timestamp] + sample_filtered + [label]}")  # Mensaje de depuración
            else:
                print(f"Muestra recibida tiene menos canales de los esperados: {sample}")

# Función para reproducir videos y manejar el stream EEG
def reproducir_videos(video_directory, neutral_video, labels, output_directory):
    video_files = [f for f in os.listdir(video_directory) if re.match(r'vid\d+\.mp4', f)]
    video_files.sort(key=lambda f: int(re.search(r'\d+', f).group()))
    
    introduction_video = "Introduction.mp4"
    introduction_video_path = os.path.join(video_directory, introduction_video)
    if not os.path.isfile(introduction_video_path):
        print(f"El archivo de introducción {introduction_video} no existe en la carpeta especificada.")
        return
    
    neutral_video_path = os.path.join(video_directory, neutral_video)
    if not os.path.isfile(neutral_video_path):
        print(f"El archivo neutral {neutral_video} no existe en la carpeta especificada.")
        return
    
    # Resolver y verificar el stream 'AURA_Power'
    print("Buscando el stream 'AURA_Power'...")
    streams = resolve_stream('name', 'AURA_Power')
    if not streams:
        print("No se encontró el stream 'AURA_Power'.")
        return
    inlet = StreamInlet(streams[0])
    print(f"Stream 'AURA_Power' encontrado: {streams[0].name()} - {streams[0].type()}")

    # Resolver y verificar el stream 'AURA'
    print("Buscando el stream 'AURA'...")
    rawStreams = resolve_stream('name', 'AURA')
    if not rawStreams:
        print("No se encontró el stream 'AURA'.")
        return
    rawInlet = StreamInlet(rawStreams[0])
    print(f"Stream 'AURA' encontrado: {rawStreams[0].name()} - {rawStreams[0].type()}")
    
    csv_fft_path = os.path.join(output_directory, 'fft_data.csv')
    csv_raw_path = os.path.join(output_directory, 'raw_data.csv')

    fft_file = open(csv_fft_path, mode='w', newline='', buffering=1)
    raw_file = open(csv_raw_path, mode='w', newline='', buffering=1)

    fft_writer = csv.writer(fft_file)
    raw_writer = csv.writer(raw_file)

    # Columnas para FFT
    nombres_columnas_fft = ['timestamp']
    for i in range(1, 9):
        nombres_columnas_fft.extend([f'Delta{i}', f'Theta{i}', f'Alpha{i}', f'Beta{i}', f'Gamma{i}'])
    nombres_columnas_fft.append('label')
    fft_writer.writerow(nombres_columnas_fft)
    
    # Columnas para RAW
    raw_columns = ['Time and date', 'Fp1', 'Fp2', 'F3', 'F4', 'C3', 'C4', 'P3', 'P4', 
                   'AccX', 'AccY', 'AccZ', 'GyroX', 'GyroY', 'GyroZ', 'Battery', 'Event']
    raw_writer.writerow(raw_columns)

    # Índices de los canales de interés para los datos RAW
    channel_indices = [0, 1, 2, 3, 4, 5, 6, 7]  # Fp1, Fp2, F3, F4, C3, C4, P3, P4
    
    # Reproducir video de introducción
    stop_event_fft = threading.Event()
    stop_event_raw = threading.Event()

    eeg_thread_fft = threading.Thread(target=receive_eeg_fft_data, args=('intro', fft_writer, inlet, stop_event_fft, fft_file))
    eeg_thread_raw = threading.Thread(target=receive_eeg_raw_data, args=('intro', raw_writer, rawInlet, stop_event_raw, channel_indices, raw_file))
    eeg_thread_fft.start()
    eeg_thread_raw.start()
    threads = [(eeg_thread_fft, stop_event_fft), (eeg_thread_raw, stop_event_raw)]
    
    introduction_clip = mp.VideoFileClip(introduction_video_path).volumex(10.0).resize(newsize=(1280, 720))  # Ajustar el volumen
    introduction_clip.preview()  # Usar preview() para probar

    for thread, stop_event in threads:
        stop_event.set()
        thread.join()
    
    # Reproducir video neutral
    stop_event_fft = threading.Event()
    stop_event_raw = threading.Event()

    eeg_thread_fft = threading.Thread(target=receive_eeg_fft_data, args=('neutral', fft_writer, inlet, stop_event_fft, fft_file))
    eeg_thread_raw = threading.Thread(target=receive_eeg_raw_data, args=('neutral', raw_writer, rawInlet, stop_event_raw, channel_indices, raw_file))
    eeg_thread_fft.start()
    eeg_thread_raw.start()
    threads = [(eeg_thread_fft, stop_event_fft), (eeg_thread_raw, stop_event_raw)]
    
    neutral_clip = mp.VideoFileClip(neutral_video_path)
    if neutral_clip.duration > 30:
        neutral_clip = neutral_clip.subclip(neutral_clip.duration - 30, neutral_clip.duration)
    neutral_clip = neutral_clip.resize(newsize=(1280, 720))
    neutral_clip.preview()  # Usar preview() para probar

    for thread, stop_event in threads:
        stop_event.set()
        thread.join()
    
    # Reproducir los otros videos
    for video, label in zip(video_files, labels):
        stop_event_fft = threading.Event()
        stop_event_raw = threading.Event()

        eeg_thread_fft = threading.Thread(target=receive_eeg_fft_data, args=(label, fft_writer, inlet, stop_event_fft, fft_file))
        eeg_thread_raw = threading.Thread(target=receive_eeg_raw_data, args=(label, raw_writer, rawInlet, stop_event_raw, channel_indices, raw_file))
        eeg_thread_fft.start()
        eeg_thread_raw.start()
        threads = [(eeg_thread_fft, stop_event_fft), (eeg_thread_raw, stop_event_raw)]
        
        video_path = os.path.join(video_directory, video)
        clip = mp.VideoFileClip(video_path).resize(newsize=(1280, 720))
        clip.preview()  # Usar preview() para probar

        for thread, stop_event in threads:
            stop_event.set()
            thread.join()

    fft_file.close()
    raw_file.close()

if __name__ == "__main__":
    video_directory = "C:\\EEGOnlyGUI\\assets"
    neutral_video = "neutral.mp4"
    labels = ['happy', 'sad', 'disgust', 'angry', 'fear', 'sad']
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_directory = os.path.join(os.getcwd(), timestamp)
    os.makedirs(output_directory, exist_ok=True)
    
    reproducir_videos(video_directory, neutral_video, labels, output_directory)
